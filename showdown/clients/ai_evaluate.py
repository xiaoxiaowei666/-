# ai_evaluate.py
import time
import subprocess
import sys
import argparse
import json
import os
from multiprocessing import Process, freeze_support

GAME_EXE = r"C:\Users\24704\Desktop\毕设\guandan_offline_v1006\windows\1.exe"
CONDA_ENV = "gg"
PYTHON_CMD = f"conda run -n {CONDA_ENV} python"

def run_ai(seat, difficulty, server_url, result_file):
    """启动单个AI客户端进程"""
    if difficulty == 'hard':
        script = 'client_ai.py'
    else:
        script = 'client_ri.py'

    cmd = [
        sys.executable, script,
        f'--seat={seat}',
        f'--server_url={server_url}',
    ]
    # 只有座位0才传递结果文件参数
    if seat == 0 and result_file:
        cmd.append(f'--result_file={result_file}')

    subprocess.run(cmd)

def start_game(team0_diff, team1_diff, total_games, result_file):
    """启动游戏服务器和四个客户端，等待结束"""
    server_url = "ws://127.0.0.1:23456/game/client"

    print(f"启动游戏服务器，总局数: {total_games}")
    server = subprocess.Popen([GAME_EXE, str(total_games)], shell=True)
    time.sleep(3)  # 等待服务器初始化

    # 座位难度分配：0,2 为队伍0；1,3 为队伍1
    difficulties = [
        team0_diff,  # 座位0
        team1_diff,  # 座位1
        team0_diff,  # 座位2
        team1_diff   # 座位3
    ]

    procs = []
    for seat in range(4):
        p = Process(target=run_ai, args=(seat, difficulties[seat], server_url, result_file))
        p.start()
        procs.append(p)
        time.sleep(1)

    # 等待服务器进程结束（所有局数打完）
    server.wait()
    print("游戏服务器已退出。")

    # 等待客户端进程自然结束（通常随服务器断开而退出）
    for p in procs:
        p.join(timeout=5)

def analyze_results(result_file, total_games, team0_diff, team1_diff):
    """读取结果文件并计算胜率"""
    if not os.path.exists(result_file):
        print("错误：未找到结果文件，游戏可能未正常结束。")
        return

    with open(result_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    if not lines:
        print("结果文件为空。")
        return

    # 最后一行即为所有局数结束后的累计胜利次数
    final_data = json.loads(lines[-1])
    victory = final_data['victoryNum']

    team0_wins = victory[0] + victory[2]
    team1_wins = victory[1] + victory[3]

    print("\n===== 评估结果 =====")
    print(f"总局数: {total_games}")
    print(f"队伍0 (座位0,2) 难度 {team0_diff}: 胜场 {team0_wins}，胜率 {team0_wins/total_games:.2%}")
    print(f"队伍1 (座位1,3) 难度 {team1_diff}: 胜场 {team1_wins}，胜率 {team1_wins/total_games:.2%}")

def main():
    parser = argparse.ArgumentParser(description='掼蛋AI对抗评估工具')
    parser.add_argument('--team0', choices=['easy','normal','hard'], default='normal',
                        help='队伍0 (座位0,2) 的难度')
    parser.add_argument('--team1', choices=['easy','normal','hard'], default='normal',
                        help='队伍1 (座位1,3) 的难度')
    parser.add_argument('--games', type=int, default=1000,
                        help='总局数')
    parser.add_argument('--result_file', type=str, default='game_results.jsonl',
                        help='结果记录文件路径')
    args = parser.parse_args()

    # 删除旧结果文件
    if os.path.exists(args.result_file):
        os.remove(args.result_file)

    start_game(args.team0, args.team1, args.games, args.result_file)
    analyze_results(args.result_file, args.games, args.team0, args.team1)

if __name__ == '__main__':
    freeze_support()
    main()