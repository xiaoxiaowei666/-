import subprocess
import time
import socket

GAME_EXE = r"C:\Users\24704\Desktop\毕设\guandan_offline_v1006\windows\1.exe"
GAME_PY = r"C:\Users\24704\Desktop\毕设\guandan_mcc-main\guandan_mcc-main\rl-frame\actor_n\game.py"
CONDA_ENV = "gg"
PYTHON_CMD = f"conda run -n {CONDA_ENV} python"


def kill_process_on_port(port):
    """查找占用端口的进程并强制结束"""
    result = subprocess.run(f'netstat -ano | findstr :{port}', shell=True, capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if 'LISTENING' in line:
            pid = line.strip().split()[-1]
            if pid.isdigit():
                subprocess.run(f'taskkill /F /PID {pid}', shell=True)
                time.sleep(1)

def run_once():
    print("Starting game server...")
    server = subprocess.Popen([GAME_EXE, "100"], shell=True)
    time.sleep(2)
    print("Starting game client...")
    client = subprocess.Popen(f"{PYTHON_CMD} {GAME_PY}", shell=True)

    print("Waiting 60 seconds for one game...")
    time.sleep(60)

    print("Time's up. Terminating server and client...")
    # 强制结束服务器进程
    server.kill()
    server.wait()
    # 额外确保端口上的进程被杀死
    kill_process_on_port(23456)

    # 终止客户端
    if client.poll() is None:
        client.terminate()
        client.wait()

    print("Restarting in 2 seconds...\n")
    time.sleep(2)

if __name__ == "__main__":
    while True:
        run_once()