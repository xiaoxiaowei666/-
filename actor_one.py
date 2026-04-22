import os
import time
from argparse import ArgumentParser
from multiprocessing import Process, freeze_support
from pathlib import Path

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
                    help='IP address of learner server')
parser.add_argument('--data_port', type=int, default=12345,
                    help='Learner server port to send training data')
parser.add_argument('--param_port', type=int, default=12346,
                    help='Learner server port to subscribe model parameters')
parser.add_argument('--exp_path', type=str,
                    default=str(Path.cwd() / 'guandan_actor_logs'),
                    help='Directory to save logs and checkpoints')
parser.add_argument('--num_saved_ckpt', type=int, default=4,
                    help='Number of recent checkpoint files to be saved')
parser.add_argument('--observation_space', type=int, default=(567,))
parser.add_argument('--action_space', type=int, default=(5, 216))
parser.add_argument('--epsilon', type=float, default=0.5,  # 初始探索率提高
                    help='Epsilon for epsilon-greedy')
parser.add_argument('--epsilon_decay', type=float, default=0.999,
                    help='Decay factor for epsilon per episode')
parser.add_argument('--epsilon_min', type=float, default=0.01,
                    help='Minimum epsilon')


class Player():
    def __init__(self, args) -> None:
        os.environ["TF_CPP_MIN_LOG_LEVEL"] = '3'
        tf.compat.v1.logging.set_verbosity(tf.compat.v1.logging.ERROR)
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        set_session(tf.Session(config=config))

        self.mb_states_no_action, self.mb_actions, self.mb_q = [], [], []
        self.all_mb_states_no_action, self.all_mb_actions, self.all_mb_q = [], [], []
        self.args = args
        self.step = 0
        self.num_set_weight = 0
        self.send_times = 1

        self.episode_process_rewards = []
        self.last_handcards = 27
        self.consecutive_passes = 0   # 连续 PASS 计数

        self.model_id = -1
        self.model = GDModel(self.args.observation_space, (5, 216))

        # ZMQ 连接
        context = zmq.Context()
        context.linger = 0
        self.socket = context.socket(zmq.REQ)
        self.socket.connect(f'tcp://{self.args.ip}:{self.args.data_port}')

        # 日志目录
        self.args.exp_path = str(Path(self.args.exp_path) / f'Client{args.client_index}')
        create_experiment_dir(self.args, f'Client{args.client_index}-')
        self.args.ckpt_path = self.args.exp_path / 'ckpt'
        self.args.log_path = self.args.exp_path / 'log'
        self.args.ckpt_path.mkdir()
        self.args.log_path.mkdir()
        logger.configure(str(self.args.log_path))

        # 启动权重订阅进程
        subscriber = Process(target=run_weights_subscriber, args=(self.args, None))
        subscriber.start()

        # 等待初始权重
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
        """选择动作，并计算过程奖励（修改版：提高出牌奖励，惩罚 PASS）"""
        output = self.model.forward(state['x_batch'])
        legal_actions = state['legal_actions']

        # 找到 PASS 动作的索引（假设 PASS 表示为空列表 []）
        pass_idx = None
        for i, act in enumerate(legal_actions):
            if act == []:
                pass_idx = i
                break

        # ---------- ε-贪婪选择（带强制非 PASS 探索） ----------
        if self.args.epsilon > 0 and np.random.rand() < self.args.epsilon:
            action_idx = np.random.randint(0, len(legal_actions))
        else:
            action_idx = np.argmax(output)

        # 强制探索：如果选了 PASS 且还有其它合法动作，以 80% 概率重新选非 PASS 动作
        if action_idx == pass_idx and len(legal_actions) > 1:
            if np.random.rand() < 0.8:
                non_pass_indices = [i for i, act in enumerate(legal_actions) if act != []]
                action_idx = np.random.choice(non_pass_indices)

        # ---------- 计算过程奖励（大幅调整） ----------
        process_reward = 0.0
        current_handcards = len(state.get('handcards', []))
        if self.last_handcards is None:
            self.last_handcards = current_handcards

        # 1. 手牌剩余惩罚（保持轻微，避免过于消极）
        process_reward -= 0.005 * current_handcards

        # 2. 出牌奖励（显著提高）
        if action_idx != pass_idx:
            process_reward += 0.3                     # 基础出牌奖励
            cards_reduced = self.last_handcards - current_handcards
            if cards_reduced > 0:
                process_reward += 0.1 * cards_reduced   # 每减少一张额外奖励
        else:
            # 3. 惩罚 PASS（除非只有 PASS 可选）
            process_reward -= 0.2
            self.consecutive_passes += 1
            if self.consecutive_passes >= 2:
                process_reward -= 0.3                  # 连续 PASS 额外惩罚
        if action_idx != pass_idx:
            self.consecutive_passes = 0

        self.last_handcards = current_handcards
        self.episode_process_rewards.append(process_reward)
        # ---------------------------------------------

        q = output[action_idx]
        self.step += 1
        action = legal_actions[action_idx]

        self.mb_states_no_action.append(state['x_no_action'])
        self.mb_actions.append(card2array(action))
        self.mb_q.append(q)

        return action_idx

    def update_weight(self):
        new_weights, self.model_id = find_new_weights(self.model_id, self.args.ckpt_path)
        if new_weights is not None:
            self.model.set_weights(new_weights)

    def _aggregate_episode_data(self):
        self.all_mb_states_no_action.extend(self.mb_states_no_action)
        self.all_mb_actions.extend(self.mb_actions)
        self.all_mb_q.extend(self.mb_q)
        self.mb_states_no_action.clear()
        self.mb_actions.clear()
        self.mb_q.clear()

    def send_data(self, final_result):
        self._aggregate_episode_data()

        if final_result[0] == 'y':
            base_reward = float(final_result[1:]) if len(final_result) > 1 else 3.0
        else:
            base_reward = -float(final_result[1:]) if len(final_result) > 1 else -3.0

        gamma = 0.99
        returns = []
        running_return = base_reward
        for r in reversed(self.episode_process_rewards):
            running_return = r + gamma * running_return
            returns.append(running_return)
        returns = list(reversed(returns))

        states_no_action = np.asarray(self.all_mb_states_no_action)
        actions = np.asarray(self.all_mb_actions)
        q = np.asarray(self.all_mb_q)
        rewards = np.asarray(returns).reshape(-1, 1)

        data = [states_no_action, actions, q, rewards]
        name = ['x_no_action', 'action', 'q', 'reward']
        self.socket.send(serialize(dict(zip(name, data))).to_buffer())
        self.socket.recv()

        # 日志
        if self.send_times % 10000 == 0:
            self.send_times = 1
            logger.record_tabular("ep_step", self.step)
            logger.record_tabular("avg_process_reward", np.mean(self.episode_process_rewards))
            logger.record_tabular("final_base_reward", base_reward)
            logger.record_tabular("epsilon", self.args.epsilon)
            logger.dump_tabular()
        else:
            self.send_times += 1

        # 衰减 epsilon（每局后）
        self.args.epsilon = max(self.args.epsilon_min, self.args.epsilon * self.args.epsilon_decay)

        # 重置状态
        self.step = 0
        self.last_handcards = 27
        self.episode_process_rewards.clear()
        self.all_mb_states_no_action.clear()
        self.all_mb_actions.clear()
        self.all_mb_q.clear()
        self.consecutive_passes = 0


def run_one_player(index, args):
    args.client_index = index
    player = Player(args)

    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.bind(f'tcp://*:{6000+index}')

    while True:
        state = deserialize(socket.recv())
        if not isinstance(state, (int, float, str)):
            action_idx = player.sample(state)
            socket.send(serialize(action_idx).to_buffer())
        elif isinstance(state, str):
            socket.send(b'none')
            player.send_data(state)
            player.update_weight()
        else:
            socket.send(b'none')


def main():
    args, _ = parser.parse_known_args()
    players = []
    for i in range(1):
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