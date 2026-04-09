import os
import time
import traceback
import logging
from collections import defaultdict
from multiprocessing import Process, freeze_support
from pathlib import Path

import pygame
import zmq
from pyarrow import deserialize, serialize
from pygame.locals import *
import ast

_SHOWDOWN_ROOT = Path(__file__).resolve().parent.parent

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("game.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def safe_wait(seconds):
    """非阻塞等待（处理退出事件）"""
    start = pygame.time.get_ticks()
    while pygame.time.get_ticks() - start < seconds * 1000:
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                exit()
        pygame.event.pump()
        pygame.time.wait(10)


class Game:
    def __init__(self) -> None:
        log.info("初始化 pygame...")
        pygame.init()
        pygame.display.set_caption("升级对战")

        # 字体
        font_path = str(_SHOWDOWN_ROOT / 'fonts' / 'HanYiRegular.ttf')
        if not os.path.exists(font_path):
            font_path = None  # 使用默认字体
        self.font = pygame.font.Font(font_path, 20)
        self.font_button = pygame.font.Font(font_path, 24)

        # 路径
        self.cards_image_path = str(_SHOWDOWN_ROOT / 'images' / 'cards') + os.sep
        self.background_image_path = str(_SHOWDOWN_ROOT / 'images' / 'background.png')
        self.partbackground_image_path = str(_SHOWDOWN_ROOT / 'images' / 'partback.bmp')
        self.chup_image_path = str(_SHOWDOWN_ROOT / 'images' / 'chup.png')
        self.buc_image_path = str(_SHOWDOWN_ROOT / 'images' / 'buc.png')

        # 加载基础图片
        try:
            self.chupImage = pygame.image.load(self.chup_image_path)
            self.bucImage = pygame.image.load(self.buc_image_path)
            self.backgroundImage = pygame.image.load(self.background_image_path)
            self.partback = pygame.image.load(self.partbackground_image_path)
            self.cardbackImage = pygame.image.load(self.cards_image_path + 'back.bmp')
            log.info("基础图片加载成功")
        except pygame.error as e:
            log.error(f"图片加载失败: {e}")
            raise

        self.height = 900
        self.width = 1200

        # 预缩放背景（避免每帧缩放）
        self.bg_scaled = pygame.transform.scale(self.backgroundImage, (self.width, self.height))
        self.partback_scaled = pygame.transform.scale(self.partback, (self.width, self.height // 3))

        # 等待画面
        waiting_image_path = str(_SHOWDOWN_ROOT / 'images' / 'waiting.jpg')
        self.screen = pygame.display.set_mode((self.width, self.height), 0, 32)
        waiting_img = pygame.image.load(waiting_image_path).convert()
        self.screen.blit(pygame.transform.scale(waiting_img, (self.width, self.height)), (0, 0))
        pygame.display.update()
        log.info("窗口创建完成")

        # 游戏状态
        self.myFixedSeat = 3
        self.msgMyPos = None
        self.my_handCards = []
        self.playerRests = [27, 27, 27, 27]
        self.playerPlayAreas = [None, None, None, None]

        self.curRank = '2'
        self.selfRank = '2'
        self.oppRank = '2'
        self.stage = ''
        self.legalActions = []          # 原始动作列表
        self.legalActions_set = []      # 用于快速匹配的计数器列表

        self.tributeflag = 0
        self.backflag = 0
        self.antiflag = 0
        self.tributeinfo = None
        self.backinfo = None
        self.antiPosList = []

        # 座位坐标（固定，相对于 myFixedSeat=3）
        self.relative_positions = [
            (self.width // 2 - 100, self.height - 500),  # 下方（自己）
            (self.width - 400, self.height // 2 - 100),  # 右侧
            (self.width // 2 - 100, 200),                # 上方
            (150, self.height // 2 - 100)                # 左侧
        ]
        self.text_offsets = [(0, -30), (0, -30), (0, -30), (0, -30)]

        # 图片缓存
        self.image_cache = {}

        # UI 交互状态
        self.selected_indices = set()    # 当前选中手牌的索引
        self.button_rects = {}           # 按钮名称 -> pygame.Rect
        self.hover_button = None         # 当前鼠标悬停的按钮名称
        self.message_text = None         # 临时提示文字（如“出牌不符合规则”）
        self.message_until = 0            # 提示消失的 tick

        # 手牌绘制参数
        self.base_width = 0

    # ---------- 辅助方法 ----------
    def get_card_image(self, card_name):
        """带缓存的牌面图片加载"""
        if card_name not in self.image_cache:
            try:
                img = pygame.image.load(self.cards_image_path + card_name + '.jpg').convert_alpha()
                # 添加简单阴影效果（预生成一个半透明表面）
                shadow = pygame.Surface(img.get_size(), pygame.SRCALPHA)
                shadow.fill((0, 0, 0, 40))
                # 将原图和阴影合并存储
                self.image_cache[card_name] = img
                self.image_cache[card_name + "_shadow"] = shadow
            except pygame.error as e:
                log.error(f"加载牌面失败: {card_name}.jpg - {e}")
                return None
        return self.image_cache[card_name]

    def draw_card_with_shadow(self, card_name, x, y, y_offset=0):
        """绘制一张牌，带阴影，可指定Y轴偏移（用于上浮）"""
        img = self.get_card_image(card_name)
        if not img:
            return
        shadow = self.image_cache.get(card_name + "_shadow")
        if shadow:
            self.screen.blit(shadow, (x + 3, y + 3 + y_offset))
        self.screen.blit(img, (x, y + y_offset))

    def get_screen_pos(self, seat):
        offset = (seat - self.myFixedSeat) % 4
        return self.relative_positions[offset]

    def get_text_pos(self, seat):
        pos = self.get_screen_pos(seat)
        off = self.text_offsets[seat % 4]
        return (pos[0] + off[0], pos[1] + off[1])

    def show_message(self, text, color=(255, 0, 0), duration=1.5):
        """显示临时消息（会在绘制时自动消失）"""
        self.message_text = text
        self.message_color = color
        self.message_until = pygame.time.get_ticks() + int(duration * 1000)

    # ---------- 核心绘制 ----------
    def draw_table(self):
        """全屏重绘（每帧调用）"""
        # 1. 背景
        self.screen.blit(self.bg_scaled, (0, 0))
        self.screen.blit(self.partback_scaled, (0, self.height * 2 // 3))

        # 2. 级数信息
        self.screen.blit(self.font.render(f"当前级数 {self.curRank}", True, (0, 0, 0)), (0, 0))
        self.screen.blit(self.font.render(f"我方级数 {self.selfRank}", True, (0, 0, 0)), (0, 20))
        self.screen.blit(self.font.render(f"敌方级数 {self.oppRank}", True, (0, 0, 0)), (0, 40))

        # 3. 四个玩家的剩余牌数、牌背、出牌区
        for seat in range(4):
            pos = self.get_screen_pos(seat)
            text_pos = self.get_text_pos(seat)

            # 剩余牌数
            rest_surf = self.font.render(f"{self.playerRests[seat]}张", True, (0, 0, 0))
            self.screen.blit(rest_surf, text_pos)

            # 牌背（非自己）
            if seat != self.myFixedSeat:
                self.screen.blit(self.cardbackImage, pos)

            # 出牌区
            cards = self.playerPlayAreas[seat]
            if cards and isinstance(cards, list):
                for j, card in enumerate(cards):
                    if card is None or card == 'PASS':
                        continue
                    self.draw_card_with_shadow(card, pos[0] + j * 30, pos[1] + 50)

        # 4. 手牌（选中上浮效果）
        self.base_width = (self.width - len(self.my_handCards) * 30) // 2 - 50
        for i, card in enumerate(self.my_handCards):
            y_offset = -15 if i in self.selected_indices else 0
            x = self.base_width + i * 30
            y = self.height - 200
            self.draw_card_with_shadow(card, x, y, y_offset)

        # 5. 动态按钮
        self._draw_buttons()

        # 6. 临时提示消息
        if self.message_text and pygame.time.get_ticks() < self.message_until:
            msg_surf = self.font.render(self.message_text, True, self.message_color)
            msg_rect = msg_surf.get_rect(center=(self.width // 2, self.height - 300))
            # 半透明背景
            bg_rect = msg_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), bg_rect)
            self.screen.blit(msg_surf, msg_rect)
        else:
            self.message_text = None

        # 7. 进贡/抗贡动画（一次性绘制，立即清除标志）
        if self.tributeflag and self.tributeinfo:
            from_seat, to_seat, card = self.tributeinfo
            pos = self.get_screen_pos(to_seat)
            self.draw_card_with_shadow(card, pos[0], pos[1])
            self.tributeflag = 0
            pygame.display.flip()
            safe_wait(2)
        if self.backflag and self.backinfo:
            from_seat, to_seat, card = self.backinfo
            pos = self.get_screen_pos(to_seat)
            self.draw_card_with_shadow(card, pos[0], pos[1])
            self.backflag = 0
            pygame.display.flip()
            safe_wait(2)
        if self.antiflag:
            y = self.height // 2 - 50
            for pos in self.antiPosList:
                text = self.font.render(f"{pos} 号玩家抗贡", True, (0, 0, 0))
                self.screen.blit(text, (self.width // 2 - 50, y))
                y += 30
            self.antiflag = 0
            pygame.display.flip()
            safe_wait(3)

        pygame.display.flip()

    def _draw_buttons(self):
        """根据 legalActions 绘制出牌/PASS 按钮，并存储区域用于交互"""
        self.button_rects.clear()
        if not self.legalActions:
            return

        # 判断当前可用动作类型
        has_pass = any(act[0] == 'PASS' for act in self.legalActions)
        has_play = any(act[0] != 'PASS' for act in self.legalActions)

        # 按钮样式参数
        btn_width, btn_height = 100, 44
        btn_radius = 12

        if has_pass and not has_play:
            # 只有 PASS
            rect = pygame.Rect(self.width // 2 - btn_width // 2, self.height - 345, btn_width, btn_height)
            color = (70, 130, 70) if self.hover_button == 'pass' else (50, 100, 50)
            pygame.draw.rect(self.screen, color, rect, border_radius=btn_radius)
            text = self.font_button.render("PASS", True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=rect.center))
            self.button_rects['pass'] = rect

        elif has_play and not has_pass:
            # 只有出牌
            rect = pygame.Rect(self.width // 2 - btn_width // 2, self.height - 345, btn_width, btn_height)
            color = (70, 100, 200) if self.hover_button == 'play' else (50, 70, 160)
            pygame.draw.rect(self.screen, color, rect, border_radius=btn_radius)
            text = self.font_button.render("出牌", True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=rect.center))
            self.button_rects['play'] = rect

        else:
            # 两者都有
            # PASS 按钮（左侧）
            rect_pass = pygame.Rect(self.width // 3 - btn_width // 2, self.height - 345, btn_width, btn_height)
            color_pass = (70, 130, 70) if self.hover_button == 'pass' else (50, 100, 50)
            pygame.draw.rect(self.screen, color_pass, rect_pass, border_radius=btn_radius)
            text_pass = self.font_button.render("PASS", True, (255, 255, 255))
            self.screen.blit(text_pass, text_pass.get_rect(center=rect_pass.center))
            self.button_rects['pass'] = rect_pass

            # 出牌按钮（右侧）
            rect_play = pygame.Rect(self.width * 2 // 3 - btn_width // 2, self.height - 345, btn_width, btn_height)
            color_play = (70, 100, 200) if self.hover_button == 'play' else (50, 70, 160)
            pygame.draw.rect(self.screen, color_play, rect_play, border_radius=btn_radius)
            text_play = self.font_button.render("出牌", True, (255, 255, 255))
            self.screen.blit(text_play, text_play.get_rect(center=rect_play.center))
            self.button_rects['play'] = rect_play

    # ---------- 消息处理 ----------
    def initInfo(self, message):
        log.info(f"收到 beginning, 座位: {message['myPos']}")
        self.msgMyPos = message['myPos']
        if self.msgMyPos != self.myFixedSeat:
            log.warning(f"服务端座位 {self.msgMyPos} 与固定座位 {self.myFixedSeat} 不一致")
        self.my_handCards = message['handCards']
        self.playerRests = [27, 27, 27, 27]
        self.playerPlayAreas = [None, None, None, None]
        self.selected_indices.clear()
        self.draw_table()

    def handle_notify_play(self, message):
        curPos = message['curPos']
        curAction = message['curAction']

        if isinstance(curAction, str):
            try:
                curAction = ast.literal_eval(curAction)
            except:
                log.error(f"无法解析 curAction: {curAction}")
                return

        # PASS
        if curAction == 'PASS' or (isinstance(curAction, list) and curAction and curAction[0] == 'PASS'):
            self.playerPlayAreas[curPos] = None
            self.draw_table()
            return

        # 正常出牌
        if isinstance(curAction, list) and len(curAction) >= 3:
            cards = curAction[2]
        else:
            log.error(f"未知 curAction 格式: {curAction}")
            return

        if isinstance(cards, str):
            cards = [cards]

        if self.playerRests[curPos] >= len(cards):
            self.playerRests[curPos] -= len(cards)
        self.playerPlayAreas[curPos] = cards
        self.draw_table()

    def sync_from_act(self, message):
        self.stage = message['stage']
        self.my_handCards = message['handCards']
        self.curRank = message['curRank']
        self.selfRank = message['selfRank']
        self.oppRank = message['oppoRank']
        self.legalActions = message['actionList']

        # 构建 legalActions_set 用于快速匹配
        self.legalActions_set = []
        for act in self.legalActions:
            if act[0] == 'PASS':
                self.legalActions_set.append(None)
            else:
                cnt = defaultdict(int)
                for c in act[2]:
                    cnt[c] += 1
                self.legalActions_set.append(cnt)

        # 更新公共信息
        publicInfo = message['publicInfo']
        for i, info in enumerate(publicInfo):
            self.playerRests[i] = info['rest']
            play_area = info.get('playArea')
            # if play_area is not None:
            #     if isinstance(play_area, (list, tuple)) and len(play_area) >= 3:
            #         self.playerPlayAreas[i] = play_area[2]
            #     elif isinstance(play_area, dict) and 'cards' in play_area:
            #         self.playerPlayAreas[i] = play_area['cards']
            #     else:
            #         self.playerPlayAreas[i] = None
            # else:
            #     self.playerPlayAreas[i] = None

        self.selected_indices.clear()
        self.draw_table()

    def recordTribute(self, message):
        self.tributeflag = 1
        self.tributeinfo = message['result'][0]
        self.draw_table()  # 触发动画绘制

    def recordBack(self, message):
        self.backflag = 1
        self.backinfo = message['result'][0]
        self.draw_table()

    def recordAntiTribute(self, message):
        self.antiflag = 1
        self.antiPosList = message['antiPos']
        self.draw_table()

    def showOver(self, message):
        self.draw_table()
        order = message['order']
        curRank = message['curRank']
        self.screen.blit(self.font.render(f"完牌顺序 {order}", True, (0, 0, 0)),
                         (self.width // 2 - 50, self.height // 2 - 50))

        my_team = [self.myFixedSeat, (self.myFixedSeat + 2) % 4]
        opp_team = [(self.myFixedSeat + 1) % 4, (self.myFixedSeat + 3) % 4]
        my_best = min(order.index(p) for p in my_team)
        opp_best = min(order.index(p) for p in opp_team)

        if my_best < opp_best:
            opp_worst = max(order.index(p) for p in opp_team)
            level_up = 3 if opp_worst == 3 else (2 if opp_worst == 2 else 1)
            self.screen.blit(self.font.render(f"我方 将要升 {level_up} 级", True, (0, 0, 0)),
                             (self.width // 2 - 50, self.height // 2))
        else:
            my_worst = max(order.index(p) for p in my_team)
            level_up = 3 if my_worst == 3 else (2 if my_worst == 2 else 1)
            self.screen.blit(self.font.render(f"敌方 将要升 {level_up} 级", True, (0, 0, 0)),
                             (self.width // 2 - 50, self.height // 2))

        self.screen.blit(self.font.render(f"当前级数 {curRank}", True, (0, 0, 0)), (0, 0))
        self.screen.blit(self.font.render(f"我方级数 {self.selfRank}", True, (0, 0, 0)), (0, 20))
        self.screen.blit(self.font.render(f"敌方级数 {self.oppRank}", True, (0, 0, 0)), (0, 40))
        pygame.display.flip()
        safe_wait(5)

    def showGameOver(self, message):
        self.draw_table()
        text = f"游戏结束：第 {message['curTimes']} 次 / 共 {message['settingTimes']} 次"
        self.screen.blit(self.font.render(text, True, (0, 0, 0)),
                         (self.width // 2 - 150, self.height // 2))
        pygame.display.flip()
        safe_wait(5)

    def showGameResult(self, message):
        self.draw_table()
        victory = message['victoryNum']
        draws = message['draws']
        text = f"胜场: {victory}  平局: {draws}"
        self.screen.blit(self.font.render(text, True, (0, 0, 0)),
                         (self.width // 2 - 150, self.height // 2))
        pygame.display.flip()
        safe_wait(5)

    # ---------- 用户输入 ----------
    def waitInput(self):
        """等待玩家点击手牌或按钮，返回选择的动作索引"""
        # 贡/还贡阶段的简单选择（保持原有逻辑）
        if self.stage in ('tribute', 'back'):
            selected = None
            while selected is None:
                for event in pygame.event.get():
                    if event.type == QUIT:
                        exit()
                    if event.type == MOUSEBUTTONUP:
                        x, y = pygame.mouse.get_pos()
                        if self.height - 230 <= y <= self.height - 50:
                            idx = int((x - self.base_width) // 30)
                            if 0 <= idx < len(self.my_handCards):
                                card = self.my_handCards[idx]
                                for act_idx, act in enumerate(self.legalActions):
                                    if act[2][0] == card:
                                        selected = act_idx
                                        break
                pygame.display.update()
                pygame.time.wait(10)
            return selected

        # 正常出牌阶段
        self.selected_indices.clear()
        self.hover_button = None
        action_index = None

        while action_index is None:
            for event in pygame.event.get():
                if event.type == QUIT:
                    exit()
                if event.type == KEYDOWN and event.key == K_ESCAPE:
                    exit()

                # 鼠标移动：更新悬停按钮
                if event.type == MOUSEMOTION:
                    old_hover = self.hover_button
                    self.hover_button = None
                    for name, rect in self.button_rects.items():
                        if rect.collidepoint(event.pos):
                            self.hover_button = name
                            break
                    if old_hover != self.hover_button:
                        self.draw_table()  # 重绘改变按钮颜色

                # 鼠标点击
                if event.type == MOUSEBUTTONUP:
                    x, y = event.pos

                    # 1) 手牌区域点击（切换选中状态）
                    if self.height - 230 <= y <= self.height - 50:
                        idx = int((x - self.base_width) // 30)
                        if 0 <= idx < len(self.my_handCards):
                            if idx in self.selected_indices:
                                self.selected_indices.remove(idx)
                            else:
                                self.selected_indices.add(idx)
                            self.draw_table()
                            continue  # 不处理按钮

                    # 2) 按钮点击
                    for btn_name, rect in self.button_rects.items():
                        if rect.collidepoint(x, y):
                            if btn_name == 'pass':
                                # 查找 PASS 动作索引
                                for idx, act in enumerate(self.legalActions):
                                    if act[0] == 'PASS':
                                        action_index = idx
                                        break
                                if action_index is None:
                                    self.show_message("当前不能 PASS", (255, 100, 100))
                                    self.draw_table()
                            elif btn_name == 'play':
                                # 根据选中的牌构建组合
                                if not self.selected_indices:
                                    self.show_message("请先点击牌选中", (255, 200, 0))
                                    self.draw_table()
                                    continue
                                selected_cards = [self.my_handCards[i] for i in sorted(self.selected_indices)]
                                cnt = defaultdict(int)
                                for c in selected_cards:
                                    cnt[c] += 1
                                # 匹配 legalActions_set
                                matched = False
                                for idx, legal_cnt in enumerate(self.legalActions_set):
                                    if legal_cnt is not None and cnt == legal_cnt:
                                        action_index = idx
                                        matched = True
                                        break
                                if not matched:
                                    self.show_message("出牌组合不符合规则", (255, 100, 100))
                                    self.draw_table()
                                    continue
                            # 无论 pass 还是 play，找到动作后就退出循环
                            if action_index is not None:
                                break
                    # 如果已经拿到动作，退出事件循环
                    if action_index is not None:
                        break

            # 每帧重绘（保证动画流畅）
            self.draw_table()
            pygame.time.wait(10)

        # 清除选中状态，准备下一轮
        self.selected_indices.clear()
        return action_index


# ---------- 进程主函数 ----------
def run_one_player():
    try:
        log.info("===== 启动 Actor 进程 =====")
        board = Game()

        context = zmq.Context()
        socket = context.socket(zmq.REP)
        socket.bind('tcp://*:11003')
        socket.setsockopt(zmq.RCVTIMEO, 100)
        log.info("ZMQ 端口 11003 绑定成功")

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                    break
                if event.type == KEYDOWN and event.key == K_ESCAPE:
                    running = False
                    break

            if not running:
                break

            try:
                raw = socket.recv()
                message = deserialize(raw)
                log.debug(f"收到消息 type={message.get('type')}, stage={message.get('stage', 'N/A')}")

                if message['type'] == 'notify':
                    stage = message.get('stage')
                    if stage == 'beginning':
                        board.initInfo(message)
                    elif stage == 'play':
                        board.handle_notify_play(message)
                    elif stage == 'tribute':
                        board.recordTribute(message)
                    elif stage == 'back':
                        board.recordBack(message)
                    elif stage == 'anti-tribute':
                        board.recordAntiTribute(message)
                    elif stage == 'episodeOver':
                        board.showOver(message)
                    elif stage == 'gameOver':
                        board.showGameOver(message)
                    elif stage == 'gameResult':
                        board.showGameResult(message)
                    else:
                        log.warning(f"未知 stage: {stage}")
                    socket.send(serialize(-1).to_buffer())

                elif message['type'] == 'act':
                    board.sync_from_act(message)
                    action_index = board.waitInput()
                    log.info(f"玩家选择动作索引: {action_index}")
                    socket.send(serialize(action_index).to_buffer())
                else:
                    log.warning(f"未知消息类型: {message.get('type')}")
                    socket.send(serialize(-1).to_buffer())

            except zmq.error.Again:
                pass
            except zmq.error.ZMQError as e:
                log.error(f"ZMQ错误: {e}")
                running = False
                break
            except Exception as e:
                log.error(f"消息处理异常: {e}", exc_info=True)
                try:
                    socket.send(serialize(-1).to_buffer())
                except:
                    pass

        pygame.quit()
        context.term()
        log.info("Actor 正常退出")

    except Exception as e:
        log.error(f"run_one_player 致命错误: {e}", exc_info=True)
        with open("crash.log", "w", encoding="utf-8") as f:
            f.write(traceback.format_exc())
        raise


def main():
    players = []
    p = Process(target=run_one_player)
    p.start()
    players.append(p)

    try:
        for player in players:
            player.join()
    except KeyboardInterrupt:
        log.info("收到 Ctrl+C，终止所有进程...")
        for p in players:
            p.terminate()
        for p in players:
            p.join()
        log.info("所有进程已终止")


if __name__ == '__main__':
    freeze_support()
    main()