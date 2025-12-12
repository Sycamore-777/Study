# -*- coding: utf-8 -*-
"""
udp_sender_generic.py
---------------------
通用 UDP 发送端，用于给 udp_with_queue_full.py 发送测试/业务报文。

设计思路：
    1. 复用 udp_protocol_defs.py 中的协议定义：
        - MsgHeader / RealtimePacket / State_01 / State_02
        - HEADER_STRUCT / PACKET_STRUCT / PACKET_SIZE

    2. 提供“构造报文”的通用函数：
        - build_header(...)
        - build_packet_bytes(...)
        - build_datagram(...)

    3. 提供一个简单的 main():
        - 根据命令行参数，周期性构造报文并通过 UDP 发送出去
        - 你可以把“构造包内容”的逻辑替换成自己的业务数据

使用方式：
    1) 确保 udp_protocol_defs.py 在同一目录下，且定义了协议结构。
    2) 运行发送端，例如：
        python udp_sender_generic.py --host 127.0.0.1 --port 5005 --num-packets 3 --interval 1.0
"""

import socket
import time
import random
import argparse
from typing import List, Tuple

from udp_protocol_defs import (
    State_01,
    State_02,
    MsgHeader,
    RealtimePacket,
    HEADER_STRUCT,
    PACKET_STRUCT,
    PACKET_SIZE,
)

# =====================================================================
# 1. 工具函数：构造 header / packet / 整个 datagram
# =====================================================================


# TODO: 可选的基础函数，仅仅为了构造State_01，为了后续能正常运行，根据实际情况修订
def get_current_state_01() -> State_01:
    """
    示例：获取当前时间构造 State_01。
    这里用本地时间，你也可以根据需要改为 UTC 时间。
    """
    tm = time.localtime()  # time.struct_time
    # year, month, day, hour, minute, second 全部转为 float，适配 State_01 类型
    return (
        float(tm.tm_year),
        float(tm.tm_mon),
        float(tm.tm_mday),
        float(tm.tm_hour),
        float(tm.tm_min),
        float(tm.tm_sec),
    )


# TODO: 依据数据头定义的数据类型构造数据头参数，按需调整
def build_header(msg_type: int, state_01: State_01, package_number: int) -> MsgHeader:
    """
    构造 MsgHeader dataclass 实例。
    PackageLength 统一使用 PACKET_SIZE。
    """
    return MsgHeader(
        MsgType=msg_type,
        MsgState_01=state_01,
        PackageNumber=package_number,
        PackageLength=PACKET_SIZE,
    )


# TODO: 可选的基础函数，仅仅为了将字符串转换成固定长度的数组，为了后续能正常运行，根据实际情况修订
def encode_name(name: str, length: int = 64) -> bytes:
    """
    把 Python 字符串编码成协议里固定长度的 char 数组。

    规则：
        - 使用 UTF-8 编码
        - 如果超过 length 字节，截断
        - 不足则用 \x00 填充
    """
    raw = name.encode("utf-8", errors="ignore")
    if len(raw) > length:
        return raw[:length]
    return raw.ljust(length, b"\x00")


# TODO: 构造单个数据包，根据实际情况修订
def build_packet_bytes(pkt: RealtimePacket) -> bytes:
    """
    把 RealtimePacket dataclass 实例打包成二进制 bytes。
    """
    # Name 字段需要先转成 64 字节的 bytes
    name_bytes = encode_name(pkt.Name, length=64)
    a, b, c, d, e, f = pkt.State_02

    # PACKET_STRUCT 定义为：<?ii64s6d>
    packed = PACKET_STRUCT.pack(
        pkt.IsValid,
        pkt.ID,
        pkt.ParentID,
        name_bytes,
        a,
        b,
        c,
        d,
        e,
        f,
    )
    return packed


# TODO: 构造数据头，根据实际情况修订
def build_header_bytes(header: MsgHeader) -> bytes:
    """
    把 MsgHeader dataclass 实例打包成二进制 bytes。
    HEADER_STRUCT 定义为：<i6dii
    """
    year, month, day, hour, minute, second = header.MsgState_01
    packed = HEADER_STRUCT.pack(
        header.MsgType,
        year,
        month,
        day,
        hour,
        minute,
        second,
        header.PackageNumber,
        header.PackageLength,
    )
    return packed


# TODO: 构建完整的数据
def build_datagram(msg_type: int, packets: List[RealtimePacket]) -> bytes:
    """
    构造完整 UDP 报文：
        [Header] + [Packet_1] + [Packet_2] + ... + [Packet_N]
    """
    state_01 = get_current_state_01()
    header = build_header(
        msg_type=msg_type, state_01=state_01, package_number=len(packets)
    )

    header_bytes = build_header_bytes(header)
    packet_bytes_list = [build_packet_bytes(pkt) for pkt in packets]

    return header_bytes + b"".join(packet_bytes_list)


# =====================================================================
# 2. 示例：构造一批“示例 RealtimePacket”
# =====================================================================


def make_example_state_02(base: float = 0.0) -> State_02:
    """
    构造一个示例 State_02。
    这里用 base 做一个简单偏移，方便你观察不同包的差异。

    TODO: 根据业务需要改成更真实的数据。
    """
    return (
        base + random.uniform(-1.0, 1.0),
        base + random.uniform(-1.0, 1.0),
        base + random.uniform(-1.0, 1.0),
        base + random.uniform(-0.1, 0.1),
        base + random.uniform(-0.1, 0.1),
        base + random.uniform(-0.1, 0.1),
    )


def make_example_packets(
    num_packets: int,
    id_start: int = 1,
    name_prefix: str = "Obj",
) -> List[RealtimePacket]:
    """
    构造 num_packets 个示例 RealtimePacket。

    每个包：
        - IsValid = True
        - ID       = id_start + i
        - ParentID = 0（或随便一个值）
        - Name     = f"{name_prefix}_{ID}"
        - State_02 = make_example_state_02(base=ID)
    """
    packets: List[RealtimePacket] = []

    for i in range(num_packets):
        obj_id = id_start + i
        state_02 = make_example_state_02(base=float(obj_id))

        pkt = RealtimePacket(
            IsValid=True,
            ID=obj_id,
            ParentID=0,
            Name=f"{name_prefix}_{obj_id}",
            State_02=state_02,
        )
        packets.append(pkt)

    return packets


# =====================================================================
# 3. 发送函数
# =====================================================================


def send_datagram(
    sock: socket.socket,
    target: Tuple[str, int],
    datagram: bytes,
) -> None:
    """
    使用给定 socket，将 datagram 发送到 target (host, port)。
    """
    sock.sendto(datagram, target)


# =====================================================================
# 4. main：命令行参数 + 周期性发送
# =====================================================================


def main() -> None:
    parser = argparse.ArgumentParser(
        description="通用 UDP 发送端（适配 udp_protocol_defs 协议）"
    )
    parser.add_argument("--host", type=str, default="127.0.0.1", help="目标 IP 地址")
    parser.add_argument("--port", type=int, default=5005, help="目标端口")
    parser.add_argument(
        "--num-packets",
        type=int,
        default=3,
        help="每个 UDP 报文内包含的数据包数量",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=1.0,
        help="两次发送之间的时间间隔（秒）",
    )
    parser.add_argument(
        "--loop",
        type=int,
        default=-1,
        help="发送轮数；-1 表示无限循环，直到 Ctrl+C 终止",
    )
    parser.add_argument(
        "--msg-type",
        type=int,
        default=1,
        help="头部 MsgType 字段值（用于业务区分）",
    )
    args = parser.parse_args()

    target = (args.host, args.port)
    print(
        f"[Sender] 目标地址：{target[0]}:{target[1]}, "
        f"每包 {args.num_packets} 个数据包, 间隔 {args.interval}s, "
        f"循环 {args.loop if args.loop >= 0 else '无限'} 次, MsgType={args.msg_type}"
    )

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", 40000))  # 将发送端口绑定在40000，可选

    try:
        count = 0
        while True:
            if args.loop >= 0 and count >= args.loop:
                print("[Sender] 已完成指定轮数发送，准备退出。")
                break

            # 1) 构造示例数据包列表
            packets = make_example_packets(num_packets=args.num_packets, id_start=1)

            # 2) 构造完整 datagram
            datagram = build_datagram(msg_type=args.msg_type, packets=packets)

            # 3) 发送
            send_datagram(sock, target, datagram)

            print(
                f"[Sender] 已发送第 {count + 1} 轮报文："
                f"长度={len(datagram)} 字节，包含 {len(packets)} 个数据包"
            )

            count += 1
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\n[Sender] 收到 Ctrl+C，准备退出。")
    finally:
        sock.close()
        print("[Sender] socket 已关闭。")


if __name__ == "__main__":
    main()
