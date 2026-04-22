import numpy as np
import tensorflow as tf
from tensorflow.keras.backend import get_session

#形成占位符: （length,None） 成为: (length,) or (length,shape)
def combined_shape(length, shape=None):
    if shape is None:
        return (length,)
    return (length, shape) if np.isscalar(shape) else (length, *shape)

#速创建一个 TensorFlow 占位符，第一个维度自动设为 None 返回值：一个 tf.placeholder 张量。
def placeholder(dtype=tf.float32, shape=None):
    return tf.placeholder(dtype=dtype, shape=combined_shape(None, shape))

#搭建多层全连接网络（MLP）MLP:突破了单层感知机只能拟合线性边界的局限，通过隐藏层+非线性激活函数，实现对任意复杂非线性函数的逼近
# hidden_sizes：是为了构建隐藏层的神经元的个数！
def mlp(x, hidden_sizes=(32,), activation=tf.tanh, output_activation=None):
    for h in hidden_sizes[:-1]:
        x = tf.layers.dense(x, units=h, activation=activation)  #x输入数据,units:神经元个数,激活函数
    return tf.layers.dense(x, units=hidden_sizes[-1], activation=output_activation)


class GDModel():
    def __init__(self, observation_space, action_space, config=None, model_id='0', session=None):
        with tf.variable_scope(model_id):  #给模型起个名字
            self.x_ph = placeholder(shape=observation_space)  #占位符 数据入口
            # self.z = placeholder(shape=action_space)
            # self.zero = placeholder(shape=128)

        # 输出张量
        self.values = None

        # Initialize Tensorflow session
        if session is None:
            session = get_session()
        self.sess = session

        self.scope = model_id
        self.observation_space = observation_space
        self.action_space = action_space
        self.model_id = model_id
        self.config = config

        # Set configurations
        if config is not None:
            self.load_config(config)

        # Build up model
        self.build()

        # Build assignment ops
        self._weight_ph = None
        self._to_assign = None
        self._nodes = None
        self._build_assign()

        # Build saver
        self.saver = tf.train.Saver(tf.trainable_variables())

        # 参数初始化
        self.sess.run(tf.global_variables_initializer())

    def set_weights(self, weights) -> None:
        feed_dict = {self._weight_ph[var.name]: weight
                     for (var, weight) in zip(tf.trainable_variables(self.scope), weights)}
        self.sess.run(self._nodes, feed_dict=feed_dict)

    def get_weights(self):
        return self.sess.run(tf.trainable_variables(self.scope))

    def save(self, path) -> None:
        self.saver.save(self.sess, str(path))

    def load(self, path) -> None:
        self.saver.restore(self.sess, str(path))

    def _build_assign(self):
        self._weight_ph, self._to_assign = dict(), dict()
        variables = tf.trainable_variables(self.scope)
        for var in variables:
            self._weight_ph[var.name] = tf.placeholder(var.value().dtype, var.get_shape().as_list())
            self._to_assign[var.name] = var.assign(self._weight_ph[var.name])
        self._nodes = list(self._to_assign.values())

    # def forward(self, x_batch, z):
    #     return self.sess.run(self.values, feed_dict={self.x_ph: x_batch, self.z: z})

    def forward(self, x_batch):
        return self.sess.run(self.values, feed_dict={self.x_ph: x_batch})

    # def forward(self, x_batch, z, zeros,*args, **kwargs):
    #     return self.sess.run(self.values, feed_dict={self.x_ph: x_batch, self.z: z, self.zero: zeros})

    # def build(self) -> None:
    #     with tf.variable_scope(self.scope):
    #         with tf.variable_scope('l1'):
    #             x = tf.unstack(self.z, 5, 1)
    #         with tf.variable_scope('l2'):
    #             lstm_cell = tf.contrib.rnn.BasicLSTMCell(128, forget_bias=1.0)
    #         with tf.variable_scope('l3'):
    #             outputs, _ = tf.contrib.rnn.static_rnn(lstm_cell, x, dtype=tf.float32)
    #             lstm_out = outputs[-1]
    #             x = tf.concat([lstm_out, self.x_ph], axis=-1)
    #         with tf.variable_scope('v'):
    #             self.values = mlp(x, [512, 512, 512, 512, 512, 1], activation='relu',
    #                                         output_activation=None)

    def build(self) -> None:
        with tf.variable_scope(self.scope):
            with tf.variable_scope('v'):
                self.values = mlp(self.x_ph, [512, 512, 512, 512, 512, 1], activation='tanh',
                                            output_activation=None)


    # def build(self) -> None:
    #     with tf.variable_scope(self.scope):
    #         with tf.variable_scope('l1'):
    #             x = tf.unstack(self.z, 5, 1)
    #         with tf.variable_scope('l2'):
    #             lstm_cell = tf.contrib.rnn.BasicLSTMCell(128, forget_bias=1.0)
    #         with tf.variable_scope('l3'):
    #             outputs, _ = tf.contrib.rnn.static_rnn(lstm_cell, x, dtype=tf.float32)
    #             #lstm_out = outputs[-1]
    #             #lstm_out = tf.zeros(outputs[-1].shape)
    #             x = tf.concat([self.zero, self.x_ph], axis=-1)
    #         with tf.variable_scope('v'):
    #             self.values = mlp(x, [512, 512, 512, 512, 512, 1], activation='elu',
    #                                         output_activation=None)
# import numpy as np
# import tensorflow as tf
# from tensorflow.keras.backend import get_session
#
#
#
#
#
# # 工具函数：拼接形状，比如把 (batch_size, 特征维度) 拼在一起
# def combined_shape(length, shape=None):
#     # 如果没有形状，直接返回长度 (batch,)
#     if shape is None:
#         return (length,)
#     # 如果是单个数字，返回 (length, shape)
#     # 如果是元组，返回 (length, *shape)
#     return (length, shape) if np.isscalar(shape) else (length, *shape)
#
#
# # 工具函数：创建占位符（网络的输入接口）
# def placeholder(dtype=tf.float32, shape=None):
#     # 第一个维度是 None，表示批次大小不固定，可以灵活喂数据
#     return tf.placeholder(dtype=dtype, shape=combined_shape(None, shape))
#
#
# # 工具函数：搭建全连接网络 MLP
# # x：输入
# # hidden_sizes：每层神经元数量，比如 [256,256,256,1]
# # activation：隐藏层激活函数
# # output_activation：输出层激活函数
# def mlp(x, hidden_sizes=(32,), activation=tf.nn.relu, output_activation=None):
#     # 遍历除最后一层以外的所有层
#     for h in hidden_sizes[:-1]:
#         # 增加一层全连接层
#         x = tf.layers.dense(x, units=h, activation=activation)
#     # 最后一层输出层
#     return tf.layers.dense(x, units=hidden_sizes[-1], activation=output_activation)
#
#
# # 核心类：Q 值网络模型
# class GDModel():
#     # 初始化
#     # observation_space：状态维度（输入大小）
#     # action_space：动作维度（这里没用到）
#     # model_id：模型名字，防止变量冲突
#     # session：TensorFlow 会话
#     def __init__(self, observation_space, action_space, config=None, model_id='0', session=None):
#         # 给模型创建独立命名空间
#         with tf.variable_scope(model_id):
#             # 创建输入占位符：接收游戏状态
#             self.x_ph = placeholder(shape=observation_space)
#
#         # 用来存网络输出：Q 值
#         self.values = None
#
#         # 如果没传会话，就自动获取一个
#         if session is None:
#             session = get_session()
#         self.sess = session
#
#         # 模型基本信息
#         self.scope = model_id
#         self.observation_space = observation_space
#         self.action_space = action_space
#         self.model_id = model_id
#         self.config = config
#
#         # 加载配置（这里是空函数，没用）
#         if config is not None:
#             self.load_config(config)
#
#         # 真正搭建网络结构
#         self.build()
#
#         # 初始化权重赋值相关的 op
#         self._weight_ph = None
#         self._to_assign = None
#         self._nodes = None
#         self._build_assign()
#
#         # 模型保存器
#         self.saver = tf.train.Saver(tf.trainable_variables())
#
#         # 初始化网络所有参数
#         self.sess.run(tf.global_variables_initializer())
#
#     # 直接设置模型权重（用于多进程、模型同步）
#     def set_weights(self, weights) -> None:
#         # 构造喂入字典：把权重放到占位符里
#         feed_dict = {self._weight_ph[var.name]: weight
#                      for (var, weight) in zip(tf.trainable_variables(self.scope), weights)}
#         # 执行赋值操作
#         self.sess.run(self._nodes, feed_dict=feed_dict)
#
#     # 获取当前模型所有权重
#     def get_weights(self):
#         return self.sess.run(tf.trainable_variables(self.scope))
#
#     # 保存模型到文件
#     def save(self, path) -> None:
#         self.saver.save(self.sess, str(path))
#
#     # 从文件加载模型
#     def load(self, path) -> None:
#         self.saver.restore(self.sess, str(path))
#
#     # 内部函数：构建权重赋值 op
#     def _build_assign(self):
#         self._weight_ph, self._to_assign = dict(), dict()
#         variables = tf.trainable_variables(self.scope)
#         for var in variables:
#             # 给每个权重创建一个占位符
#             self._weight_ph[var.name] = tf.placeholder(var.value().dtype, var.get_shape().as_list())
#             # 创建赋值操作
#             self._to_assign[var.name] = var.assign(self._weight_ph[var.name])
#         self._nodes = list(self._to_assign.values())
#
#     # 前向传播：输入状态，输出 Q 值
#     def forward(self, x_batch):
#         return self.sess.run(self.values, feed_dict={self.x_ph: x_batch})
#
#     # 构建网络结构（真正的 Q 网络）
#     def build(self) -> None:
#         with tf.variable_scope(self.scope):
#             with tf.variable_scope('v'):
#                 # 输入：self.x_ph（状态）
#                 # 网络结构：3层256 + 输出1个Q值
#                 # 激活：relu
#                 self.values = mlp(
#                     self.x_ph,
#                     [256, 256, 256, 1],
#                     activation=tf.nn.relu,
#                     output_activation=None
#                 )
#
#     # 加载配置（空实现）
#     def load_config(self, config: dict) -> None:
#         pass