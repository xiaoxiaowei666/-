


思路:依据南邮的游戏服务器，然后改写action，其实就是选择不同的action即可！ 然后就是选择咯！
//思路明白咯！ 然后就是渲染问题咯1



1.修改game.py：1，pip install websocket-client

```py

import os

from pyarrow import deserialize, serialize

os.environ["KMP_WARNINGS"] = "FALSE" 

import json
import time
import warnings
from argparse import ArgumentParser
from functools import reduce
from multiprocessing import Process, freeze_support
from random import randint

import zmq
import websocket
from utils.utils import *

warnings.filterwarnings("ignore")
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
parser = ArgumentParser()
parser.add_argument('--ip', type=str, default='127.0.0.1',
                    help='IP address of learner server')
parser.add_argument('--action_port', type=int, default=6000,
                    help='Learner server port to send training data')


RANK = {
    '2':1, '3':2, '4':3, '5':4, '6':5, '7':6, '8':7, '9':8,
    'T':9, 'J':10, 'Q':11, 'K':12, 'A':13
}


def _get_one_hot_array(num_left_cards, max_num_cards, flag):
    if flag == 0:
        one_hot = np.zeros(max_num_cards)
        one_hot[num_left_cards - 1] = 1
    else:
        one_hot = np.zeros(max_num_cards+1)
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
        self.history_action = {0: [], 1: [], 2: [], 3:[]}
        self.action_seq = []
        self.action_order = []
        self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
        self.other_left_hands = [2 for _ in range(54)]
        self.flag = 0
        self.over = []
        self.max_acion = 5000

        # 初始化zmq
        self.context = zmq.Context()
        self.context.linger = 0
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f'tcp://localhost:{6000+args.client_index}')

    def on_open(self, ws):
        pass

    def on_message(self, ws, message):
        message = json.loads(message)
        print(message)
        if message['type'] == 'notify':
            if message['stage'] == 'beginning':
                self.mypos = message['myPos']
            elif message['stage'] == 'tribute':
                self.tribute_result = message['result']
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
                        if (just_play+1) % 4 not in self.over:
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
                    elif self.flag <= 2 and (just_play+1) % 4 in self.over:
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
                    elif (just_play+1) % 4 in self.over and self.flag == 3:
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
                self.send(json.dumps({"actIndex": int(act_index)}))
            elif message["stage"] == "tribute":
                act_index = self.tribute(message['actionList'], message["curRank"])
                self.send(json.dumps({"actIndex": int(act_index)}))
            elif message["stage"] == 'play':
                if self.flag == 0:
                    init_hand = card2num(message['handCards'])
                    for ele in init_hand:
                        self.other_left_hands[ele] -= 1
                    self.flag = 1
                if len(message['actionList']) == 1:
                    self.send(json.dumps({"actIndex": 0}))
                else:
                    state = self.prepare(message)
                    self.socket.send(serialize(state).to_buffer())
                    act_index = deserialize(self.socket.recv())
                    self.send(json.dumps({"actIndex": int(act_index)}))

        if message['stage'] == 'episodeOver':
            reward = self.get_reward(message)
            self.socket.send(serialize(reward).to_buffer())
            self.socket.recv()
            self.history_action = {0: [], 1: [], 2: [], 3:[]}
            self.action_seq = []
            self.other_left_hands = [2 for _ in range(54)]
            self.flag = 0
            self.action_order = []
            self.remaining = {0: 27, 1: 27, 2: 27, 3: 27}
            self.over = []

    def on_error(self, ws, error):
        print("WebSocket error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        print("Closed down", close_status_code, close_msg)

    def send(self, data):
        if self.ws:
            self.ws.send(data)

    def run_forever(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

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
        if handCards[(cur_rank-1)*4] == 0:
            return res
        res[0] = 1
        rock_flag = 0
        for i in range(4):
            left, right = 0, 5
            temp = [handCards[i + j*4] if i+j*4 != (cur_rank-1)*4 else 0 for j in range(5)]
            while right <= 12:
                zero_num = temp.count(0)
                if zero_num <= 1:
                    rock_flag = 1
                    break
                else:
                    temp.append(handCards[i + right*4] if i+right*4 != (cur_rank-1)*4 else 0)
                    temp.pop(0)
                    left += 1
                    right += 1
            if rock_flag == 1:
                break
        res[1] = rock_flag
        num_count = [0] * 13
        for i in range(4):
            for j in range(13):
                if handCards[i + j*4] != 0 and i + j*4 != (cur_rank-1)*4:
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
                    if num_count[i] == 2 and num_count[i-1] >= 3 or num_count[i] >= 3 and num_count[i-1] == 2:
                        res[9] = 1
                    elif num_count[i] == 2 and num_count[i-1] == 2:
                        res[11] = 1
                if i >= 2:
                    if num_count[i-2] == 1 and num_count[i-1] >= 2 and num_count[i] >= 2 or \
                        num_count[i-2] >= 2 and num_count[i-1] == 1 and num_count[i] >= 2 or \
                        num_count[i-2] >= 2 and num_count[i-1] >= 2 and num_count[i] == 1:
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
        last_action = card2array(self.action_seq[-1]) if len(self.action_seq) > 0 else card2array([-1])
        last_action_batch = np.repeat(last_action[np.newaxis, :], num_legal_actions, axis=0)
        last_teammate_action = card2array(self.history_action[(self.mypos + 2) % 4][-1]) if len(self.history_action[(self.mypos + 2) % 4]) > 0 and (self.mypos + 2) % 4 not in self.over else card2array([-1])
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
        down_played_cards = card2array(reduce(lambda x, y: x+y, self.history_action[(self.mypos + 1) % 4])) if len(self.history_action[(self.mypos + 1) % 4]) > 0 else card2array([])
        down_played_cards_batch = np.repeat(down_played_cards[np.newaxis, :], num_legal_actions, axis=0)
        teammate_played_cards = card2array(reduce(lambda x, y: x+y, self.history_action[(self.mypos + 2) % 4])) if len(self.history_action[(self.mypos + 2) % 4]) > 0 else card2array([])
        teammate_played_cards_batch = np.repeat(teammate_played_cards[np.newaxis, :], num_legal_actions, axis=0)
        up_played_cards = card2array(reduce(lambda x, y: x+y, self.history_action[(self.mypos + 3) % 4])) if len(self.history_action[(self.mypos + 3) % 4]) > 0 else card2array([])
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
        if num_legal_actions < self.max_acion:
            x_batch = np.concatenate((x_batch, np.zeros((self.max_acion-num_legal_actions, 567), dtype=np.int8)))
            legal_index = np.concatenate((np.ones(num_legal_actions, dtype=np.int8), np.zeros(self.max_acion-num_legal_actions, dtype=np.int8)))
        else:
            legal_index = np.ones(num_legal_actions, dtype=np.int8)
        obs = {
            'x_batch': x_batch.astype(np.float32),
            'legal_index': legal_index,
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
                    pair_first_val, pair_second_val, pair_third_val = pair_list[i - 2][0][-1], pair_list[i - 1][0][-1], pair_list[i][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1 and val_dict[pair_second_val] == val_dict[pair_third_val] - 1:
                        flag = True
                if 1 <= i <= len(pair_list) - 2:
                    pair_first_val, pair_second_val, pair_third_val = pair_list[i - 1][0][-1], pair_list[i][0][-1], pair_list[i + 1][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1 and val_dict[pair_second_val] == val_dict[pair_third_val] - 1:
                        flag = True
                if i <= len(pair_list) - 3:
                    pair_first_val, pair_second_val, pair_third_val = pair_list[i][0][-1], pair_list[i + 1][0][-1], pair_list[i + 2][0][-1]
                    if val_dict[pair_first_val] == val_dict[pair_second_val] - 1 and val_dict[pair_second_val] == val_dict[pair_third_val] - 1:
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
            for key, value in bomb_info.items():
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
        rank_card = 'H'+rank
        first_action = actionList[0]
        if rank_card in first_action[2]:
            return 1
        else:
            return 0


def run_one_client(index, args):
    args.client_index = index
    client = MyClient(f'ws://127.0.0.1:23456/game/client{index}', args)
    client.run_forever()


def main():
    args, _ = parser.parse_known_args()
    clients = []
    for i in range(4):
        p = Process(target=run_one_client, args=(i, args))
        p.start()
        time.sleep(0.2)
        clients.append(p)

    try:
        for client in clients:
            client.join()
    except KeyboardInterrupt:
        for p in clients:
            p.terminate()


if __name__ == '__main__':
    freeze_support()
    main()
```



2.修改actor.py ，因为actor.py不做出决策！,同时在actor_ppo 下创建了guandan_actor_logs文件夹


```py
import os
import time
from argparse import ArgumentParser
from multiprocessing import Process, freeze_support
from pathlib import Path
from random import randint
from statistics import mean

import numpy as np
import tensorflow as tf
import zmq
from model import GDPPOModel
from pyarrow import deserialize, serialize
from tensorflow.keras.backend import set_session
from utils import logger
from utils.data_trans import (create_experiment_dir, find_new_weights,
                              run_weights_subscriber)
from utils.utils import *

parser = ArgumentParser()
parser.add_argument('--ip', type=str, default='127.0.0.1',
                    help='IP address of learner server (本机使用 127.0.0.1)')
parser.add_argument('--data_port', type=int, default=5000,
                    help='Learner server port to send training data')
parser.add_argument('--param_port', type=int, default=5001,
                    help='Learner server port to subscribe model parameters')
parser.add_argument('--exp_path', type=str,
                    default=str(Path.cwd() / 'guandan_actor_logs'),
                    help='Directory to save logging data, model parameters and config file')
parser.add_argument('--num_saved_ckpt', type=int, default=4,
                    help='Number of recent checkpoint files to be saved')
parser.add_argument('--observation_space', type=int, default=(5000, 567),
                    help='The YAML configuration file')
parser.add_argument('--action_space', type=int, default=(5, 216),
                    help='The YAML configuration file')
parser.add_argument('--epsilon', type=float, default=0.01,
                    help='Epsilon')

class Player():
    def __init__(self, args) -> None:
        # Set 'allow_growth'
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = '3'
        tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        set_session(tf.Session(config=config))

        # 数据初始化
        self.mb_states, self.mb_legal_indexs, self.mb_rewards, self.mb_actions, self.mb_dones, self.mb_values, self.mb_neglogp = [], [], [], [], [], [], []
        self.all_mb_states, self.all_mb_legal_indexs, self.all_mb_rewards, self.all_mb_actions, self.all_mb_dones, self.all_mb_values, self.all_mb_neglogp = [], [], [], [], [], [], []
        self.args = args
        self.step = 0
        self.num_set_weight = 0
        self.send_times = 1

        # 模型初始化
        self.model_id = -1
        self.model  = GDPPOModel(self.args.observation_space)

        # 连接learner
        context = zmq.Context()
        context.linger = 0  # For removing linger behavior
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f'tcp://{self.args.ip}:{self.args.data_port}')

        # log文件
        self.args.exp_path = str(Path(self.args.exp_path) / f'Client{args.client_index}')
        create_experiment_dir(self.args, f'Client{args.client_index}-')
        self.args.ckpt_path = self.args.exp_path / 'ckpt'
        self.args.log_path = self.args.exp_path / 'log'
        self.args.ckpt_path.mkdir()
        self.args.log_path.mkdir()
        logger.configure(str(self.args.log_path))

        # 开模型订阅
        subscriber = Process(target=run_weights_subscriber, args=(self.args, None))
        subscriber.start()

        # 初始化模型
        # print('set weight start')
        # model_init_flag = 0
        # while model_init_flag == 0:
        #     new_weights, self.model_id = find_new_weights(-1, self.args.ckpt_path)
        #     if new_weights is not None:
        #         self.model.set_weights(new_weights)
        #         self.num_set_weight += 1
        #         model_init_flag = 1
        # print('set weight success') 

    def sample(self, state) -> int:
        action, value, neglogp = self.model.forward([state['x_batch']], [state['legal_index']])
        self.mb_states.append(state['x_batch'])
        self.mb_legal_indexs.append(state['legal_index'])
        self.mb_actions.append(action)
        self.mb_values.append(value)
        self.mb_neglogp.append(neglogp)
        return action
        
    def update_weight(self):
        new_weights, self.model_id = find_new_weights(self.model_id, self.args.ckpt_path)
        if new_weights is not None:
            self.model.set_weights(new_weights)

    def save_data(self, reward):
        self.mb_rewards = [[reward] for _ in range(len(self.mb_states))]
        self.mb_dones = [[0] for _ in range(len(self.mb_states))]
        self.mb_dones[-1] = [1]
        self.all_mb_states += self.mb_states
        self.all_mb_legal_indexs += self.mb_legal_indexs
        self.all_mb_rewards += self.mb_rewards
        self.all_mb_actions += self.mb_actions
        self.all_mb_dones += self.mb_dones
        self.all_mb_values += self.mb_values
        self.all_mb_neglogp += self.mb_neglogp

        self.mb_states, self.mb_legal_indexs, self.mb_rewards, self.mb_actions, self.mb_dones, self.mb_values, self.mb_neglogp = [], [], [], [], [], [], []

    def send_data(self, reward):
        # 调整数据格式并发送
        data = self.prepare_training_data(reward)
        np.save('test.npy', data)
        print('save success!')
        self.socket.send(serialize(data).to_buffer())
        self.socket.recv()

        # 打印log
        if self.send_times % 10000 == 0:
            self.send_times = 1
            logger.record_tabular("ep_step", self.step)
            logger.dump_tabular()
        else:
            self.send_times += 1

        # 重置数据存储
        self.step = 0
        self.mb_states, self.mb_legal_indexs, self.mb_rewards, self.mb_actions, self.mb_dones, self.mb_values, self.mb_neglogp = [], [], [], [], [], [], []
        self.all_mb_states, self.all_mb_legal_indexs, self.all_mb_rewards, self.all_mb_actions, self.all_mb_dones, self.all_mb_values, self.all_mb_neglogp = [], [], [], [], [], [], []

    def prepare_training_data(self, reward):
        # Hyperparameters
        gamma  =  0.99
        lam    =  0.95

        states = np.asarray(self.all_mb_states)
        legal_indexs = np.asarray(self.all_mb_legal_indexs)
        rewards = np.asarray(self.all_mb_rewards)
        actions = np.asarray(self.all_mb_actions)
        dones = np.asarray(self.all_mb_dones)
        values = np.asarray(self.all_mb_values)
        neglogps = np.asarray(self.all_mb_neglogp)
        print(states.shape)
        print(legal_indexs.shape)
        print(rewards.shape)
        print(actions.shape)
        print(dones.shape)
        print(values.shape)
        print(neglogps.shape)
        if reward[0] == 'y':
            rewards += 1
        else:
            rewards -= 1

        values = np.concatenate([values, [[0.0]]])
        deltas   =  rewards + gamma * values[1:] * (1.0 - dones) - values[:-1]
        
        nsteps     =  len(states)
        advs    =  np.zeros_like(rewards)
        lastgaelam =  0
        for t in reversed(range(nsteps)):
            nextnonterminal = 1.0 - dones[t]
            advs[t] = lastgaelam = deltas[t] + gamma * lam * nextnonterminal * lastgaelam
            
        def sf01(arr):
            """
            swap and then flatten axes 0 and 1
            """
            s = arr.shape
            return arr.swapaxes(0, 1).reshape(s[0] * s[1], *s[2:])
        
        returns = advs + values[:-1]
        data = [states, legal_indexs] + [sf01(arr) for arr in [returns, actions, values, neglogps]]
        name = ['x_batch', 'legal_indexs', 'returns', 'actions', 'values', 'neglogps']
        return dict(zip(name, data))


def run_one_player(index, args):
    args.client_index = index
    player = Player(args)

    # 初始化zmq
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f'tcp://*:{6000+index}')

    action_index = 0
    while True:
        # 做动作到获得reward
        state = deserialize(socket.recv())
        if not isinstance(state, int) and not isinstance(state, float) and not isinstance(state, str):
            action_index = player.sample(state)
            socket.send(serialize(action_index).to_buffer())
        elif isinstance(state, str):
            socket.send(b'none')
            if state[0] == 'y':
                player.save_data(int(state[1]))
            else:
                player.save_data(-int(state[1]))
            player.send_data(state)
            player.update_weight()
        else:
            socket.send(b'none')
            player.save_data(state)


def main():
    args, _ = parser.parse_known_args()
    players = []
    for i in range(4):
        p = Process(target=run_one_player, args=(i, args))
        p.start()
        time.sleep(0.5)
        players.append(p)

    try:
        for player in players:
            player.join()
    except KeyboardInterrupt:
        for p in players:
            p.terminate()

if __name__ == '__main__':
    freeze_support()
    main()


```


3.conda 环境

```conda

(D:\conda_envs\gg) C:\Users\24704>conda list
# packages in environment at D:\conda_envs\gg:
#
# Name                     Version          Build            Channel
absl-py                    2.1.0            pypi_0           pypi
astor                      0.8.1            pypi_0           pypi
ca-certificates            2026.3.19        haa95532_0       https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
certifi                    2024.8.30        pyhd8ed1ab_0     conda-forge
cffi                       1.15.1           py37h2bbff1b_3   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
cryptography               39.0.1           py37h21b164f_0   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
gast                       0.2.2            pypi_0           pypi
google-pasta               0.2.0            pypi_0           pypi
grpcio                     1.62.3           pypi_0           pypi
h5py                       2.10.0           pypi_0           pypi
importlib-metadata         6.7.0            pypi_0           pypi
keras-applications         1.0.8            pypi_0           pypi
keras-preprocessing        1.1.2            pypi_0           pypi
markdown                   3.4.4            pypi_0           pypi
markupsafe                 2.1.5            pypi_0           pypi
numpy                      1.18.5           pypi_0           pypi
openssl                    1.1.1w           h2bbff1b_0       https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
opt-einsum                 3.3.0            pypi_0           pypi
pip                        22.3.1           py37haa95532_0   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
protobuf                   3.20.3           pypi_0           pypi
pyarrow                    5.0.0            pypi_0           pypi
pycparser                  2.21             pyhd3eb1b0_0     https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
pygame                     2.6.1            pypi_0           pypi
pyopenssl                  23.0.0           py37haa95532_0   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
python                     3.7.16           h6244533_0       https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
pyyaml                     6.0.1            pypi_0           pypi
pyzmq                      22.3.0           pypi_0           pypi
setuptools                 65.6.3           py37haa95532_0   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
six                        1.17.0           pypi_0           pypi
sqlite                     3.51.2           hee5a0db_0       https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
tensorboard                1.15.0           pypi_0           pypi
tensorflow                 1.15.5           pypi_0           pypi
tensorflow-estimator       1.15.1           pypi_0           pypi
termcolor                  2.3.0            pypi_0           pypi
typing-extensions          4.7.1            pypi_0           pypi
ucrt                       10.0.22621.0     haa95532_0       https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
vc                         14.3             h2df5915_10      https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
vc14_runtime               14.44.35208      h4927774_10      https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
vs2015_runtime             14.44.35208      ha6b5a95_10      https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
websocket-client           1.6.1            pypi_0           pypi
werkzeug                   2.2.3            pypi_0           pypi
wheel                      0.38.4           py37haa95532_0   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
wincertstore               0.2              py37haa95532_2   https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main
wrapt                      1.16.0           pypi_0           pypi
ws4py                      0.6.0            pypi_0           pypi
zipp                       3.15.0           pypi_0           pypi

```


4.修改mc:game.py


```py
import os
import json
import time
import warnings
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
        # 将原 self.send 调用替换为 ws.send
        if message['type'] == 'notify':
            if message['stage'] == 'beginning':
                self.mypos = message['myPos']
            elif message['stage'] == 'tribute':
                self.tribute_result = message['result']
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
                    state = self.prepare(message)
                    self.socket.send(serialize(state).to_buffer())
                    act_index = deserialize(self.socket.recv())
                    ws.send(json.dumps({"actIndex": int(act_index)}))

        if message.get('stage') == 'episodeOver':
            reward = self.get_reward(message)
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

            for key, value in bomb_info.items():
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


def main():
    args, _ = parser.parse_known_args()
    clients = []
    for i in range(4):
        p = Process(target=run_one_client, args=(i, args))
        p.start()
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

```

5.修改mc:actor.py

```py
import os
import time
from argparse import ArgumentParser
from multiprocessing import Process, freeze_support
from pathlib import Path
from random import randint
from statistics import mean

import numpy as np
import tensorflow as tf
import zmq
from pyarrow import deserialize, serialize
from tensorflow.keras.backend import set_session

from model import GDModel
from utils import logger
from utils.data_trans import (create_experiment_dir, find_new_weights,
                              run_weights_subscriber)
from utils.utils import *

parser = ArgumentParser()
parser.add_argument('--ip', type=str, default='127.0.0.1',
                    help='IP address of learner server (本机训练使用 127.0.0.1)')
parser.add_argument('--data_port', type=int, default=5000,
                    help='Learner server port to send training data')
parser.add_argument('--param_port', type=int, default=5001,
                    help='Learner server port to subscribe model parameters')
parser.add_argument('--exp_path', type=str,
                    default=str(Path.cwd() / 'guandan_actor_logs'),
                    help='Directory to save logging data, model parameters and config file')
parser.add_argument('--num_saved_ckpt', type=int, default=4,
                    help='Number of recent checkpoint files to be saved')
parser.add_argument('--observation_space', type=int, default=(567,),
                    help='The YAML configuration file')
parser.add_argument('--action_space', type=int, default=(5, 216),
                    help='The YAML configuration file')
parser.add_argument('--epsilon', type=float, default=0.01,
                    help='Epsilon')

class Player():
    def __init__(self, args) -> None:
        # Set 'allow_growth'
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = '3'
        tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        set_session(tf.Session(config=config))

        # 数据初始化
        self.mb_states_no_action, self.mb_actions, self.mb_rewards, self.mb_q = [], [], [], []
        self.all_mb_states_no_action, self.all_mb_actions, self.all_mb_rewards = [], [], []
        self.args = args
        self.step = 0
        self.num_set_weight = 0
        self.send_times = 1

        # 模型初始化
        self.model_id = -1
        self.model  = GDModel(self.args.observation_space, (5, 216))

        # 连接learner
        context = zmq.Context()
        context.linger = 0  # For removing linger behavior
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f'tcp://{self.args.ip}:{self.args.data_port}')

        # log文件
        self.args.exp_path = str(Path(self.args.exp_path) / f'Client{args.client_index}')
        create_experiment_dir(self.args, f'Client{args.client_index}-')
        self.args.ckpt_path = self.args.exp_path / 'ckpt'
        self.args.log_path = self.args.exp_path / 'log'
        self.args.ckpt_path.mkdir()
        self.args.log_path.mkdir()
        logger.configure(str(self.args.log_path))

        # 开模型订阅
        subscriber = Process(target=run_weights_subscriber, args=(self.args, None))
        subscriber.start()

        # 初始化模型
        print('set weight start')
        model_init_flag = 0
        while model_init_flag == 0:
            new_weights, self.model_id = find_new_weights(-1, self.args.ckpt_path)
            if new_weights is not None:
                self.model.set_weights(new_weights)
                self.num_set_weight += 1
                model_init_flag = 1
        print('set weight success') 

    def sample(self, state) -> int:
        output = self.model.forward(state['x_batch'])
        if self.args.epsilon > 0 and np.random.rand() < self.args.epsilon:
            action_idx = np.random.randint(0, len(state['legal_actions']))
        else:
            action_idx = np.argmax(output)
        q = output[action_idx]
        self.step += 1
        action = state['legal_actions'][action_idx]
        self.mb_states_no_action.append(state['x_no_action'])
        self.mb_actions.append(card2array(action))
        self.mb_q.append(q)
        return action_idx
        
    def update_weight(self):
        new_weights, self.model_id = find_new_weights(self.model_id, self.args.ckpt_path)
        if new_weights is not None:
            self.model.set_weights(new_weights)

    def save_data(self, reward):
        self.mb_rewards = [[reward] for _ in range(len(self.mb_states_no_action))]
        self.all_mb_states_no_action += self.mb_states_no_action
        self.all_mb_actions += self.mb_actions
        self.all_mb_rewards += self.mb_rewards
        self.all_mb_q += self.all_mb_q

        self.mb_states_no_action = []
        self.mb_rewards = []
        self.mb_actions = []
        self.all_mb_q = []

    def send_data(self, reward):
        # 调整数据格式并发送
        data = self.prepare_training_data(reward)
        self.socket.send(serialize(data).to_buffer())
        self.socket.recv()

        # 打印log
        if self.send_times % 10000 == 0:
            self.send_times = 1
            logger.record_tabular("ep_step", self.step)
            logger.dump_tabular()
        else:
            self.send_times += 1

        # 重置数据存储
        self.step = 0
        self.mb_states_no_action, self.mb_actions, self.mb_rewards, self.mb_q = [], [], [], []
        self.all_mb_states_no_action, self.all_mb_actions, self.all_mb_rewards, self.all_mb_q = [], [], [], []

    def prepare_training_data(self, reward):
        states_no_action = np.asarray(self.all_mb_states_no_action)
        actions = np.asarray(self.all_mb_actions)
        rewards = np.asarray(self.all_mb_rewards)
        q = np.asarray(self.all_mb_q)
        if reward[0] == 'y':
            rewards += 1
        else:
            rewards -= 1
        data = [states_no_action, actions, q, rewards]
        name = ['x_no_action', 'action', 'q', 'reward']
        return dict(zip(name, data))


def run_one_player(index, args):
    args.client_index = index
    player = Player(args)

    # 初始化zmq
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f'tcp://*:{11000+index}')

    action_index = 0
    while True:
        # 做动作到获得reward
        state = deserialize(socket.recv())
        if not isinstance(state, int) and not isinstance(state, float) and not isinstance(state, str):
            action_index = player.sample(state)
            socket.send(serialize(action_index).to_buffer())
        elif isinstance(state, str):
            socket.send(b'none')
            if state[0] == 'y':
                player.save_data(int(state[1]))
            else:
                player.save_data(-int(state[1]))
            player.send_data(state)
            player.update_weight()
        else:
            socket.send(b'none')
            player.save_data(state)


def main():
    args, _ = parser.parse_known_args()
    players = []
    for i in range(4):
        p = Process(target=run_one_player, args=(i, args))
        p.start()
        time.sleep(0.5)
        players.append(p)

    try:
        for player in players:
            player.join()
    except KeyboardInterrupt:
        for p in players:
            p.terminate()

if __name__ == '__main__':

    main()



```


6.修改learner.py


