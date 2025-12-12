# UDP 模块说明

本目录实现了一个可自定义协议的 UDP 收发示例，包含协议定义、通用发送端、带队列的接收端以及可替换的业务处理函数。可以用它快速模拟「C 端发送 / Python 端接收」或纯 Python 自测的完整链路。

## 目录结构
- `udp_protocol_defs.py`：协议结构、`struct` 格式、解析函数（bytes -> `MsgHeader` + `RealtimePacket` 列表）。
- `udp_sender_generic.py`：通用发送端；基于协议定义构造报文并循环发包。
- `udp_receiver_with_queue.py`：带线程安全队列的接收端；监听 UDP、解析报文并调用业务 handler。
- `example_func.py`：示例业务函数，对比前后两次 `State_02` 计算差异并返回是否触发。
- `state_update.log`：接收端默认写入的日志文件（初始化、更新事件）。

## 协议与数据结构（`udp_protocol_defs.py`）
- 基础类型别名  
  - `State_01 = Tuple[float, float, float, float, float, float]`：示例为时间戳 `(year, month, day, hour, minute, second)`。  
  - `State_02 = Tuple[float, float, float, float, float, float]`：示例为 6 维业务向量。  
  - `State = Tuple[State_01, State_02]`：历史状态。
- 数据类  
  - `MsgHeader`：`MsgType`、`MsgState_01`、`PackageNumber`（包个数）、`PackageLength`（单包长度，示例使用 `PACKET_SIZE`）。  
  - `RealtimePacket`：`IsValid`、`ID`、`ParentID`、`Name`（64 字节，UTF-8，0 填充）、`State_02`。
- `struct` 定义（小端 `<`；若需网络字节序改为 `!`）  
  - 头部：`HEADER_STRUCT = "<i6dii"`，`HEADER_SIZE = 60` 字节  
    - 字段顺序：`MsgType (int32)`、`State_01` 六个 `double`、`PackageNumber (int32)`、`PackageLength (int32)`  
  - 数据包：`PACKET_STRUCT = "<?ii64s6d"`，`PACKET_SIZE = 121` 字节  
    - 字段顺序：`IsValid (bool)`、`ID (int32)`、`ParentID (int32)`、`Name (64 bytes)`、`State_02` 六个 `double`
- 解析函数  
  - `parse_header(data: bytes) -> MsgHeader`：校验长度、按头部结构解包。  
  - `parse_one_packet(buf, offset) -> RealtimePacket`：从偏移处解出单包，`Name` 去除 `\x00` 以 UTF-8 解码。  
  - `parse_full_datagram(data) -> (header, packets)`：先解析头，再按 `PackageLength` 逐包解析；当报文长度或包长与本地定义不一致时打印警告。

## 发送端（`udp_sender_generic.py`）
- 核心函数  
  - `get_current_state_01()`：以本地时间构造 `State_01`。  
  - `build_header(msg_type, state_01, package_number)` / `build_header_bytes(...)`：生成头部及其 bytes。  
  - `encode_name(name, length=64)`：UTF-8 编码，超长截断，不足 `\x00` 填充。  
  - `build_packet_bytes(pkt: RealtimePacket)`：按协议打包单个数据包。  
  - `build_datagram(msg_type, packets)`：组合头部与数据包列表得到完整 datagram。  
  - `make_example_packets(num_packets, id_start=1, name_prefix="Obj")`：生成示例包，`State_02` 带随机扰动。  
  - `send_datagram(sock, target, datagram)`：`socket.sendto` 发送。
- 命令行参数（`python udp_sender_generic.py ...`）  
  - `--host`：目标 IP，默认 `127.0.0.1`。  
  - `--port`：目标端口，默认 `5005`。  
  - `--num-packets`：每个 UDP 报文内的数据包数量，默认 3。  
  - `--interval`：发送间隔秒数，默认 1.0。  
  - `--loop`：发送轮数，-1 为无限循环。  
  - `--msg-type`：头部 `MsgType`，默认 1。  
  - 发送端本地绑定端口默认 `40000`，可按需修改。
- 快速自测  
```bash
python udp_sender_generic.py --host 127.0.0.1 --port 5005 --num-packets 3 --interval 0.5 --loop 5 --msg-type 1
```
将示例包循环发送给接收端。

## 接收端（`udp_receiver_with_queue.py`）
- 线程与队列设计  
  - 监听线程 `udp_listener`：绑定 `0.0.0.0:5005`，`recvfrom` 后把 `(addr, raw_data, recv_time)` 放入线程安全队列 `task_queue`（`maxsize=10000`，满则警告并丢弃）。  
  - 工作线程 `worker_loop`：从队列取出任务，调用 `parse_full_datagram` 解析，再把 `(addr, parsed, recv_time)` 交给业务 handler。  
  - 主线程：启动上述线程后保持存活，可用 `Ctrl+C` 退出。
- 默认业务处理 `data_handler`  
  - 维护全局 `history_state_by_id: Dict[int, State]`。  
  - 对每个 `RealtimePacket`（仅处理 `IsValid=True`）提取 `ID` 与当前 `State_02`。  
  - 首次见到某 ID：初始化历史并记日志。  
  - 后续：取上一次状态，调用 `example_func(state_02_current, state_02_prev)` 判定是否触发；触发则更新历史并写入 `state_update.log`。  
  - 示例 `example_func`（位于 `example_func.py`）对比前后两次 `State_02` 的欧氏距离，阈值默认为 0，可按业务改写。
- 运行方式  
```bash
python udp_receiver_with_queue.py
```
启动后即可接收 `udp_sender_generic.py` 的报文，解析结果与更新记录写入 `state_update.log`。
- 自定义建议  
  - 协议变更：仅需修改 `udp_protocol_defs.py`（类型别名、`struct` 格式、`parse_*` 函数），发送端与接收端共享同一定义。  
  - 业务逻辑：替换 `data_handler` 或在 `main()` 中传入自定义 handler；如需不同日志格式可调整 `logging.basicConfig` 或改写写入目标。  
  - 名称字段：`Name` 为 64 字节定长，过长会被截断；接收端解析会去除尾部 `\x00` 并按 UTF-8 解码。  
  - 包长校验：发送端头部 `PackageLength` 统一写入 `PACKET_SIZE=121`，接收端会用头部声明推进偏移，务必与 C 端或其他语言端保持一致。

## 常见操作流程
1. 终端 A 启动接收端：`python udp_receiver_with_queue.py`，观察 `state_update.log`。  
2. 终端 B 运行发送端：`python udp_sender_generic.py --num-packets 3 --interval 1.0 --loop 3`。  
3. 如需接入真实业务：  
   - 按真实协议修改 `udp_protocol_defs.py`。  
   - 按业务改写 `example_func` 或 `data_handler`（也可引入多个 handler）。  
   - 视需要调整队列大小、监听/发送端口以及日志输出位置。
