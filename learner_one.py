import multiprocessing
import os
import time
import pickle
import warnings
from argparse import ArgumentParser
from collections import defaultdict
from multiprocessing import Process

import numpy as np
import tensorflow as tf
import zmq
from pyarrow import deserialize
from tensorflow.keras.backend import set_session

from common import (create_experiment_dir, get_agent, load_yaml_config,
                    save_yaml_config)
from core.mem_pool import MemPoolManager, MultiprocessingMemPool
from utils import logger
from utils.cmdline import parse_cmdline_kwargs

warnings.filterwarnings("ignore")
os.environ["TF_CPP_MIN_LOG_LEVEL"] = '3'


def _init_tensorflow_session():
    tf.logging.set_verbosity(tf.logging.ERROR)
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    set_session(tf.Session(config=config))


parser = ArgumentParser()
parser.add_argument('--alg', type=str, default='MC', help='The RL algorithm')
parser.add_argument('--env', type=str, default='GuanDan', help='The game environment')
parser.add_argument('--data_port', type=int, default=12345, help='Learner server port to receive training data')
parser.add_argument('--param_port', type=int, default=12346, help='Learner server to publish model parameters')
parser.add_argument('--model', type=str, default='guandan_model', help='Training model')
parser.add_argument('--pool_size', type=int, default=65536, help='The max length of data pool')
parser.add_argument('--batch_size', type=int, default=32768, help='The batch size for training')
parser.add_argument('--training_freq', type=int, default=150,
                    help='How many receptions of new data are between each training')
parser.add_argument('--keep_training', type=bool, default=False,
                    help="Keep training regardless of new data")
parser.add_argument('--config', type=str, default=None, help='Directory to config file')
parser.add_argument('--exp_path', type=str, default=None, help='Directory to save logging data and config file')
parser.add_argument('--record_throughput_interval', type=int, default=1000,
                    help='The time interval between each throughput record')
parser.add_argument('--num_envs', type=int, default=1, help='The number of environment copies')
parser.add_argument('--ckpt_save_freq', type=int, default=3000, help='The number of updates between each weights saving')
parser.add_argument('--ckpt_save_type', type=str, default='weight', help='Type of checkpoint file')
parser.add_argument('--observation_space', type=int, default=(567,))
parser.add_argument('--action_space', type=int, default=(5, 216))
parser.add_argument('--epsilon', type=float, default=0.001)


def main():
    _init_tensorflow_session()

    args, unknown_args = parser.parse_known_args()
    unknown_args = parse_cmdline_kwargs(unknown_args)

    load_yaml_config(args, 'learner')

    context = zmq.Context()
    weights_socket = context.socket(zmq.PUB)
    weights_socket.bind(f'tcp://*:{args.param_port}')

    agent = get_agent(args, unknown_args)
    with open('./last.ckpt', 'rb') as f:
        weight = pickle.load(f)
    agent.set_weights(weight)
    print('Finetune Success')

    import datetime
    from pathlib import Path

    if args.exp_path is None:
        log_root = Path.cwd() / 'learner_log'
        log_root.mkdir(exist_ok=True)
        timestamp = datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H-%M-%S')
        args.exp_path = str(log_root / f'LEARNER-{timestamp}')
    create_experiment_dir(args, 'LEARNER-')
    save_yaml_config(args.exp_path / 'config.yaml', args, 'learner', agent)
    args.log_path = args.exp_path / 'log'
    args.ckpt_path = args.exp_path / 'ckpt'
    args.ckpt_path.mkdir()
    args.log_path.mkdir()

    logger.configure(str(args.log_path))

    receiving_condition = multiprocessing.Condition()
    num_receptions = multiprocessing.Value('i', 0)

    manager = MemPoolManager()
    manager.start()
    mem_pool = manager.MemPool(capacity=args.pool_size)
    Process(target=recv_data,
            args=(args.data_port, mem_pool, receiving_condition, num_receptions, args.keep_training)).start()

    Process(target=MultiprocessingMemPool.record_throughput, args=(mem_pool, args.record_throughput_interval)).start()

    model_save_freq = 0
    model_init_flag = 0
    log_times = 0
    while True:
        if model_init_flag == 0:
            weights_socket.send(pickle.dumps(agent.get_weights()))
            model_init_flag = 1

        if len(mem_pool) >= args.batch_size:
            weights = agent.get_weights()
            weights_socket.send(pickle.dumps(weights))

            if model_save_freq % args.ckpt_save_freq == 0:
                if args.ckpt_save_type == 'checkpoint':
                    agent.save(args.ckpt_path / 'ckpt')
                elif args.ckpt_save_type == 'weight':
                    with open(args.ckpt_path / f'adduniversal{model_save_freq}.ckpt', 'wb') as f:
                        pickle.dump(weights, f)

            if args.keep_training:
                agent.learn(mem_pool.sample(size=args.batch_size))
            else:
                with receiving_condition:
                    while num_receptions.value < args.training_freq:
                        receiving_condition.wait()
                    data = mem_pool.sample(size=args.batch_size)
                    num_receptions.value -= args.training_freq



                if log_times % 100 == 0:
                    print("\n[DEBUG] Training batch stats:")
                    for k, v in data.items():
                        print(f"  {k}: shape={v.shape}, mean={v.mean():.4f}, std={v.std():.4f}")

                old_weights_sample = agent.get_weights()[0][0, :5].copy()
                stat = agent.learn(data)
                new_weights_sample = agent.get_weights()[0][0, :5]
                print(f"[DEBUG] weight change = {np.abs(new_weights_sample - old_weights_sample).mean():.8f}")

            if log_times % 1000 == 0:
                weights = agent.get_weights()
                total_norm = sum(np.linalg.norm(w) for w in weights)
                print(f"[DEBUG] weights total norm = {total_norm:.4f}")
                stats = defaultdict(list)
                for k, v in stat.items():
                    stats[k].append(v)
                stat_mean = {k: np.array(v).mean() for k, v in stats.items()}
                if stat_mean:
                    for k, v in stat_mean.items():
                        logger.record_tabular(k, v)
                logger.dump_tabular()
            else:
                log_times += 1

            model_save_freq += 1


def recv_data(data_port, mem_pool, receiving_condition, num_receptions, keep_training):
    context = zmq.Context()
    data_socket = context.socket(zmq.REP)
    data_socket.bind(f'tcp://*:{data_port}')

    while True:
        data: dict = deserialize(data_socket.recv())
        data_socket.send(b'200')

        if keep_training:
            mem_pool.push(data)
        else:
            with receiving_condition:
                mem_pool.push(data)
                num_receptions.value += 1
                receiving_condition.notify()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()