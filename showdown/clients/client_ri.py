import json
import argparse
import websocket
from rule_make.action import Action
from rule_make.state import State

class ExampleClient:
    def __init__(self, url):
        self.url = url
        self.state = State("client4")
        self.action = Action("client4")
        self.ws = None

    def on_open(self, ws):
        print(f"WebSocket connected to {self.url}")

    def on_message(self, ws, message):
        # message 已经是字符串，无需转换
        msg = json.loads(message)
        print(msg)
        self.state.parse(msg)
        if "actionList" in msg:
            act_index = self.action.rule_parse(
                msg,   # 传递字典，与原代码一致
                self.state._myPos,
                self.state.remain_cards,
                self.state.history,
                self.state.remain_cards_classbynum,
                self.state.pass_num,
                self.state.my_pass_num,
                self.state.tribute_result
            )
            # 发送动作索引，注意使用 ws.send 而不是 self.send
            ws.send(json.dumps({"actIndex": act_index}))

    def on_error(self, ws, error):
        print("Error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        print("Closed down", close_status_code, close_msg)

    def connect(self):
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='规则模式掼蛋AI客户端')
    parser.add_argument('--seat', type=int, required=True, help='座位号 (0-3)')
    parser.add_argument('--server_url', type=str, default='ws://127.0.0.1:23456/game/client',
                        help='服务器基础URL，默认 ws://127.0.0.1:23456/game/client')
    args = parser.parse_args()

    full_url = f"{args.server_url}{args.seat}"
    try:
        client = ExampleClient(full_url)
        client.connect()
    except KeyboardInterrupt:
        if client.ws:
            client.ws.close()