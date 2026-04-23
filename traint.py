import os
import json
import time
import warnings
import random
import sys
import subprocess
from argparse import ArgumentParser
from functools import reduce
from multiprocessing import Process
from random import randint

import zmq
import websocket
from pyarrow import deserialize, serialize

from utils.utils import *

warnings.filterwarnings("ignore")
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
parser = ArgumentParser()
parser.add_argument('--ip', type=str, default='127.0.0.1',
                    help='IP address of learner server')
parser.add_argument('--action_port', type=int, default=6000,
                    help='Learner server port to send training data')

RANK = {
    '2': 1, '3': 2, '4': 3, '5': 4, '6': 5, '7': 6, '8': 7, '9': 8,
    'T': 9, 'J': 10, 'Q': 11, 'K': 12, 'A': 13
}


def _get_one_hot_array(num_left_cards, max_num_cards, flag):
    if flag == 0:     # 级数的情况
        one_hot = np.zeros(max_num_cards)
        one_hot[num_left_cards - 1] = 1
    else:
        one_hot = np.zeros(max_num_cards + 1)    # 剩余的牌（0-1阵格式）
        one_hot[num_left_cards] = 1
    return one_hot


def _action_seq_list2array(action_seq_list):
    action_seq_array = np.zeros((len(action_seq_list), 54))
    for row, list_cards in enumerate(action_seq_list):
        action_seq_array[row, :] = card2array(list_cards)
    action_seq_array = action_seq_array.reshape(5, 216)
    return action_seq_array


def _process_action_seq(sequence, length=20):
    sequence = sequence[-length:].copy()
    if len(sequence) < length:
        empty_sequence = [[] for _ in range(length - len(sequence))]
        empty_sequence.extend(sequence)
        sequence = empty_sequence
    return sequence


class MyClient:
    def __init__(self, url, args):
        self.url = url
        self.args = args
        self.ws = None
        self.mypos = 0
        self.history_action = {0: [], 1: [], 2: [], 3: []}
        self.action_seq = []
        self.action_order = []  # 记录出牌顺序(4个智能体是一样的)
        self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
        self.other_left_hands = [2 for _ in range(54)]
        self.flag = 0
        self.over = []

        # 初始化zmq
        self.context = zmq.Context()
        self.context.linger = 0
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f'tcp://localhost:{6000 + args.client_index}')

    def on_open(self, ws):
        """WebSocket连接打开时的回调"""
        pass

    def on_message(self, ws, message):
        """收到消息时的回调"""
        message = json.loads(str(message))
        print(message)
        # 将原 self.send 调用替换为 ws.send
        if message['type'] == 'notify':
            if message['stage'] == 'beginning':
                self.mypos = message['myPos']
            elif message['stage'] == 'tribute':
                self.tribute_result = message['result']
            elif message['stage'] == 'episodeOver':
                reward = self.get_reward(message)
                # 推荐写法（最简洁、不会报错）
                self.socket.send(serialize(reward).to_buffer())
                self.socket.recv()
                # 信息重置
                self.history_action = {0: [], 1: [], 2: [], 3: []}
                self.action_seq = []
                self.other_left_hands = [2 for _ in range(54)]
                self.flag = 0
                self.action_order = []
                self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
                self.over = []
            elif message['stage'] == 'play':
                just_play = message['curPos']
                action = card2num(message['curAction'][2])
                if message['curPos'] != self.mypos:
                    for ele in action:
                        self.other_left_hands[ele] -= 1
                if len(self.over) == 0:
                    self.action_order.append(just_play)
                    self.action_seq.append(action)
                    self.history_action[message['curPos']].append(action)
                elif len(self.over) == 1:
                    if len(action) > 0 and self.flag == 1:
                        self.flag = 2
                        if just_play == (self.over[0] + 3) % 4:
                            self.action_order.append(just_play)
                            self.action_seq.append(action)
                            self.history_action[message['curPos']].append(action)
                            self.action_order.append(self.over[0])
                            self.history_action[self.over[0]].append([-1])
                            self.action_seq.append([-1])
                        else:
                            self.action_order.append(just_play)
                            self.action_seq.append(action)
                            self.history_action[message['curPos']].append(action)
                    elif self.flag == 1 and (just_play + 1) % 4 == self.over[0]:
                        self.flag = 2
                        self.action_order.append(just_play)
                        self.action_seq.append(action)
                        self.history_action[message['curPos']].append(action)
                        self.action_order.append(self.over[0])
                        self.history_action[self.over[0]].append([-1])
                        self.action_seq.append([-1])
                        self.action_order.append((just_play + 2) % 4)
                        self.history_action[(just_play + 2) % 4].append([])
                        self.action_seq.append([])
                    elif just_play == (self.over[0] + 3) % 4 and self.flag == 2:
                        self.action_order.append(just_play)
                        self.action_seq.append(action)
                        self.history_action[message['curPos']].append(action)
                        self.action_order.append(self.over[0])
                        self.history_action[self.over[0]].append([-1])
                        self.action_seq.append([-1])
                    else:
                        self.action_order.append(just_play)
                        self.action_seq.append(action)
                        self.history_action[message['curPos']].append(action)
                elif len(self.over) == 2:
                    if len(action) > 0 and self.flag <= 2:
                        if (just_play + 1) % 4 not in self.over:
                            self.flag = 3
                            self.action_order.append(just_play)
                            self.action_seq.append(action)
                            self.history_action[message['curPos']].append(action)
                        else:
                            self.flag = 3
                            self.action_order.append(just_play)
                            self.action_seq.append(action)
                            self.history_action[message['curPos']].append(action)
                            self.action_order.append((just_play + 1) % 4)
                            self.history_action[(just_play + 1) % 4].append([-1])
                            self.action_seq.append([-1])
                            self.action_order.append((just_play + 2) % 4)
                            self.history_action[(just_play + 2) % 4].append([-1])
                            self.action_seq.append([-1])
                    elif self.flag <= 2 and (just_play + 1) % 4 in self.over:
                        self.flag = 3
                        self.action_order.append(just_play)
                        self.action_seq.append(action)
                        self.history_action[message['curPos']].append(action)
                        self.action_order.append((just_play + 1) % 4)
                        self.history_action[(just_play + 1) % 4].append([-1])
                        self.action_seq.append([-1])
                        self.action_order.append((just_play + 2) % 4)
                        self.history_action[(just_play + 2) % 4].append([-1])
                        self.action_seq.append([-1])
                        if just_play == (self.over[-1] + 2) % 4:
                            self.action_order.append((just_play + 3) % 4)
                            self.history_action[(just_play + 3) % 4].append([])
                            self.action_seq.append([])
                    elif (just_play + 1) % 4 in self.over and self.flag == 3:
                        self.action_order.append(just_play)
                        self.action_seq.append(action)
                        self.history_action[message['curPos']].append(action)
                        self.action_order.append((just_play + 1) % 4)
                        self.history_action[(just_play + 1) % 4].append([-1])
                        self.action_seq.append([-1])
                        self.action_order.append((just_play + 2) % 4)
                        self.history_action[(just_play + 2) % 4].append([-1])
                        self.action_seq.append([-1])
                    else:
                        self.action_order.append(just_play)
                        self.action_seq.append(action)
                        self.history_action[message['curPos']].append(action)

                self.remaining[just_play] -= len(action)
                if self.remaining[just_play] == 0:
                    self.over.append(just_play)

        elif message["type"] == 'act':
            if message["stage"] == "back":
                act_index = self.back_action(message, self.mypos, self.tribute_result)
                ws.send(json.dumps({"actIndex": int(act_index)}))
            elif message["stage"] == "tribute":
                act_index = self.tribute(message['actionList'], message["curRank"])
                ws.send(json.dumps({"actIndex": int(act_index)}))
            elif message["stage"] == 'play':
                if self.flag == 0:
                    init_hand = card2num(message['handCards'])
                    for ele in init_hand:
                        self.other_left_hands[ele] -= 1
                    self.flag = 1

                if len(message['actionList']) == 1:
                    ws.send(json.dumps({"actIndex": 0}))
                else:
                    # print(
                    #     f"Client {self.args.client_index}: sending decision request, actions={len(message['actionList'])}")
                    # state = self.prepare(message)
                    # self.socket.send(serialize(state).to_buffer())
                    # print(f"Client {self.args.client_index}: waiting for reply...")
                    # act_index = deserialize(self.socket.recv())
                    # print(f"Client {self.args.client_index}: received reply {act_index}")
                    # ws.send(json.dumps({"actIndex": int(act_index)}))
                    state = self.prepare(message)
                    data = serialize(state).to_buffer()  # 序列化为字节
                    self.socket.send(data)
                    act_index = deserialize(self.socket.recv())
                    ws.send(json.dumps({"actIndex": int(act_index)}))

        # if message.get('stage') == 'episodeOver':
        #     reward = self.get_reward(message)
        #     self.socket.send(serialize(reward).to_buffer())
        #     self.socket.recv()
        #     # 信息重置
        #     self.history_action = {0: [], 1: [], 2: [], 3: []}
        #     self.action_seq = []
        #     self.other_left_hands = [2 for _ in range(54)]
        #     self.flag = 0
        #     self.action_order = []
        #     self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
        #     self.over = []

    def on_close(self, ws, close_status_code, close_msg):
        print("Closed down", close_status_code, close_msg)

    def on_error(self, ws, error):
        print("WebSocket error:", error)

    def connect(self):
        """建立WebSocket连接并进入事件循环"""
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_close=self.on_close,
            on_error=self.on_error
        )
        # 运行连接（阻塞直到连接关闭）
        self.ws.run_forever(ping_interval=30, ping_timeout=10)

    # 以下方法保持不变
    def get_reward(self, message):
        team = [self.mypos, (self.mypos + 2) % 4]
        order = message['order']
        rewards = {"1100": 3, "1010": 2, "1001": 1, "0110": -1, "0101": -2, "0011": -3}
        res = ""
        for i in order:
            if i in team:
                res += '1'
            else:
                res += '0'
        if RANK[message['curRank']] == 13:
            if rewards[res] == 2 or rewards[res] == 3:
                return f'y{rewards[res]}'
            elif rewards[res] == -2 or rewards[res] == -3:
                return f'n{-rewards[res]}'
            else:
                return rewards[res]
        else:
            return rewards[res]

    def proc_universal(self, handCards, cur_rank):
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

    def prepare(self, message):
        num_legal_actions = message['indexRange'] + 1
        legal_actions = [card2num(i[2]) for i in message['actionList']]
        my_handcards = card2array(card2num(message['handCards']))
        my_handcards_batch = np.repeat(my_handcards[np.newaxis, :], num_legal_actions, axis=0)

        universal_card_flag = self.proc_universal(my_handcards, RANK[message['curRank']])
        universal_card_flag_batch = np.repeat(universal_card_flag[np.newaxis, :], num_legal_actions, axis=0)

        other_hands = []
        for i in range(54):
            if self.other_left_hands[i] == 1:
                other_hands.append(i)
            elif self.other_left_hands[i] == 2:
                other_hands.append(i)
                other_hands.append(i)
        other_handcards = card2array(other_hands)
        other_handcards_batch = np.repeat(other_handcards[np.newaxis, :], num_legal_actions, axis=0)

        last_action = []
        if len(self.action_seq) > 0:
            last_action = card2array(self.action_seq[-1])
        else:
            last_action = card2array([-1])
        last_action_batch = np.repeat(last_action[np.newaxis, :], num_legal_actions, axis=0)

        last_teammate_action = []
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
        obs = {
            'x_batch': x_batch.astype(np.float32),
            'legal_actions': legal_actions,
            'x_no_action': x_no_action.astype(np.float32),
        }
        return obs

    def back_action(self, msg, mypos, tribute_result):
        rank = msg["curRank"]
        self.action = msg["actionList"]
        handCards = msg["handCards"]
        card_val = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10, "J": 11,
                    "Q": 12, "K": 13, "A": 14, "B": 16, "R": 17}
        card_val[rank] = 15

        def flag_TJQ(handCards_X) -> tuple:
            flag_T = False
            flag_J = False
            flag_Q = False
            for i in range(len(handCards_X)):
                if handCards_X[i][0][-1] == "T":
                    flag_T = True
                if handCards_X[i][0][-1] == "J":
                    flag_J = True
                if handCards_X[i][0][-1] == "Q":
                    flag_Q = True
            return flag_T, flag_J, flag_Q

        def get_card_index(target: str) -> int:
            for i in range(len(self.action)):
                if self.action[i][2][0] == target:
                    return i

        def choose_in_single(single_list) -> str:
            for my_pos in tribute_result:
                if my_pos[1] == mypos:
                    tribute_pos = my_pos[0]

            n = len(single_list)
            if (int(tribute_pos) + int(mypos)) % 2 != 0:
                for card in single_list:
                    if card in ['H5', 'HT']:
                        return card
                    elif card in ['S5', 'C5', 'D5', 'ST', 'CT', 'DT']:
                        return card
                return single_list[randint(0, n - 1)]
            else:
                back_list = []
                for card in single_list:
                    if card[-1] != 'T':
                        if int(card[-1]) < 5:
                            back_list.append(card)
                if back_list:
                    return back_list[randint(0, len(back_list) - 1)]
                return single_list[randint(0, n - 1)]

        def choose_in_pair(pair_list, pair_list_from_handcards) -> str:
            val_dict = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10}
            if len(pair_list) < 3:
                return pair_list[0][0]
            for i in range(len(pair_list)):
                flag = False
                if i >= 2:
                    pair_first_val, pair_second_val, pair_third_val = pair_list[i - 2][0][-1], pair_list[i - 1][0][-1], \
                                                                      pair_list[i][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1 and val_dict[pair_second_val] == \
                            val_dict[pair_third_val] - 1:
                        flag = True
                if 1 <= i <= len(pair_list) - 2:
                    pair_first_val, pair_second_val, pair_third_val = pair_list[i - 1][0][-1], pair_list[i][0][-1], \
                                                                      pair_list[i + 1][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1 and val_dict[pair_second_val] == \
                            val_dict[pair_third_val] - 1:
                        flag = True
                if i <= len(pair_list) - 3:
                    pair_first_val, pair_second_val, pair_third_val = pair_list[i][0][-1], pair_list[i + 1][0][-1], \
                                                                      pair_list[i + 2][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1 and val_dict[pair_second_val] == \
                            val_dict[pair_third_val] - 1:
                        flag = True
                if pair_list[i][0][-1] == '9':
                    flag_T, flag_J, flag_Q = flag_TJQ(pair_list_from_handcards)
                    if flag_T and flag_J:
                        flag = True
                if pair_list[i][0][-1] == 'T':
                    flag_T, flag_J, flag_Q = flag_TJQ(pair_list_from_handcards)
                    if flag_J and flag_Q:
                        flag = True
                if flag:
                    continue
                else:
                    return pair_list[i][0]
            return pair_list[0][0]

        def choose_in_trips(trips_list, trips_list_from_handcards) -> str:
            val_dict = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9, "T": 10}
            if len(trips_list) < 2:
                return trips_list[0][0]
            for i in range(len(trips_list)):
                flag = False
                if i >= 1:
                    pair_first_val, pair_second_val = trips_list[i - 1][0][-1], trips_list[i][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1:
                        flag = True
                if i <= len(trips_list) - 2:
                    pair_first_val, pair_second_val = trips_list[i][0][-1], trips_list[i + 1][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1:
                        flag = True
                if trips_list[i][0][-1] == 'T':
                    flag_T, flag_J, flag_Q = flag_TJQ(trips_list_from_handcards)
                    if flag_J:
                        flag = True
                if flag:
                    continue
                else:
                    return trips_list[i][0]
            return trips_list[0][0]

        def choose_in_bomb(bomb_list, bomb_info) -> str:
            def get_card_from_bomb(bomb_list, key):
                for bomb in bomb_list:
                    for card in bomb:
                        if card[-1] == key:
                            return card

            #for key, value in bomb_info.items():
            for key, value in bomb_info:
                if value > 4:
                    return get_card_from_bomb(bomb_list, key)
            return bomb_list[0][0]

        combined_handcards, handCards_bomb_info = combine_handcards(handCards, rank, card_val)

        combined_temp = {"Single": [], "Trips": [], "Pair": [], "Bomb": []}
        temp_bomb_info = {}
        for card in combined_handcards["Single"]:
            if card_val[card[-1]] <= 10:
                combined_temp["Single"].append(card)
        for trips_card in combined_handcards["Trips"]:
            if card_val[trips_card[0][-1]] <= 10:
                combined_temp["Trips"].append(trips_card)
        for pair_card in combined_handcards["Pair"]:
            if card_val[pair_card[0][-1]] <= 10:
                combined_temp["Pair"].append(pair_card)
        for bomb_card in combined_handcards["Bomb"]:
            if card_val[bomb_card[0][-1]] <= 10:
                combined_temp["Bomb"].append(bomb_card)
        for key, values in handCards_bomb_info.items():
            if card_val[key] <= 10:
                temp_bomb_info[key] = values
        card = None
        if combined_temp["Single"]:
            card = choose_in_single(combined_temp["Single"])
        elif combined_temp["Trips"]:
            card = choose_in_trips(combined_temp["Trips"], combined_handcards["Trips"])
        elif combined_temp["Pair"]:
            card = choose_in_pair(combined_temp["Pair"], combined_handcards["Pair"])
        elif combined_temp["Bomb"]:
            card = choose_in_bomb(combined_temp["Bomb"], temp_bomb_info)
        else:
            temp = []
            for handCard in handCards:
                if card_val[handCard[-1]] <= 10:
                    temp.append(handCard)
            card = temp[randint(0, len(temp) - 1)]
        return get_card_index(card)

    def tribute(self, actionList, rank):
        rank_card = 'H' + rank
        first_action = actionList[0]
        if rank_card in first_action[2]:
            return 1
        else:
            return 0


def run_one_client(index, args):
    args.client_index = index
    client = MyClient(f'ws://127.0.0.1:23456/game/client{index}', args)
    client.connect()

def run_ai(seat, ai_type, server_url):
    """启动规则AI客户端进程"""
    import os

    # 计算showdown/clients目录的绝对路径
    current_dir = os.path.dirname(os.path.abspath(__file__))
    script_dir = os.path.join(current_dir, '..', '..', 'showdown', 'clients')
    script_dir = os.path.normpath(script_dir)

    if ai_type == 'hard':
        script = 'client_r2.py'
    else:
        script = 'client_ri.py'

    server_url = 'ws://127.0.0.1:23456/game/client'
    cmd = [sys.executable, script, f'--seat={seat}', f'--server_url={server_url}']

    print(f"[Rule AI Client {seat}] Starting {script} from {script_dir}")
    subprocess.run(cmd, cwd=script_dir, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    args, _ = parser.parse_known_args()
    clients = []
    server_url = "ws://127.0.0.1:23456/game/client"
    for i in range(4):
        print("启动玩家！")
        if i==0:
            p = Process(target=run_one_client, args=(i, args))
            p.start()
        else:
            # 随机选择难度：'normal' -> client_ri.py, 'hard' -> client_r2.py
            diff = 'normal' if random.random() < 0.5 else 'hard'
            p = Process(target=run_ai, args=(i, diff, server_url))
            p.start()
        print("启动ai玩家！")
        time.sleep(0.2)
        clients.append(p)
    try:
        for client in clients:
            client.join()
    except KeyboardInterrupt:
        for p in clients:
            p.terminate()


if __name__ == '__main__':
    main()