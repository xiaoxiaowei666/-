# from typing import Any, Dict
#
# import models.utils as utils
# import numpy as np
# import tensorflow as tf
# from agents import agent_registry
# from core import Agent
# from tensorflow.train import AdamOptimizer
#
#
# @agent_registry.register('MC')
# class MCAgent(Agent):
#     def __init__(self, model_cls, observation_space, action_space, config=None, lr=0.01,
#                  *args, **kwargs):
#         # Define parameters
#         self.lr = lr
#         self.lamda = 0.65
#
#         self.policy_model = None
#         self.loss = None
#         self.train_q = None
#
#         self.target_ph = utils.placeholder(shape=(1))
#         self.old_q = utils.placeholder(shape=(1))
#
#         super(MCAgent, self).__init__(model_cls, observation_space, action_space, config, *args, **kwargs)
#
#     # def build(self) -> None:
#     #     self.policy_model = self.model_instances[0]
#     #     cliped_q = tf.clip_by_value(self.old_q / self.policy_model.values, 1-self.lamda, 1+self.lamda)
#     #     self.loss = tf.reduce_mean((cliped_q - self.target_ph) ** 2)
#     #     self.train_q = tf.train.RMSPropOptimizer(learning_rate=self.lr, epsilon=1e-5).minimize(self.loss)
#     #     self.policy_model.sess.run(tf.global_variables_initializer())
#     # def build(self) -> None:
#     #     self.policy_model = self.model_instances[0]
#     #     # 标准 MSE 损失：让 Q 值逼近目标回报
#     #     self.loss = tf.reduce_mean(tf.square(self.policy_model.values - self.target_ph))
#     #     # 优化器可以保持 RMSProp，也可尝试 Adam
#     #     self.train_q = tf.train.RMSPropOptimizer(learning_rate=self.lr, epsilon=1e-5).minimize(self.loss)
#     #     self.policy_model.sess.run(tf.global_variables_initializer())
#     #     # 添加下面两行
#     #     grads = optimizer.compute_gradients(self.loss)
#     #     self.grad_norm = tf.global_norm([g for g, _ in grads if g is not None])
#     def build(self) -> None:
#         self.policy_model = self.model_instances[0]
#         self.loss = tf.reduce_mean(tf.square(self.policy_model.values - self.target_ph))
#
#         # 显式创建优化器对象
#         optimizer = tf.train.AdamOptimizer(learning_rate=self.lr)  # 替换RMSProp
#         self.train_q = optimizer.minimize(self.loss)
#
#         # 计算梯度范数（关键）
#         grads = optimizer.compute_gradients(self.loss)
#         self.grad_norm = tf.global_norm([g for g, _ in grads if g is not None])
#
#         self.policy_model.sess.run(tf.global_variables_initializer())
#
#     # def learn(self, training_data: Dict[str, np.ndarray], *args, **kwargs) -> None:
#     #     x_no_action, action, q, reward = [training_data[key] for key in ['x_no_action', 'action', 'q', 'reward']]
#     #     x_batch = np.concatenate([x_no_action, action], axis=-1)
#     #
#     #     _, loss, values = self.policy_model.sess.run([self.train_q, self.loss, self.policy_model.values],
#     #             feed_dict={
#     #                 self.policy_model.x_ph: x_batch,
#     #                 self.old_q: q,
#     #                 self.target_ph: reward})
#     #     return {
#     #         'loss': loss,
#     #         'values': values
#     #     }
#
#     # def learn(self, training_data: Dict[str, np.ndarray], *args, **kwargs) -> None:
#     #     # 假设 training_data 包含 'x_no_action', 'action', 'reward'（可能还有 'q'，忽略即可）
#     #     x_no_action, action, reward = [training_data[key] for key in ['x_no_action', 'action', 'reward']]
#     #     x_batch = np.concatenate([x_no_action, action], axis=-1)
#     #
#     #     _, loss, values = self.policy_model.sess.run(
#     #         [self.train_q, self.loss, self.policy_model.values],
#     #         feed_dict={
#     #             self.policy_model.x_ph: x_batch,
#     #             self.target_ph: reward  # 直接用 reward 作为监督信号
#     #         }
#     #     )
#     #     # 添加调试打印
#     #     print(f"[DEBUG] loss = {loss:.6f}, pred_mean = {values.mean():.4f}, pred_std = {values.std():.4f}, "
#     #           f"target_mean = {reward.mean():.4f}, target_std = {reward.std():.4f}")
#     #
#     #     return {'loss': loss, 'values': values}
#     #     #return {'loss': loss, 'values': values}
#     def learn(self, training_data: Dict[str, np.ndarray], *args, **kwargs) -> None:
#         x_no_action, action, reward = [training_data[key] for key in ['x_no_action', 'action', 'reward']]
#         x_batch = np.concatenate([x_no_action, action], axis=-1)
#
#         # 同时运行 train_op, loss, values, grad_norm
#         _, loss, values, grad_norm = self.policy_model.sess.run(
#             [self.train_q, self.loss, self.policy_model.values, self.grad_norm],
#             feed_dict={
#                 self.policy_model.x_ph: x_batch,
#                 self.target_ph: reward
#             }
#         )
#
#         # 打印关键信息
#         print(f"[DEBUG] loss = {loss:.6f}, grad_norm = {grad_norm:.6f}, "
#               f"pred_mean = {values.mean():.4f}, target_mean = {reward.mean():.4f}")
#
#         return {'loss': loss, 'values': values}
#
#     def set_weights(self, weights, *args, **kwargs) -> None:
#         self.policy_model.set_weights(weights)
#
#     def get_weights(self, *args, **kwargs) -> Any:
#         return self.policy_model.get_weights()
#
#     def save(self, path, *args, **kwargs) -> None:
#         self.policy_model.save(path)
#
#     def load(self, path, *args, **kwargs) -> None:
#         self.policy_model.load(path)
#
#
#
# # deeepseek修改方案:
#
# # agents/guandan_agent.py
#
# # agents/guandan_agent.py
#
# # from typing import Any, Dict
# #
# # import models.utils as utils
# # import numpy as np
# # import tensorflow as tf
# # from agents import agent_registry
# # from core import Agent
# #
# #
# # @agent_registry.register('MC')
# # class MCAgent(Agent):
# #     def __init__(self, model_cls, observation_space, action_space, config=None, lr=1e-4,  # 修改：降低学习率
# #                  *args, **kwargs):
# #         self.lr = lr
# #         self.lamda = 0.65
# #
# #         self.policy_model = None
# #         self.loss = None
# #         self.train_q = None
# #
# #         self.target_ph = utils.placeholder(shape=(1))
# #         self.old_q = utils.placeholder(shape=(1))
# #
# #         super(MCAgent, self).__init__(model_cls, observation_space, action_space, config, *args, **kwargs)
# #
# #     def build(self) -> None:
# #         self.policy_model = self.model_instances[0]
# #         self.loss = tf.reduce_mean(tf.square(self.policy_model.values - self.target_ph))
# #
# #         # ---------- 修改处：梯度裁剪 ----------
# #         optimizer = tf.train.AdamOptimizer(learning_rate=self.lr)
# #
# #         # 计算梯度
# #         grads_and_vars = optimizer.compute_gradients(self.loss)
# #         # 对梯度进行裁剪，限制全局范数不超过 1.0
# #         capped_grads_and_vars = [
# #             (tf.clip_by_norm(g, 1.0), v) if g is not None else (g, v)
# #             for g, v in grads_and_vars
# #         ]
# #         self.train_q = optimizer.apply_gradients(capped_grads_and_vars)
# #
# #         # 计算梯度范数（用于调试）
# #         self.grad_norm = tf.global_norm([g for g, _ in grads_and_vars if g is not None])
# #
# #         self.policy_model.sess.run(tf.global_variables_initializer())
# #
# #     def learn(self, training_data: Dict[str, np.ndarray], *args, **kwargs) -> None:
# #         x_no_action, action, reward = [training_data[key] for key in ['x_no_action', 'action', 'reward']]
# #         x_batch = np.concatenate([x_no_action, action], axis=-1)
# #
# #         # ---------- 修改处：对 reward 做标准化（在 learner.py 中已处理，此处不再重复） ----------
# #         # 标准化操作移至 learner.py 中统一进行，这里直接使用已标准化的 reward
# #
# #         _, loss, values, grad_norm = self.policy_model.sess.run(
# #             [self.train_q, self.loss, self.policy_model.values, self.grad_norm],
# #             feed_dict={
# #                 self.policy_model.x_ph: x_batch,
# #                 self.target_ph: reward
# #             }
# #         )
# #
# #         print(f"[DEBUG] loss = {loss:.6f}, grad_norm = {grad_norm:.6f}, "
# #               f"pred_mean = {values.mean():.4f}, target_mean = {reward.mean():.4f}")
# #
# #         return {'loss': loss, 'values': values}
# #
# #     def set_weights(self, weights, *args, **kwargs) -> None:
# #         self.policy_model.set_weights(weights)
# #
# #     def get_weights(self, *args, **kwargs) -> Any:
# #         return self.policy_model.get_weights()
# #
# #     def save(self, path, *args, **kwargs) -> None:
# #         self.policy_model.save(path)
# #
# #     def load(self, path, *args, **kwargs) -> None:
# #         self.policy_model.load(path)

from typing import Any, Dict

import models.utils as utils
import numpy as np
import tensorflow as tf
from agents import agent_registry
from core import Agent


@agent_registry.register('MC')
class MCAgent(Agent):
    def __init__(self, model_cls, observation_space, action_space, config=None, lr=1e-4,  # 降低学习率
                 *args, **kwargs):
        self.lr = lr
        self.lamda = 0.65

        self.policy_model = None
        self.loss = None
        self.train_q = None

        self.target_ph = utils.placeholder(shape=(1))
        self.old_q = utils.placeholder(shape=(1))

        super(MCAgent, self).__init__(model_cls, observation_space, action_space, config, *args, **kwargs)

    def build(self) -> None:
        self.policy_model = self.model_instances[0]
        self.loss = tf.reduce_mean(tf.square(self.policy_model.values - self.target_ph))

        # 使用 Adam 优化器，并添加梯度裁剪
        optimizer = tf.train.AdamOptimizer(learning_rate=self.lr)
        grads_and_vars = optimizer.compute_gradients(self.loss)

        # 全局梯度裁剪，限制范数不超过 1.0
        capped_grads_and_vars = [
            (tf.clip_by_norm(g, 1.0), v) if g is not None else (g, v)
            for g, v in grads_and_vars
        ]
        self.train_q = optimizer.apply_gradients(capped_grads_and_vars)

        # 记录梯度范数用于调试
        self.grad_norm = tf.global_norm([g for g, _ in grads_and_vars if g is not None])

        self.policy_model.sess.run(tf.global_variables_initializer())

    def learn(self, training_data: Dict[str, np.ndarray], *args, **kwargs) -> None:
        x_no_action, action, reward = [training_data[key] for key in ['x_no_action', 'action', 'reward']]
        x_batch = np.concatenate([x_no_action, action], axis=-1)

        _, loss, values, grad_norm = self.policy_model.sess.run(
            [self.train_q, self.loss, self.policy_model.values, self.grad_norm],
            feed_dict={
                self.policy_model.x_ph: x_batch,
                self.target_ph: reward
            }
        )

        print(f"[DEBUG] loss = {loss:.6f}, grad_norm = {grad_norm:.6f}, "
              f"pred_mean = {values.mean():.4f}, target_mean = {reward.mean():.4f}")

        return {'loss': loss, 'values': values}

    def set_weights(self, weights, *args, **kwargs) -> None:
        self.policy_model.set_weights(weights)

    def get_weights(self, *args, **kwargs) -> Any:
        return self.policy_model.get_weights()

    def save(self, path, *args, **kwargs) -> None:
        self.policy_model.save(path)

    def load(self, path, *args, **kwargs) -> None:
        self.policy_model.load(path)