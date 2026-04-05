import datetime
import os
import pickle
import re
import shutil
import time
from itertools import count
from pathlib import Path
from typing import Any, Tuple

import zmq


def _ckpt_sort_key(filename: str) -> int:
    """支持纯数字命名或 adduniversal3000 等带前缀的权重文件名。"""
    stem = Path(filename).stem
    if stem.isdigit():
        return int(stem)
    parts = re.findall(r'\d+', stem)
    return int(parts[-1]) if parts else 0


def find_new_weights(current_model_id: int, ckpt_path: Path) -> Tuple[Any, int]:
    try:
        names = [p for p in os.listdir(ckpt_path) if p.endswith('.ckpt')]
        ckpt_files = sorted(names, key=_ckpt_sort_key)
        latest_file = ckpt_files[-1]
    except IndexError:
        # No checkpoint file
        return None, -1
    new_model_id = _ckpt_sort_key(latest_file)

    if int(new_model_id) > current_model_id:
        loaded = False
        while not loaded:
            try:
                with open(ckpt_path / latest_file, 'rb') as f:
                    new_weights = pickle.load(f)
                loaded = True
            except (EOFError, pickle.UnpicklingError):
                # The file of weights does not finish writing
                pass

        return new_weights, new_model_id
    else:
        return None, current_model_id


def create_experiment_dir(args, prefix: str) -> None:
    if args.exp_path is None:
        args.exp_path = prefix + datetime.datetime.fromtimestamp(time.time()).strftime('%Y-%m-%d-%H-%M-%S')
    args.exp_path = Path(args.exp_path)

    if args.exp_path.exists():
        shutil.rmtree(args.exp_path, ignore_errors=True)
        # raise FileExistsError(f'Experiment directory {str(args.exp_path)!r} already exists')

    args.exp_path.mkdir()


def run_weights_subscriber(args, unknown_args):
    """Subscribe weights from Learner and save them locally"""
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect(f'tcp://{args.ip}:{args.param_port}')
    socket.setsockopt_string(zmq.SUBSCRIBE, '')  # Subscribe everything
    for model_id in count(1):  # Starts from 1
        while True:
            try:
                weights = socket.recv(flags=zmq.NOBLOCK)
                # Weights received
                with open(args.ckpt_path / f'{model_id}.ckpt', 'wb') as f:
                    f.write(weights)

                if model_id > args.num_saved_ckpt:
                    os.remove(args.ckpt_path / f'{model_id - args.num_saved_ckpt}.ckpt')
                break
            except zmq.Again:
                pass

            # For not cpu-intensive
            time.sleep(1)
