# main.py
import subprocess
import sys
import tkinter as tk
import time
from tkinter import ttk
from multiprocessing import Process, freeze_support


def start_game(difficulties):
    """启动游戏服务器和客户端"""
    server_url = "ws://127.0.0.1:23456/game/client"  # 基础 URL

    GAME_EXE = r"C:\Users\24704\Desktop\毕设\guandan_offline_v1006\windows\1.exe"
    CONDA_ENV = "gg"
    PYTHON_CMD = f"conda run -n {CONDA_ENV} python"
    print("Starting game server...")
    server = subprocess.Popen([GAME_EXE, "100"], shell=True)
    time.sleep(2)

    # 启动三个 AI 客户端子进程（座位 0,1,2）
    ai_procs = []
    for seat in range(3):
        diff = difficulties[seat]
        proc = Process(target=run_ai, args=(seat, diff, server_url))
        proc.start()
        ai_procs.append(proc)

    # 启动玩家客户端（座位 3）
    run_player(seat=3, server_url=server_url)


def run_ai(seat, difficulty, server_url):
    """根据难度选择对应的 AI 客户端脚本"""
    if difficulty == 'hard':
        script = 'client_ai.py'  # 深度学习模型客户端
    elif difficulty == 'normal':
        script = 'client_ri.py'  # 规则客户端（中等难度）
    else:  # easy
        script = 'client_r2.py'  # 规则客户端（简单难度）

    cmd = [
        sys.executable, script,
        f'--seat={seat}',
        f'--server_url={server_url}'
    ]
    # 如果需要为 hard 模式指定权重文件，可以取消下面的注释
    # if difficulty == 'hard':
    #     cmd.extend(['--weights', 'dan.ckpt'])
    subprocess.run(cmd)


def run_player(seat, server_url):
    """运行玩家客户端（在当前进程）"""
    from client_player import PlayerGame
    url = f"{server_url}{seat}"
    game = PlayerGame(seat, url)
    game.run()


def main():
    root = tk.Tk()
    root.title("选择 AI 难度")
    root.geometry("400x300")

    tk.Label(root, text="请选择三个 AI 的难度").pack(pady=10)

    difficulties = []
    for i in range(3):
        frame = tk.Frame(root)
        frame.pack(pady=5)
        tk.Label(frame, text=f"AI {i} 座位 {i}").pack(side=tk.LEFT, padx=10)
        combo = ttk.Combobox(frame, values=['easy', 'normal', 'hard'], state='readonly')
        combo.set('normal')
        combo.pack(side=tk.LEFT)
        difficulties.append(combo)

    def on_start():
        selected = [cb.get() for cb in difficulties]
        root.destroy()
        start_game(selected)

    tk.Button(root, text="开始游戏", command=on_start, bg="green", fg="white").pack(pady=20)

    root.mainloop()


if __name__ == '__main__':
    freeze_support()
    main()