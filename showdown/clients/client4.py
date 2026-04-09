import json
from random import randint

import zmq
import websocket
from pyarrow import deserialize, serialize


class ExampleClient:
    def __init__(self, url):
        self.url = url
        self.ws = None
        # 初始化zmq
        self.context = zmq.Context()
        self.context.linger = 0
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f'tcp://localhost:{11003}')

        self.ws = websocket.WebSocketApp(
            url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )

    def on_open(self, ws):
        print("WebSocket opened")

    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket closed: {close_status_code} - {close_msg}")

    def on_message(self, ws, message):
        message = json.loads(message)
        print(message)
        # 传输给决策模块
        self.socket.send(serialize(message).to_buffer())
        # 收到决策
        act_index = deserialize(self.socket.recv())
        if "actionList" in message:
            self.ws.send(json.dumps({"actIndex": act_index}))


if __name__ == '__main__':
    try:
        client = ExampleClient('ws://127.0.0.1:23456/game/client3')
        client.ws.run_forever()
    except KeyboardInterrupt:
        client.ws.close()