"""
示例业务函数，换成自己的逻辑即可
"""

from udp_protocol_defs import State_02


def example_func(
    state_02_current: State_02,
    state_02_prev: State_02,
) -> bool:
    """
    示例业务函数：对比前后两次 State_02，返回是否“触发”。

    这里先给一个非常简单的示例：
        - 计算当前状态与上次状态的欧氏距离
        - 如果差值超过一个阈值（例如 1.0），就认为“触发 True”

    TODO: 根据实际业务需要，修改函数参数和内部逻辑。
    """
    dx = state_02_current[0] - state_02_prev[0]
    dy = state_02_current[1] - state_02_prev[1]
    dz = state_02_current[2] - state_02_prev[2]
    dvx = state_02_current[3] - state_02_prev[3]
    dvy = state_02_current[4] - state_02_prev[4]
    dvz = state_02_current[5] - state_02_prev[5]

    diff_norm = (dx * dx + dy * dy + dz * dz + dvx * dvx + dvy * dvy + dvz * dvz) ** 0.5
    threshold = 0.0

    return diff_norm > threshold
