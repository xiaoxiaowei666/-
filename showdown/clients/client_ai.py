# client_ai.py
import json
import argparse
import os
import warnings
from functools import reduce

import numpy as np
import websocket

from util import card2num, card2array
from model import GDModel
import pickle

warnings.filterwarnings("ignore")
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

RANK = {
    '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8,
    'T': 9, 'J': 10, 'Q': 11, 'K': 12, 'A': 13
}

def _get_one_hot_array(num_left_cards, max_num_cards, flag):
    if flag == 0:
        one_hot = np.zeros(max_num_cards)
        one_hot[num_left_cards - 1] = 1
    else:
        one_hot = np.zeros(max_num_cards + 1)
        one_hot[num_left_cards] = 1
    return one_hot

class HardClient:
    def __init__(self, url, weights_path='dan.ckpt'):
        self.url = url
        self.ws = None

        # 加载模型
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = '3'
        import tensorflow as tf
        tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        from tensorflow.keras.backend import set_session
        set_session(tf.Session(config=config))

        self.model = GDModel(observation_space=(567,), action_space=(5, 216))
        with open(weights_path, 'rb') as f:
            new_weights = pickle.load(f)
        self.model.set_weights(new_weights)

        # 游戏状态
        self.mypos = 0
        self.history_action = {0: [], 1: [], 2: [], 3: []}
        self.action_seq = []
        self.action_order = []
        self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
        self.other_left_hands = [2 for _ in range(54)]
        self.flag = 0
        self.over = []
        self.tribute_result = None

    def on_open(self, ws):
        print("WebSocket connected (Hard AI)")

    def on_message(self, ws, message):
        try:
            msg = json.loads(message)
            print(msg)  # 调试输出，可按需关闭
            if msg['type'] == 'notify':
                self.handle_notify(msg)
            elif msg['type'] == 'act':
                self.handle_act(msg)
        except Exception as e:
            print(f"处理消息出错: {e}")
            import traceback
            traceback.print_exc()

    def on_error(self, ws, error):
        print("WebSocket error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket closed", close_status_code, close_msg)

    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

    # ---------- 以下方法保持不变 ----------
    def handle_notify(self, msg):
        stage = msg.get('stage')
        if stage == 'beginning':
            self.mypos = msg['myPos']
            print(f"AI 座位 {self.mypos} 开始游戏")
        elif stage == 'tribute':
            self.tribute_result = msg['result']
        elif stage == 'play':
            curPos = msg['curPos']
            cur_action = msg.get('curAction')
            if isinstance(cur_action, list) and len(cur_action) >= 3:
                action_cards = cur_action[2]
            else:
                action_cards = []
            if not isinstance(action_cards, list):
                action_cards = []
            action_nums = card2num(action_cards)

            if curPos != self.mypos:
                for ele in action_nums:
                    self.other_left_hands[ele] -= 1

            # 动作记录逻辑（保持原样）
            if len(self.over) == 0:
                self.action_order.append(curPos)
                self.action_seq.append(action_nums)
                self.history_action[curPos].append(action_nums)
            elif len(self.over) == 1:
                if len(action_nums) > 0 and self.flag == 1:
                    self.flag = 2
                    if curPos == (self.over[0] + 3) % 4:
                        self.action_order.append(curPos)
                        self.action_seq.append(action_nums)
                        self.history_action[curPos].append(action_nums)
                        self.action_order.append(self.over[0])
                        self.history_action[self.over[0]].append([-1])
                        self.action_seq.append([-1])
                    else:
                        self.action_order.append(curPos)
                        self.action_seq.append(action_nums)
                        self.history_action[curPos].append(action_nums)
                elif self.flag == 1 and (curPos + 1) % 4 == self.over[0]:
                    self.flag = 2
                    self.action_order.append(curPos)
                    self.action_seq.append(action_nums)
                    self.history_action[curPos].append(action_nums)
                    self.action_order.append(self.over[0])
                    self.history_action[self.over[0]].append([-1])
                    self.action_seq.append([-1])
                    self.action_order.append((curPos + 2) % 4)
                    self.history_action[(curPos + 2) % 4].append([])
                    self.action_seq.append([])
                elif curPos == (self.over[0] + 3) % 4 and self.flag == 2:
                    self.action_order.append(curPos)
                    self.action_seq.append(action_nums)
                    self.history_action[curPos].append(action_nums)
                    self.action_order.append(self.over[0])
                    self.history_action[self.over[0]].append([-1])
                    self.action_seq.append([-1])
                else:
                    self.action_order.append(curPos)
                    self.action_seq.append(action_nums)
                    self.history_action[curPos].append(action_nums)
            elif len(self.over) == 2:
                if len(action_nums) > 0 and self.flag <= 2:
                    if (curPos + 1) % 4 not in self.over:
                        self.flag = 3
                        self.action_order.append(curPos)
                        self.action_seq.append(action_nums)
                        self.history_action[curPos].append(action_nums)
                    else:
                        self.flag = 3
                        self.action_order.append(curPos)
                        self.action_seq.append(action_nums)
                        self.history_action[curPos].append(action_nums)
                        self.action_order.append((curPos + 1) % 4)
                        self.history_action[(curPos + 1) % 4].append([-1])
                        self.action_seq.append([-1])
                        self.action_order.append((curPos + 2) % 4)
                        self.history_action[(curPos + 2) % 4].append([-1])
                        self.action_seq.append([-1])
                elif self.flag <= 2 and (curPos + 1) % 4 in self.over:
                    self.flag = 3
                    self.action_order.append(curPos)
                    self.action_seq.append(action_nums)
                    self.history_action[curPos].append(action_nums)
                    self.action_order.append((curPos + 1) % 4)
                    self.history_action[(curPos + 1) % 4].append([-1])
                    self.action_seq.append([-1])
                    self.action_order.append((curPos + 2) % 4)
                    self.history_action[(curPos + 2) % 4].append([-1])
                    self.action_seq.append([-1])
                    if curPos == (self.over[-1] + 2) % 4:
                        self.action_order.append((curPos + 3) % 4)
                        self.history_action[(curPos + 3) % 4].append([])
                        self.action_seq.append([])
                elif (curPos + 1) % 4 in self.over and self.flag == 3:
                    self.action_order.append(curPos)
                    self.action_seq.append(action_nums)
                    self.history_action[curPos].append(action_nums)
                    self.action_order.append((curPos + 1) % 4)
                    self.history_action[(curPos + 1) % 4].append([-1])
                    self.action_seq.append([-1])
                    self.action_order.append((curPos + 2) % 4)
                    self.history_action[(curPos + 2) % 4].append([-1])
                    self.action_seq.append([-1])
                else:
                    self.action_order.append(curPos)
                    self.action_seq.append(action_nums)
                    self.history_action[curPos].append(action_nums)
            else:
                self.action_order.append(curPos)
                self.action_seq.append(action_nums)
                self.history_action[curPos].append(action_nums)

            self.remaining[curPos] -= len(action_nums)
            if self.remaining[curPos] == 0:
                self.over.append(curPos)
        elif stage == 'episodeOver':
            self.reset()

    def handle_act(self, msg):
        stage = msg.get('stage')
        if stage == 'tribute':
            act_index = self.tribute_decision(msg['actionList'], msg['curRank'])
            self.ws.send(json.dumps({"actIndex": act_index}))
        elif stage == 'back':
            act_index = self.back_decision(msg, self.tribute_result)
            self.ws.send(json.dumps({"actIndex": act_index}))
        elif stage == 'play':
            if len(msg['actionList']) == 1:
                self.ws.send(json.dumps({"actIndex": 0}))
                return
            if self.flag == 0:
                init_hand = card2num(msg['handCards'])
                for ele in init_hand:
                    self.other_left_hands[ele] -= 1
                self.flag = 1
            state = self.prepare(msg)
            output = self.model.forward(state['x_batch'])
            if output.ndim > 1:
                output = output.flatten()
            act_index = int(np.argmax(output))
            self.ws.send(json.dumps({"actIndex": act_index}))

    def prepare(self, message):
        """构建模型输入特征"""
        num_legal_actions = message['indexRange'] + 1
        legal_actions = [card2num(i[2]) for i in message['actionList']]
        my_handcards = card2array(card2num(message['handCards']))
        my_handcards_batch = np.repeat(my_handcards[np.newaxis, :],
                                       num_legal_actions, axis=0)

        universal_card_flag = self.proc_universal(my_handcards, RANK[message['curRank']])
        universal_card_flag_batch = np.repeat(universal_card_flag[np.newaxis, :],
                                              num_legal_actions, axis=0)

        other_hands = []
        for i in range(54):
            if self.other_left_hands[i] == 1:
                other_hands.append(i)
            elif self.other_left_hands[i] == 2:
                other_hands.append(i)
                other_hands.append(i)
        other_handcards = card2array(other_hands)
        other_handcards_batch = np.repeat(other_handcards[np.newaxis, :],
                                          num_legal_actions, axis=0)

        if len(self.action_seq) > 0:
            last_action = card2array(self.action_seq[-1])
        else:
            last_action = card2array([-1])
        last_action_batch = np.repeat(last_action[np.newaxis, :],
                                      num_legal_actions, axis=0)

        if len(self.history_action[(self.mypos + 2) % 4]) > 0 and (self.mypos + 2) % 4 not in self.over:
            last_teammate_action = card2array(self.history_action[(self.mypos + 2) % 4][-1])
        else:
            last_teammate_action = card2array([-1])
        last_teammate_action_batch = np.repeat(last_teammate_action[np.newaxis, :], num_legal_actions, axis=0)

        my_action_batch = np.zeros(my_handcards_batch.shape)
        for j, action in enumerate(legal_actions):
            my_action_batch[j, :] = card2array(action)

        down_num_cards_left = _get_one_hot_array(self.remaining[(self.mypos + 1) % 4], 27, 1)
        down_num_cards_left_batch = np.repeat(down_num_cards_left[np.newaxis, :], num_legal_actions, axis=0)
        teammate_num_cards_left = _get_one_hot_array(self.remaining[(self.mypos + 2) % 4], 27, 1)
        teammate_num_cards_left_batch = np.repeat(teammate_num_cards_left[np.newaxis, :], num_legal_actions, axis=0)
        up_num_cards_left = _get_one_hot_array(self.remaining[(self.mypos + 3) % 4], 27, 1)
        up_num_cards_left_batch = np.repeat(up_num_cards_left[np.newaxis, :], num_legal_actions, axis=0)

        if len(self.history_action[(self.mypos + 1) % 4]) > 0:
            down_played_cards = card2array(reduce(lambda x, y: x + y, self.history_action[(self.mypos + 1) % 4]))
        else:
            down_played_cards = card2array([])
        down_played_cards_batch = np.repeat(down_played_cards[np.newaxis, :], num_legal_actions, axis=0)

        if len(self.history_action[(self.mypos + 2) % 4]) > 0:
            teammate_played_cards = card2array(reduce(lambda x, y: x + y, self.history_action[(self.mypos + 2) % 4]))
        else:
            teammate_played_cards = card2array([])
        teammate_played_cards_batch = np.repeat(teammate_played_cards[np.newaxis, :], num_legal_actions, axis=0)

        if len(self.history_action[(self.mypos + 3) % 4]) > 0:
            up_played_cards = card2array(reduce(lambda x, y: x + y, self.history_action[(self.mypos + 3) % 4]))
        else:
            up_played_cards = card2array([])
        up_played_cards_batch = np.repeat(up_played_cards[np.newaxis, :], num_legal_actions, axis=0)

        self_rank = _get_one_hot_array(RANK[message['selfRank']], 13, 0)
        self_rank_batch = np.repeat(self_rank[np.newaxis, :], num_legal_actions, axis=0)
        oppo_rank = _get_one_hot_array(RANK[message['oppoRank']], 13, 0)
        oppo_rank_batch = np.repeat(oppo_rank[np.newaxis, :], num_legal_actions, axis=0)
        cur_rank = _get_one_hot_array(RANK[message['curRank']], 13, 0)
        cur_rank_batch = np.repeat(cur_rank[np.newaxis, :], num_legal_actions, axis=0)

        x_batch = np.hstack((my_handcards_batch,
                             universal_card_flag_batch,
                             other_handcards_batch,
                             last_action_batch,
                             last_teammate_action_batch,
                             down_played_cards_batch,
                             teammate_played_cards_batch,
                             up_played_cards_batch,
                             down_num_cards_left_batch,
                             teammate_num_cards_left_batch,
                             up_num_cards_left_batch,
                             self_rank_batch,
                             oppo_rank_batch,
                             cur_rank_batch,
                             my_action_batch))

        x_no_action = np.hstack((my_handcards,
                                 universal_card_flag,
                                 other_handcards,
                                 last_action,
                                 last_teammate_action,
                                 down_played_cards,
                                 teammate_played_cards,
                                 up_played_cards,
                                 down_num_cards_left,
                                 teammate_num_cards_left,
                                 up_num_cards_left,
                                 self_rank,
                                 oppo_rank,
                                 cur_rank))

        return {
            'x_batch': x_batch.astype(np.float32),
            'legal_actions': legal_actions,
            'x_no_action': x_no_action.astype(np.float32),
        }

    def proc_universal(self, handCards, cur_rank):
        """万能牌标志位"""
        res = np.zeros(12, dtype=np.int8)
        if handCards[(cur_rank - 1) * 4] == 0:
            return res
        res[0] = 1
        rock_flag = 0
        for i in range(4):
            left, right = 0, 5
            temp = [handCards[i + j * 4] if i + j * 4 != (cur_rank - 1) * 4 else 0 for j in range(5)]
            while right <= 12:
                zero_num = temp.count(0)
                if zero_num <= 1:
                    rock_flag = 1
                    break
                else:
                    temp.append(handCards[i + right * 4] if i + right * 4 != (cur_rank - 1) * 4 else 0)
                    temp.pop(0)
                    left += 1
                    right += 1
            if rock_flag == 1:
                break
        res[1] = rock_flag

        num_count = [0] * 13
        for i in range(4):
            for j in range(13):
                if handCards[i + j * 4] != 0 and i + j * 4 != (cur_rank - 1) * 4:
                    num_count[j] += 1
        num_max = max(num_count)
        if num_max >= 6:
            res[2:8] = 1
        elif num_max == 5:
            res[3:8] = 1
        elif num_max == 4:
            res[4:8] = 1
        elif num_max == 3:
            res[5:8] = 1
        elif num_max == 2:
            res[6:8] = 1
        else:
            res[7] = 1
        temp = 0
        for i in range(13):
            if num_count[i] != 0:
                temp += 1
                if i >= 1:
                    if num_count[i] == 2 and num_count[i - 1] >= 3 or num_count[i] >= 3 and num_count[i - 1] == 2:
                        res[9] = 1
                    elif num_count[i] == 2 and num_count[i - 1] == 2:
                        res[11] = 1
                if i >= 2:
                    if num_count[i - 2] == 1 and num_count[i - 1] >= 2 and num_count[i] >= 2 or \
                            num_count[i - 2] >= 2 and num_count[i - 1] == 1 and num_count[i] >= 2 or \
                            num_count[i - 2] >= 2 and num_count[i - 1] >= 2 and num_count[i] == 1:
                        res[10] = 1
            else:
                temp = 0
        if temp >= 4:
            res[8] = 1
        return res

    def tribute_decision(self, actionList, curRank):
        rank_card = 'H' + curRank
        first_action = actionList[0]
        return 1 if rank_card in first_action[2] else 0

    def back_decision(self, msg, tribute_result):
        # 简化：返回第一个合法动作
        return 0

    def reset(self):
        self.history_action = {0: [], 1: [], 2: [], 3: []}
        self.action_seq = []
        self.other_left_hands = [2 for _ in range(54)]
        self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
        self.over = []
        self.flag = 0


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--seat', type=int, required=True, help='座位号 (0-3)')
    parser.add_argument('--server_url', type=str, default='ws://127.0.0.1:23456/game/client',
                        help='服务器基础URL')
    parser.add_argument('--weights', type=str, default='dan.ckpt', help='模型权重路径')
    args = parser.parse_args()

    full_url = f"{args.server_url}{args.seat}"
    client = HardClient(full_url, weights_path=args.weights)
    client.connect()