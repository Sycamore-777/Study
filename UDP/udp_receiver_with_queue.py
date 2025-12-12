# -*- coding: utf-8 -*-
"""
udp_with_queue_full.py（框架版）
-------------------------------
框架思路：
    1. UDP 监听线程：
        - 只负责 recvfrom()
        - 把 (addr, raw_data, recv_time) 丢进线程安全队列

    2. 工作线程：
        - 从队列中取出原始报文
        - 调用 parse_full_datagram() 解析为 (MsgHeader, [RealtimePacket...])
        - 再把解析结果交给 “业务处理函数 handler(...)”

    3. 业务处理函数（可插拔）：
        - 签名统一：handler(addr, parsed, recv_time)
            - addr: (ip, port)
            - parsed: (header, packets)
            - recv_time: float 时间戳
        - 你可以写多个 handler（比如数据处理、日志版等），通过 main() 里传入不同 handler 切换行为。

当前默认业务逻辑：
    - 使用 example_func 当作案例函数，维护 history_state_by_id：
        key:   对象 ID (int)
        value: State = (State_01_prev, State_02_prev)
"""

import socket
import threading
import queue
import time
import logging
from typing import Tuple, Dict, Callable, Any

# 协议 & 数据结构 & 解析函数 TODO:根据协议按需修改
from udp_protocol_defs import (
    State_01,
    State_02,
    State,
    MsgHeader,
    RealtimePacket,
    ParsedDatagram,
    parse_full_datagram,
)

# =====================================================================
# 0. logging 配置
# =====================================================================

logging.basicConfig(
    filename="state_update.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# =====================================================================
# 1. 类型别名（框架相关）
# =====================================================================

# 时间戳：time.time() 的结果
Timestamp = float

# UDP 对端地址：(IP字符串, 端口号)
Address = Tuple[str, int]

# 工作队列中的任务项：(addr, raw_data, recv_time)
TaskItem = Tuple[Address, bytes, Timestamp]


# =====================================================================
# 3. 框架层：全局队列 + MessageHandler 类型
# =====================================================================

# 队列：监听线程 -> 工作线程 传递任务参数
task_queue: "queue.Queue[TaskItem]" = queue.Queue(maxsize=10000)

# 业务处理函数类型：addr, parsed_datagram, recv_time -> None
MessageHandler = Callable[[Address, ParsedDatagram, Timestamp], None]


# =====================================================================
# 4. 业务层：数据处理 handler + 状态字典
# =====================================================================

# 维护每个 ID 的“历史状态”
# key: ID, value: State = (State_01_prev, State_02_prev)
history_state_by_id: Dict[int, State] = {}


def data_handler(addr: Address, parsed: ParsedDatagram, recv_time: Timestamp) -> None:
    """
    数据处理业务处理函数（可换成你自己的 handler）：

    对每个有效 packet：
        1. 取出 ID 和当前 State_02
        2. 使用 history_state_by_id 维护上一拍 State = (State_01_prev, State_02_prev)
        3. 调用 example_func 做数据处理，例如把 State_02 前后对比计算变化
        4. 如果触发，则更新 history_state_by_id 并写日志
    """
    ip, port = addr
    header, packets = parsed

    package_num: int = header.PackageNumber  # 示例：使用头部的 PackageNumber
    state_01: State_01 = header.MsgState_01  # 示例：使用头部的 State_01

    for pkt in packets:
        # 只处理有效包
        if not pkt.IsValid:
            continue

        obj_id = pkt.ID
        state_02_current: State_02 = pkt.State_02

        # 如果是第一次看到该 ID，则初始化状态
        if obj_id not in history_state_by_id:
            history_state_by_id[obj_id] = (state_01, state_02_current)
            logger.info(
                f"[INIT] addr={ip}:{port}, ID={obj_id}, "
                f"state_01_init={state_01}, state_02_init={state_02_current}"
            )
            # 第一次只初始化，不进行对比，可以根据业务需要调整
            continue

        # 取出上一次记录状态
        state_01_prev, state_02_prev = history_state_by_id[obj_id]

        # 调用你的业务函数（示例：只对比 State_02）
        trigger: bool = example_func(
            state_02_current=state_02_current,
            state_02_prev=state_02_prev,
        )

        # 如果触发，就用当前 (state_01, state_02) 更新历史状态
        if trigger:
            history_state_by_id[obj_id] = (state_01, state_02_current)
            logger.info(
                f"[UPDATE] addr={ip}:{port}, ID={obj_id}, "
                f"state_02_prev={state_02_prev}, state_02_new={state_02_current}"
            )


# =====================================================================
# 5. 工作线程：从队列取任务 -> 解析 -> 调用 handler
# =====================================================================


def worker_loop(handler: MessageHandler) -> None:
    """
    工作线程主循环：

    不断从 task_queue 中取出 (addr, raw_data, recv_time)，然后：
        1. 调用 parse_full_datagram(raw_data)
        2. 把解析结果交给 handler(addr, parsed, recv_time)
    """
    print("[Worker] 工作线程启动。")
    logger.info("工作线程启动。")

    while True:
        # 从队列中取出任务参数（addr, raw_data, recv_time）
        addr, data, recv_time = task_queue.get()

        try:
            # 解析报文
            parsed = parse_full_datagram(data)
            # 调用业务处理函数
            handler(addr, parsed, recv_time)

        except Exception as e:
            print(f"[Worker][ERROR] 处理报文时出错: {e}")
            logger.error(f"[Worker][ERROR] 处理报文时出错: {e}", exc_info=True)
        finally:
            task_queue.task_done()


# =====================================================================
# 6. UDP 监听线程：只负责收包 + 丢队列
# =====================================================================


def udp_listener(host: str = "0.0.0.0", port: int = 5005) -> None:
    """
    UDP 监听线程函数：

    逻辑：
        1. 创建 UDP socket，并绑定 (host, port)
        2. 死循环 recvfrom()
        3. 每收到一包，就把 (addr, data, recv_time) 丢进队列
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))

    print(f"[Listener] 正在监听 UDP {host}:{port} ...")
    logger.info(f"UDP 监听线程启动，绑定 {host}:{port}")

    try:
        while True:
            data, addr = sock.recvfrom(8192 * 4)
            recv_time = time.time()
            ip, sport = addr
            print(f"[Listener] 收到来自 {ip}:{sport} 的报文，len={len(data)}")

            task: TaskItem = (addr, data, recv_time)
            try:
                task_queue.put(task, timeout=1.0)
            except queue.Full:
                print("[Listener][WARN] 队列已满，丢弃一个报文。")
                logger.warning("队列已满，丢弃一个报文。")

    except KeyboardInterrupt:
        print("\n[Listener] 收到中断信号，监听线程即将退出。")
        logger.info("监听线程收到 KeyboardInterrupt，将退出。")
    finally:
        sock.close()
        print("[Listener] socket 已关闭。")
        logger.info("监听 socket 已关闭。")


# =====================================================================
# 7. 主入口：启动线程并保持进程存活
# =====================================================================


def main() -> None:
    """
    主入口：

        1. 启动工作线程（传入你想用的 handler）
        2. 启动 UDP 监听线程
        3. 主线程挂起（sleep），等待 Ctrl+C 退出
    """
    # 1) 启动工作线程，指定业务处理函数，例如此处为 data_handler
    worker_thread = threading.Thread(
        target=worker_loop,
        args=(data_handler,),  # TODO: 这里可以换成其他 handler
        daemon=True,
    )
    worker_thread.start()

    # 2) 启动 UDP 监听线程
    listener_thread = threading.Thread(
        target=udp_listener,
        kwargs={"host": "0.0.0.0", "port": 5005},
        daemon=True,
    )
    listener_thread.start()

    print("[Main] 主线程启动完成，工作线程和监听线程已启动。")
    logger.info("主线程启动完成，工作线程和监听线程已启动。")

    try:
        # 主线程挂起，保持进程存活
        while True:
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[Main] 收到 Ctrl+C，主线程即将退出。")
        logger.info("主线程收到 KeyboardInterrupt，即将退出。")


if __name__ == "__main__":
    main()
