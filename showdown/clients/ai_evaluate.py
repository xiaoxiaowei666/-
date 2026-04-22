# ai_evaluate.py (循环单局版本)
import time
import subprocess
import sys
import argparse
import json
import os
import signal
from multiprocessing import Process, freeze_support

GAME_EXE = r"C:\Users\24704\Desktop\毕设\guandan_offline_v1006\windows\1.exe"
CONDA_ENV = "gg"

def run_ai(seat, difficulty, server_url):
    if difficulty == 'hard':
        script = 'client_ai.py'
    else:
        script = 'client_r2.py'
    cmd = [sys.executable, script, f'--seat={seat}', f'--server_url={server_url}']
    subprocess.run(cmd)

def play_one_game(team0_diff, team1_diff):

    subprocess.run("taskkill /f /im 1.exe", shell=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)  # 等待操作系统释放端口

    """启动服务器和客户端进行一局游戏，返回该局胜利数组 [v0,v1,v2,v3]"""
    server_url = "ws://127.0.0.1:23456/game/client"
    # 每局启动服务器（总局数=1）
    server = subprocess.Popen([GAME_EXE, "1"], shell=True)
    time.sleep(2)

    difficulties = [team0_diff, team1_diff, team0_diff, team1_diff]
    procs = []
    for seat in range(4):
        p = Process(target=run_ai, args=(seat, difficulties[seat], server_url))
        p.start()
        procs.append(p)
        time.sleep(1)

    # 等待服务器自行退出（假设单局结束会退出）或超时后强杀
    try:
        server.wait(timeout=60)   # 单局60秒足够
    except subprocess.TimeoutExpired:
        server.terminate()
        server.wait()

    # 确保所有客户端终止
    for p in procs:
        p.join(timeout=5)
        if p.is_alive():
            p.terminate()

    # 读取单局结果（由某个客户端写入临时文件）
    result_file = 'final_result.jsonl'
    if os.path.exists(result_file):
        with open(result_file, 'r') as f:
            data = json.load(f)
        os.remove(result_file)   # 删除单局文件，避免影响下一局
        return data['victoryNum']
    else:
        print("警告：未找到单局结果文件，本局视为无效")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--team0', choices=['easy','normal','hard'], default='hard')
    parser.add_argument('--team1', choices=['easy','normal','hard'], default='normal')
    parser.add_argument('--games', type=int, default=1000)
    args = parser.parse_args()

    total_victory = [0, 0, 0, 0]
    valid_games = 0

    for i in range(args.games):
        print(f"开始第 {i+1}/{args.games} 局...")
        victory = play_one_game(args.team0, args.team1)
        if victory:
            total_victory = [total_victory[j] + victory[j] for j in range(4)]
            valid_games += 1
        time.sleep(1)  # 间隔避免端口冲突

    team0_wins = total_victory[0] + total_victory[2]
    team1_wins = total_victory[1] + total_victory[3]

    print("\n===== 最终评估结果 =====")
    print(f"有效总局数: {valid_games}")
    print(f"队伍0 (座位0,2) 难度 {args.team0}: 胜场 {team0_wins}，胜率 {team0_wins/valid_games:.2%}" if valid_games else "无数据")
    print(f"队伍1 (座位1,3) 难度 {args.team1}: 胜场 {team1_wins}，胜率 {team1_wins/valid_games:.2%}" if valid_games else "无数据")

if __name__ == '__main__':
    freeze_support()
    main()