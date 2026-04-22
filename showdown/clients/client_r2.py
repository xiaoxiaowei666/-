# -*- coding: utf-8 -*-
# @Time       : 2020/10/1 16:30
# @Author     : Duofeng Wu
# @File       : client.py
# @Description:

import json
import argparse
import websocket
import ast
from r2_make.state import State
from r2_make.action import Action


class ExampleClient:
    def __init__(self, url):
        self.url = url
        self.state = State("client1")
        self.action = Action("client1")
        self.ws = None

    def on_open(self, ws):
        """连接打开时调用"""
        pass

    def on_message(self, ws, message):
        """收到消息时自动调用"""

        message = json.loads(message)

        # 修复 message 字典，将字符串类型的 curAction/greaterAction 转为列表
        if "curAction" in message and isinstance(message["curAction"], str):
            try:
                message["curAction"] = ast.literal_eval(message["curAction"])
            except (SyntaxError, ValueError):
                pass

        if "greaterAction" in message and isinstance(message["greaterAction"], str):
            try:
                message["greaterAction"] = ast.literal_eval(message["greaterAction"])
            except (SyntaxError, ValueError):
                pass

        self.state.parse(message)

        if "actionList" in message:
            act_index = self.action.rule_parse(
                message,
                self.state._myPos,
                self.state.remain_cards,
                self.state.history,
                self.state.remain_cards_classbynum,
                self.state.pass_num,
                self.state.my_pass_num,
                self.state.tribute_result
            )
            ws.send(json.dumps({"actIndex": act_index}))

    def on_error(self, ws, error):
        """报错时调用"""
        print("Error:", error)

    def on_close(self, ws, close_status_code, close_msg):
        """连接关闭时调用"""
        print("Closed down", close_status_code, close_msg)

    def connect(self):
        """启动连接"""
        self.ws = websocket.WebSocketApp(
            self.url,
            on_open=self.on_open,
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

    def close(self):
        """手动关闭连接"""
        self.ws.close()


if __name__ == '__main__':
    # 命令行参数
    parser = argparse.ArgumentParser(description='规则模式掼蛋AI客户端')
    parser.add_argument('--seat', type=int, required=True, help='座位号 (0-3)')
    parser.add_argument('--server_url', type=str, default='ws://127.0.0.1:23456/game/client',
                        help='服务器基础URL，默认 ws://127.0.0.1:23456/game/client')
    args = parser.parse_args()

    # 拼接最终 URL
    full_url = f"{args.server_url}{args.seat}"

    try:
        client = ExampleClient(full_url)
        client.connect()
    except KeyboardInterrupt:
        client.close()