# -*- coding: utf-8 -*-
"""
udp_protocol_defs.py
--------------------
协议 & 数据结构 & 解析函数模块。

职责：
    - 定义常用的状态类型别名（State_01, State_02, State）
    - 定义 UDP 协议中的 MsgHeader / RealtimePacket 数据结构（dataclass）
    - 定义 struct 格式（HEADER_STRUCT / PACKET_STRUCT）
    - 提供 parse_header / parse_one_packet / parse_full_datagram 三类解析函数

后续使用：
    - 在主框架里： from udp_protocol_defs import ...
    - 如果协议变了，只改这个文件即可，框架和业务逻辑不用动。
"""

import struct
from dataclasses import dataclass
from typing import Tuple, List, Tuple as TypingTuple

# =====================================================================
# 1. 类型别名（协议相关）
# =====================================================================

# 通用状态类型 1，例如时间：(year, month, day, hour, minute, second)
State_01 = Tuple[float, float, float, float, float, float]

# 通用状态类型 2，例如业务向量：(a, b, c, d, e, f)
State_02 = Tuple[float, float, float, float, float, float]

# 历史状态：例如“上一拍”的 (State_01, State_02)
State = Tuple[State_01, State_02]

# =====================================================================
# 2. 协议数据结构定义（dataclass）
# =====================================================================


@dataclass
class MsgHeader:
    """
    UDP 数据头结构（示例协议）：
        - MsgType        : 消息类型
        - MsgState_01    : 常用状态 1（例如时间）
        - PackageNumber  : 数据包个数
        - PackageLength  : 单个数据包长度（字节）

    TODO: 根据实际 UDP 协议调整字段和类型。
    """

    MsgType: int
    MsgState_01: State_01
    PackageNumber: int
    PackageLength: int


@dataclass
class RealtimePacket:
    """
    UDP 单个数据包结构（示例协议）：
        - IsValid  : 是否有效
        - ID       : 目标 ID
        - ParentID : 父 ID
        - Name     : 名称（64 字节字符串）
        - State_02 : 常用状态 2（例如业务数组）

    TODO: 根据实际 UDP 协议调整字段和类型。
    """

    IsValid: bool
    ID: int
    ParentID: int
    Name: str
    State_02: State_02


# =====================================================================
# 3. struct 格式定义
# =====================================================================

# 头部：1 * int + 6 * double + 2 * int
# < 表示小端字节序；如需要网络字节序改为 "!"
HEADER_STRUCT = struct.Struct("<i6dii")
HEADER_SIZE = HEADER_STRUCT.size

# 数据包：bool + int + int + char[64] + 6 * double
PACKET_STRUCT = struct.Struct(
    "<"
    "?"  # IsValid
    "i"  # ID
    "i"  # ParentID
    "64s"  # Name
    "6d"  # State_02
)
PACKET_SIZE = PACKET_STRUCT.size

# 解析完整报文后的类型： (header, [packet, ...])，一个报文可能包含多个数据包
ParsedDatagram = Tuple[MsgHeader, List[RealtimePacket]]

# =====================================================================
# 4. 协议解析函数：bytes -> (MsgHeader, [RealtimePacket...])
# =====================================================================


def parse_header(data: bytes) -> MsgHeader:
    """
    从原始报文 data 中解析数据头（MsgHeader）。
    """
    if len(data) < HEADER_SIZE:
        raise ValueError(
            f"数据长度不足以解析头部：len={len(data)}, 需要至少 {HEADER_SIZE} 字节"
        )

    (
        MsgType,
        year,
        month,
        day,
        hour,
        minute,
        second,
        PackageNumber,
        PackageLength,
    ) = HEADER_STRUCT.unpack_from(data, 0)

    state_01: State_01 = (year, month, day, hour, minute, second)

    return MsgHeader(
        MsgType=MsgType,
        MsgState_01=state_01,
        PackageNumber=PackageNumber,
        PackageLength=PackageLength,
    )


def parse_one_packet(buf: bytes, offset: int) -> RealtimePacket:
    """
    从 buf[offset:] 解析一个实时数据包，返回 RealtimePacket。
    """
    if len(buf) < offset + PACKET_SIZE:
        raise ValueError(
            f"数据长度不足以解析一个数据包: len(buf)={len(buf)}, "
            f"offset={offset}, 需要 {PACKET_SIZE} 字节"
        )

    unpacked = PACKET_STRUCT.unpack_from(buf, offset)

    (
        IsValid,
        ID,
        ParentID,
        Name_raw,
        a,  # State_02 的第一个 double
        b,  # State_02 的第二个 double
        c,  # State_02 的第三个 double
        d,  # State_02 的第四个 double
        e,  # State_02 的第五个 double
        f,  # State_02 的第六个 double
        *rest,  # ✅ 预留：如果以后在 PACKET_STRUCT 里继续加字段，就从这里拆
    ) = unpacked

    # TODO: 如果协议将来扩展，可以在这里解析 rest，例如：
    # extra_fields = tuple(rest)

    # 组装 State_02
    state_02: State_02 = (a, b, c, d, e, f)

    # 名称去掉尾部 \x00，并按 UTF-8 解码
    Name = Name_raw.split(b"\x00", 1)[0].decode("utf-8", errors="ignore")

    return RealtimePacket(
        IsValid=IsValid,
        ID=ID,
        ParentID=ParentID,
        Name=Name,
        State_02=state_02,
    )


def parse_full_datagram(data: bytes) -> ParsedDatagram:
    """
    解析完整 UDP 报文：返回 (header, [packets...])
    """
    header = parse_header(data)
    packets: List[RealtimePacket] = []

    # 校验报文长度是否足够：理论总长度=数据头长度 + 包数量 * 包长度
    expected_len = HEADER_SIZE + header.PackageNumber * header.PackageLength
    if len(data) < expected_len:
        print(
            f"[Parser][警告] 报文长度 {len(data)} 小于头部声明长度 {expected_len}，"
            f"可能被截断或协议不一致。"
        )

    # 校验包长度是否与本地定义一致
    if header.PackageLength != PACKET_SIZE:
        print(
            f"[Parser][警告] 头部声明 PackageLength={header.PackageLength} "
            f"与本地 PACKET_SIZE={PACKET_SIZE} 不一致，请检查 C 端结构对齐。"
        )

    # 逐个解析数据包
    offset = HEADER_SIZE  # 数据包起始偏移，先跳过头部

    for i in range(header.PackageNumber):
        if offset + PACKET_SIZE > len(data):
            print(
                f"[Parser][警告] 解析第 {i} 个数据包时长度不足，"
                f"offset={offset}, len(data)={len(data)}"
            )
            break

        pkt = parse_one_packet(data, offset)
        packets.append(pkt)
        # 用头部声明的 PackageLength 推进偏移量
        offset += header.PackageLength

    return header, packets
