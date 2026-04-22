# import json
# import argparse
# import threading
# import pygame
# import websocket
# from pygame.locals import *
# from collections import defaultdict   # 新增导入
# from showdown_actor import Game
#
# class PlayerGame(Game):
#     def __init__(self, seat, server_url):
#         super().__init__()
#         self.seat = seat
#         self.server_url = server_url
#         self.ws = None
#         self.myFixedSeat = None   # 实际座位由服务器通知
#         self.running = True
#
#     def on_message(self, ws, message):
#         if not self.running:
#             return
#         try:
#             msg = json.loads(message)
#             if msg['type'] == 'notify':
#                 self.handle_notify(msg)
#             elif msg['type'] == 'act':
#                 self.handle_act(msg)
#         except Exception as e:
#             print(f"处理消息出错: {e}")
#
#     def handle_notify(self, msg):
#         stage = msg.get('stage')
#         if stage == 'beginning':
#             self.myFixedSeat = msg['myPos']
#             # 删除错误的 super().myFixedSeat = ...
#             self.initInfo(msg)
#             print(f"玩家实际座位: {self.myFixedSeat}")
#         elif stage == 'play':
#             self.handle_notify_play(msg)
#         elif stage == 'tribute':
#             self.recordTribute(msg)
#         elif stage == 'back':
#             self.recordBack(msg)
#         elif stage == 'anti-tribute':
#             self.recordAntiTribute(msg)
#         elif stage == 'episodeOver':
#             self.showOver(msg)
#         elif stage == 'gameOver':
#             self.showGameOver(msg)
#         elif stage == 'gameResult':
#             self.showGameResult(msg)
#
#     def handle_act(self, msg):
#         if not self.running:
#             return
#         self.sync_from_act(msg)
#         action_index = self.waitInput()
#         if self.running:
#             self.ws.send(json.dumps({"actIndex": action_index}))
#
#     def draw_table(self):
#         """重写父类 draw_table，移除动画等待和额外 flip，避免闪烁"""
#         self.screen.blit(self.bg_scaled, (0, 0))
#         self.screen.blit(self.partback_scaled, (0, self.height * 2 // 3))
#
#         self.screen.blit(self.font.render(f"当前级数 {self.curRank}", True, (0, 0, 0)), (0, 0))
#         self.screen.blit(self.font.render(f"我方级数 {self.selfRank}", True, (0, 0, 0)), (0, 20))
#         self.screen.blit(self.font.render(f"敌方级数 {self.oppRank}", True, (0, 0, 0)), (0, 40))
#
#         for seat in range(4):
#             pos = self.get_screen_pos(seat)
#             text_pos = self.get_text_pos(seat)
#
#             rest_surf = self.font.render(f"{self.playerRests[seat]}张", True, (0, 0, 0))
#             self.screen.blit(rest_surf, text_pos)
#
#             if seat != self.myFixedSeat:
#                 self.screen.blit(self.cardbackImage, pos)
#
#             cards = self.playerPlayAreas[seat]
#             if cards and isinstance(cards, list):
#                 for j, card in enumerate(cards):
#                     if card is None or card == 'PASS':
#                         continue
#                     self.draw_card_with_shadow(card, pos[0] + j * 30, pos[1] + 50)
#
#         self.base_width = (self.width - len(self.my_handCards) * 30) // 2 - 50
#         for i, card in enumerate(self.my_handCards):
#             y_offset = -15 if i in self.selected_indices else 0
#             x = self.base_width + i * 30
#             y = self.height - 200
#             self.draw_card_with_shadow(card, x, y, y_offset)
#
#             if self.stage in ('tribute', 'back') and self.highlight_cards and card in self.highlight_cards:
#                 img = self.get_card_image(card)
#                 if img:
#                     rect = pygame.Rect(x, y + y_offset, img.get_width(), img.get_height())
#                     pygame.draw.rect(self.screen, (255, 215, 0), rect, 4)
#                     glow_rect = rect.inflate(8, 8)
#                     pygame.draw.rect(self.screen, (255, 215, 0, 100), glow_rect, 2)
#
#         self._draw_buttons()
#
#         if self.message_text and pygame.time.get_ticks() < self.message_until:
#             msg_surf = self.font.render(self.message_text, True, self.message_color)
#             msg_rect = msg_surf.get_rect(center=(self.width // 2, self.height - 300))
#             bg_rect = msg_rect.inflate(20, 10)
#             pygame.draw.rect(self.screen, (0, 0, 0, 180), bg_rect)
#             self.screen.blit(msg_surf, msg_rect)
#         else:
#             self.message_text = None
#
#         pygame.display.flip()
#
#     def waitInput(self):
#         """覆盖父类 waitInput，使用 self.running 控制退出"""
#         if self.stage in ('tribute', 'back'):
#             allowed_cards = set()
#             card_to_action = {}
#             for act_idx, act in enumerate(self.legalActions):
#                 if act[0] != 'PASS':
#                     card_info = act[2]
#                     if isinstance(card_info, list) and len(card_info) > 0:
#                         card = card_info[0]
#                     elif isinstance(card_info, str):
#                         card = card_info
#                     else:
#                         continue
#                     allowed_cards.add(card)
#                     card_to_action[card] = act_idx
#             self.highlight_cards = allowed_cards
#
#             selected_action = None
#             while selected_action is None and self.running:
#                 for event in pygame.event.get():
#                     if event.type == QUIT:
#                         self.running = False
#                         return 0
#                     if event.type == MOUSEBUTTONUP:
#                         x, y = event.pos
#                         if self.height - 230 <= y <= self.height - 50:
#                             idx = int((x - self.base_width) // 30)
#                             if 0 <= idx < len(self.my_handCards):
#                                 card = self.my_handCards[idx]
#                                 if card in allowed_cards:
#                                     selected_action = card_to_action[card]
#                                 else:
#                                     self.show_message("只能选择高亮的牌进行进贡/还贡", (255, 100, 100))
#                                     self.draw_table()
#                 self.draw_table()
#                 pygame.time.wait(10)
#             self.highlight_cards = None
#             return selected_action if selected_action is not None else 0
#
#         # 正常出牌阶段
#         self.selected_indices.clear()
#         self.hover_button = None
#         action_index = None
#
#         while action_index is None and self.running:
#             for event in pygame.event.get():
#                 if event.type == QUIT:
#                     self.running = False
#                     return 0
#                 if event.type == KEYDOWN and event.key == K_ESCAPE:
#                     self.running = False
#                     return 0
#
#                 if event.type == MOUSEMOTION:
#                     old_hover = self.hover_button
#                     self.hover_button = None
#                     for name, rect in self.button_rects.items():
#                         if rect.collidepoint(event.pos):
#                             self.hover_button = name
#                             break
#                     if old_hover != self.hover_button:
#                         self.draw_table()
#
#                 if event.type == MOUSEBUTTONUP:
#                     x, y = event.pos
#                     if self.height - 230 <= y <= self.height - 50:
#                         idx = int((x - self.base_width) // 30)
#                         if 0 <= idx < len(self.my_handCards):
#                             if idx in self.selected_indices:
#                                 self.selected_indices.remove(idx)
#                             else:
#                                 self.selected_indices.add(idx)
#                             self.draw_table()
#                             continue
#                     for btn_name, rect in self.button_rects.items():
#                         if rect.collidepoint(x, y):
#                             if btn_name == 'pass':
#                                 for idx, act in enumerate(self.legalActions):
#                                     if act[0] == 'PASS':
#                                         action_index = idx
#                                         break
#                                 if action_index is None:
#                                     self.show_message("当前不能 PASS", (255, 100, 100))
#                                     self.draw_table()
#                             elif btn_name == 'play':
#                                 if not self.selected_indices:
#                                     self.show_message("请先点击牌选中", (255, 200, 0))
#                                     self.draw_table()
#                                     continue
#                                 selected_cards = [self.my_handCards[i] for i in sorted(self.selected_indices)]
#                                 cnt = defaultdict(int)
#                                 for c in selected_cards:
#                                     cnt[c] += 1
#                                 matched = False
#                                 for idx, legal_cnt in enumerate(self.legalActions_set):
#                                     if legal_cnt is not None and cnt == legal_cnt:
#                                         action_index = idx
#                                         matched = True
#                                         break
#                                 if not matched:
#                                     self.show_message("出牌组合不符合规则", (255, 100, 100))
#                                     self.draw_table()
#                                     continue
#                             if action_index is not None:
#                                 break
#                     if action_index is not None:
#                         break
#
#             self.draw_table()
#             pygame.time.wait(10)
#
#         self.selected_indices.clear()
#         return action_index if action_index is not None else 0
#
#     def recordTribute(self, message):
#         self.tributeflag = 1
#         self.tributeinfo = message['result'][0]
#         self._play_animation()
#
#     def recordBack(self, message):
#         self.backflag = 1
#         self.backinfo = message['result'][0]
#         self._play_animation()
#
#     def recordAntiTribute(self, message):
#         self.antiflag = 1
#         self.antiPosList = message['antiPos']
#         self._play_animation()
#
#     def _play_animation(self):
#         self.draw_table()
#         pygame.display.flip()
#
#         if self.tributeflag and self.tributeinfo:
#             from_seat, to_seat, card = self.tributeinfo
#             pos = self.get_screen_pos(to_seat)
#             self.draw_card_with_shadow(card, pos[0], pos[1])
#             self.tributeflag = 0
#             pygame.display.flip()
#             self._safe_wait(2)
#         if self.backflag and self.backinfo:
#             from_seat, to_seat, card = self.backinfo
#             pos = self.get_screen_pos(to_seat)
#             self.draw_card_with_shadow(card, pos[0], pos[1])
#             self.backflag = 0
#             pygame.display.flip()
#             self._safe_wait(2)
#         if self.antiflag:
#             y = self.height // 2 - 50
#             for pos in self.antiPosList:
#                 text = self.font.render(f"{pos} 号玩家抗贡", True, (0, 0, 0))
#                 self.screen.blit(text, (self.width // 2 - 50, y))
#                 y += 30
#             self.antiflag = 0
#             pygame.display.flip()
#             self._safe_wait(3)
#
#     def _safe_wait(self, seconds):
#         start = pygame.time.get_ticks()
#         while pygame.time.get_ticks() - start < seconds * 1000:
#             for event in pygame.event.get():
#                 if event.type == QUIT:
#                     self.running = False
#                     return
#             pygame.event.pump()
#             pygame.time.wait(10)
#
#     # def run(self):
#     #     self.ws = websocket.WebSocketApp(
#     #         self.server_url,
#     #         on_open=lambda ws: print("Connected to server"),
#     #         on_message=self.on_message,
#     #         on_error=lambda ws, err: print(f"Error: {err}"),
#     #         on_close=lambda ws, a, b: print("Disconnected")
#     #     )
#     #     threading.Thread(target=self.ws.run_forever, daemon=True).start()
#     #
#     #     clock = pygame.time.Clock()
#     #     while self.running:
#     #         for event in pygame.event.get():
#     #             if event.type == QUIT:
#     #                 self.running = False
#     #                 self.ws.close()
#     #         clock.tick(30)
#     #     pygame.quit()
#     def run(self):
#         self.ws = websocket.WebSocketApp(
#             self.server_url,
#             on_open=lambda ws: print("Connected to server"),
#             on_message=self.on_message,
#             on_error=lambda ws, err: print(f"Error: {err}"),
#             on_close=lambda ws, a, b: print("Disconnected")
#         )
#         threading.Thread(target=self.ws.run_forever, daemon=True).start()
#
#         clock = pygame.time.Clock()
#         while self.running:
#             # 关键：不要调用 pygame.event.get()，改为 pump() 保持窗口响应
#             pygame.event.pump()
#             clock.tick(30)
#         pygame.quit()
#
# if __name__ == '__main__':
#     parser = argparse.ArgumentParser()
#     parser.add_argument('--seat', type=int, default=3)
#     parser.add_argument('--server_url', type=str, default='ws://127.0.0.1:23456/game/client')
#     args = parser.parse_args()
#     url = f"{args.server_url}{args.seat}"
#     game = PlayerGame(args.seat, url)
#     game.run()
import json
import argparse
import threading
import pygame
import websocket
from pygame.locals import *
from collections import defaultdict
from showdown_actor import Game

class PlayerGame(Game):
    def __init__(self, seat, server_url):
        super().__init__()
        self.seat = seat
        self.server_url = server_url
        self.ws = None
        self.myFixedSeat = None   # 实际座位由服务器通知
        self.running = True
        self.hint_index = 0       # 提示动作索引

    def on_message(self, ws, message):
        if not self.running:
            return
        try:
            msg = json.loads(message)
            if msg['type'] == 'notify':
                self.handle_notify(msg)
            elif msg['type'] == 'act':
                self.handle_act(msg)
        except Exception as e:
            print(f"处理消息出错: {e}")

    def handle_notify(self, msg):
        stage = msg.get('stage')
        if stage == 'beginning':
            self.myFixedSeat = msg['myPos']
            self.initInfo(msg)
            print(f"玩家实际座位: {self.myFixedSeat}")
        elif stage == 'play':
            self.handle_notify_play(msg)
        elif stage == 'tribute':
            self.recordTribute(msg)
        elif stage == 'back':
            self.recordBack(msg)
        elif stage == 'anti-tribute':
            self.recordAntiTribute(msg)
        elif stage == 'episodeOver':
            self.showOver(msg)
        elif stage == 'gameOver':
            self.showGameOver(msg)
        elif stage == 'gameResult':
            self.showGameResult(msg)

    def handle_act(self, msg):
        if not self.running:
            return
        self.sync_from_act(msg)
        action_index = self.waitInput()
        if self.running:
            self.ws.send(json.dumps({"actIndex": action_index}))

    def draw_table(self):
        """重写父类 draw_table，移除动画等待和额外 flip，避免闪烁"""
        self.screen.blit(self.bg_scaled, (0, 0))
        self.screen.blit(self.partback_scaled, (0, self.height * 2 // 3))

        self.screen.blit(self.font.render(f"当前级数 {self.curRank}", True, (0, 0, 0)), (0, 0))
        self.screen.blit(self.font.render(f"我方级数 {self.selfRank}", True, (0, 0, 0)), (0, 20))
        self.screen.blit(self.font.render(f"敌方级数 {self.oppRank}", True, (0, 0, 0)), (0, 40))

        for seat in range(4):
            pos = self.get_screen_pos(seat)
            text_pos = self.get_text_pos(seat)

            rest_surf = self.font.render(f"{self.playerRests[seat]}张", True, (0, 0, 0))
            self.screen.blit(rest_surf, text_pos)

            if seat != self.myFixedSeat:
                self.screen.blit(self.cardbackImage, pos)

            cards = self.playerPlayAreas[seat]
            if cards and isinstance(cards, list):
                for j, card in enumerate(cards):
                    if card is None or card == 'PASS':
                        continue
                    self.draw_card_with_shadow(card, pos[0] + j * 30, pos[1] + 50)

        self.base_width = (self.width - len(self.my_handCards) * 30) // 2 - 50
        for i, card in enumerate(self.my_handCards):
            y_offset = -15 if i in self.selected_indices else 0
            x = self.base_width + i * 30
            y = self.height - 200
            self.draw_card_with_shadow(card, x, y, y_offset)

            if self.stage in ('tribute', 'back') and self.highlight_cards and card in self.highlight_cards:
                img = self.get_card_image(card)
                if img:
                    rect = pygame.Rect(x, y + y_offset, img.get_width(), img.get_height())
                    pygame.draw.rect(self.screen, (255, 215, 0), rect, 4)
                    glow_rect = rect.inflate(8, 8)
                    pygame.draw.rect(self.screen, (255, 215, 0, 100), glow_rect, 2)

        self._draw_buttons()

        if self.message_text and pygame.time.get_ticks() < self.message_until:
            msg_surf = self.font.render(self.message_text, True, self.message_color)
            msg_rect = msg_surf.get_rect(center=(self.width // 2, self.height - 300))
            bg_rect = msg_rect.inflate(20, 10)
            pygame.draw.rect(self.screen, (0, 0, 0, 180), bg_rect)
            self.screen.blit(msg_surf, msg_rect)
        else:
            self.message_text = None

        pygame.display.flip()

    def _draw_buttons(self):
        """根据 legalActions 绘制出牌/PASS/提示按钮，并存储区域用于交互"""
        # 贡/还贡阶段不需要按钮
        if self.stage in ('tribute', 'back'):
            return

        self.button_rects.clear()
        if not self.legalActions:
            return

        # 判断当前可用动作类型
        has_pass = any(act[0] == 'PASS' for act in self.legalActions)
        has_play = any(act[0] != 'PASS' for act in self.legalActions)

        # 按钮样式参数
        btn_width, btn_height = 100, 44
        btn_radius = 12
        btn_y = self.height - 260  # 下移，避免遮挡手牌

        # 根据可用动作绘制按钮
        if has_pass and not has_play:
            # 只有 PASS，居中显示
            rect = pygame.Rect(self.width // 2 - btn_width // 2, btn_y, btn_width, btn_height)
            color = (70, 130, 70) if self.hover_button == 'pass' else (50, 100, 50)
            pygame.draw.rect(self.screen, color, rect, border_radius=btn_radius)
            text = self.font_button.render("PASS", True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=rect.center))
            self.button_rects['pass'] = rect

        elif has_play and not has_pass:
            # 只有出牌，居中显示
            rect = pygame.Rect(self.width // 2 - btn_width // 2, btn_y, btn_width, btn_height)
            color = (70, 100, 200) if self.hover_button == 'play' else (50, 70, 160)
            pygame.draw.rect(self.screen, color, rect, border_radius=btn_radius)
            text = self.font_button.render("出牌", True, (255, 255, 255))
            self.screen.blit(text, text.get_rect(center=rect.center))
            self.button_rects['play'] = rect

        else:
            # 两者都有：PASS 在左，提示居中，出牌在右
            # 计算各按钮的 X 坐标（紧凑排列）
            pass_x = self.width * 3 // 8 - btn_width // 2
            hint_x = self.width // 2 - btn_width // 2
            play_x = self.width * 5 // 8 - btn_width // 2

            # 提示按钮（居中）
            hint_rect = pygame.Rect(hint_x, btn_y, btn_width, btn_height)
            hint_color = (200, 120, 50) if self.hover_button == 'hint' else (180, 100, 30)
            pygame.draw.rect(self.screen, hint_color, hint_rect, border_radius=btn_radius)
            hint_text = self.font_button.render("提示", True, (255, 255, 255))
            self.screen.blit(hint_text, hint_text.get_rect(center=hint_rect.center))
            self.button_rects['hint'] = hint_rect

            # PASS 按钮（左侧）
            if has_pass:
                pass_rect = pygame.Rect(pass_x, btn_y, btn_width, btn_height)
                color_pass = (70, 130, 70) if self.hover_button == 'pass' else (50, 100, 50)
                pygame.draw.rect(self.screen, color_pass, pass_rect, border_radius=btn_radius)
                text_pass = self.font_button.render("PASS", True, (255, 255, 255))
                self.screen.blit(text_pass, text_pass.get_rect(center=pass_rect.center))
                self.button_rects['pass'] = pass_rect

            # 出牌按钮（右侧）
            if has_play:
                play_rect = pygame.Rect(play_x, btn_y, btn_width, btn_height)
                color_play = (70, 100, 200) if self.hover_button == 'play' else (50, 70, 160)
                pygame.draw.rect(self.screen, color_play, play_rect, border_radius=btn_radius)
                text_play = self.font_button.render("出牌", True, (255, 255, 255))
                self.screen.blit(text_play, text_play.get_rect(center=play_rect.center))
                self.button_rects['play'] = play_rect

    def _handle_hint(self):
        """处理提示按钮：循环选中下一个合法出牌组合"""
        # 过滤出非 PASS 动作
        play_actions = [act for act in self.legalActions if act[0] != 'PASS']
        if not play_actions:
            self.show_message("没有可出的牌，请 PASS", (200, 200, 0))
            return

        # 清空当前选中
        self.selected_indices.clear()

        # 获取当前提示索引对应的动作
        idx = self.hint_index % len(play_actions)
        action = play_actions[idx]

        # 提取动作中的牌
        cards = action[2]
        if isinstance(cards, str):
            cards = [cards]

        # 在手牌中按顺序匹配（处理重复牌）
        hand_cards = self.my_handCards[:]
        for card in cards:
            try:
                pos = hand_cards.index(card)
                self.selected_indices.add(pos)
                hand_cards[pos] = None  # 标记已使用
            except ValueError:
                pass  # 理论上不会出现

        self.draw_table()
        # 索引递增，下次点击切换下一个组合
        self.hint_index = (self.hint_index + 1) % len(play_actions)

    def waitInput(self):
        """覆盖父类 waitInput，使用 self.running 控制退出，并加入提示功能"""
        # 贡/还贡阶段特殊处理
        if self.stage in ('tribute', 'back'):
            allowed_cards = set()
            card_to_action = {}
            for act_idx, act in enumerate(self.legalActions):
                if act[0] != 'PASS':
                    card_info = act[2]
                    if isinstance(card_info, list) and len(card_info) > 0:
                        card = card_info[0]
                    elif isinstance(card_info, str):
                        card = card_info
                    else:
                        continue
                    allowed_cards.add(card)
                    card_to_action[card] = act_idx
            self.highlight_cards = allowed_cards

            selected_action = None
            while selected_action is None and self.running:
                for event in pygame.event.get():
                    if event.type == QUIT:
                        self.running = False
                        return 0
                    if event.type == MOUSEBUTTONUP:
                        x, y = event.pos
                        if self.height - 230 <= y <= self.height - 50:
                            idx = int((x - self.base_width) // 30)
                            if 0 <= idx < len(self.my_handCards):
                                card = self.my_handCards[idx]
                                if card in allowed_cards:
                                    selected_action = card_to_action[card]
                                else:
                                    self.show_message("只能选择高亮的牌进行进贡/还贡", (255, 100, 100))
                                    self.draw_table()
                self.draw_table()
                pygame.time.wait(10)
            self.highlight_cards = None
            return selected_action if selected_action is not None else 0

        # 正常出牌阶段
        self.hint_index = 0           # 重置提示索引
        self.selected_indices.clear()
        self.hover_button = None
        action_index = None

        while action_index is None and self.running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    self.running = False
                    return 0
                if event.type == KEYDOWN and event.key == K_ESCAPE:
                    self.running = False
                    return 0

                if event.type == MOUSEMOTION:
                    old_hover = self.hover_button
                    self.hover_button = None
                    for name, rect in self.button_rects.items():
                        if rect.collidepoint(event.pos):
                            self.hover_button = name
                            break
                    if old_hover != self.hover_button:
                        self.draw_table()

                if event.type == MOUSEBUTTONUP:
                    x, y = event.pos
                    if self.height - 230 <= y <= self.height - 50:
                        idx = int((x - self.base_width) // 30)
                        if 0 <= idx < len(self.my_handCards):
                            if idx in self.selected_indices:
                                self.selected_indices.remove(idx)
                            else:
                                self.selected_indices.add(idx)
                            self.draw_table()
                            continue

                    for btn_name, rect in self.button_rects.items():
                        if rect.collidepoint(x, y):
                            if btn_name == 'hint':
                                self._handle_hint()
                                break
                            elif btn_name == 'pass':
                                for idx, act in enumerate(self.legalActions):
                                    if act[0] == 'PASS':
                                        action_index = idx
                                        break
                                if action_index is None:
                                    self.show_message("当前不能 PASS", (255, 100, 100))
                                    self.draw_table()
                            elif btn_name == 'play':
                                if not self.selected_indices:
                                    self.show_message("请先点击牌选中", (255, 200, 0))
                                    self.draw_table()
                                    continue
                                selected_cards = [self.my_handCards[i] for i in sorted(self.selected_indices)]
                                cnt = defaultdict(int)
                                for c in selected_cards:
                                    cnt[c] += 1
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
                            if action_index is not None:
                                break
                    if action_index is not None:
                        break

            self.draw_table()
            pygame.time.wait(10)

        self.selected_indices.clear()
        return action_index if action_index is not None else 0

    def recordTribute(self, message):
        self.tributeflag = 1
        self.tributeinfo = message['result'][0]
        self._play_animation()

    def recordBack(self, message):
        self.backflag = 1
        self.backinfo = message['result'][0]
        self._play_animation()

    def recordAntiTribute(self, message):
        self.antiflag = 1
        self.antiPosList = message['antiPos']
        self._play_animation()

    def _play_animation(self):
        self.draw_table()
        pygame.display.flip()

        if self.tributeflag and self.tributeinfo:
            from_seat, to_seat, card = self.tributeinfo
            pos = self.get_screen_pos(to_seat)
            self.draw_card_with_shadow(card, pos[0], pos[1])
            self.tributeflag = 0
            pygame.display.flip()
            self._safe_wait(2)
        if self.backflag and self.backinfo:
            from_seat, to_seat, card = self.backinfo
            pos = self.get_screen_pos(to_seat)
            self.draw_card_with_shadow(card, pos[0], pos[1])
            self.backflag = 0
            pygame.display.flip()
            self._safe_wait(2)
        if self.antiflag:
            y = self.height // 2 - 50
            for pos in self.antiPosList:
                text = self.font.render(f"{pos} 号玩家抗贡", True, (0, 0, 0))
                self.screen.blit(text, (self.width // 2 - 50, y))
                y += 30
            self.antiflag = 0
            pygame.display.flip()
            self._safe_wait(3)

    def _safe_wait(self, seconds):
        start = pygame.time.get_ticks()
        while pygame.time.get_ticks() - start < seconds * 1000:
            for event in pygame.event.get():
                if event.type == QUIT:
                    self.running = False
                    return
            pygame.event.pump()
            pygame.time.wait(10)

    def run(self):
        self.ws = websocket.WebSocketApp(
            self.server_url,
            on_open=lambda ws: print("Connected to server"),
            on_message=self.on_message,
            on_error=lambda ws, err: print(f"Error: {err}"),
            on_close=lambda ws, a, b: print("Disconnected")
        )
        threading.Thread(target=self.ws.run_forever, daemon=True).start()

        clock = pygame.time.Clock()
        while self.running:
            pygame.event.pump()
            clock.tick(30)
        pygame.quit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seat', type=int, default=3)
    parser.add_argument('--server_url', type=str, default='ws://127.0.0.1:23456/game/client')
    args = parser.parse_args()
    url = f"{args.server_url}{args.seat}"
    game = PlayerGame(args.seat, url)
    game.run()