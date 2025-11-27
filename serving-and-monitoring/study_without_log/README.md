# Serving & Monitoring（基础版）

最小可运行的“算法服务 + 模拟数据源 + 轮询处理”示例，强调流程跑通和接口对接，不包含日志中间件。

- `service.py`：FastAPI 主服务，对外暴露 `/run_algo`（算法计算）、`/data_callback`（被动接收回调）、`/health`。
- `core_alog.py`：算法核心，当前示例逻辑为 `x*2 + y*3 + z*4`，可自由替换。
- `send_data.py`：模拟远程数据源，支持拉取最新数据与写入新数据。
- `get_data.py`：后台轮询远程数据并调用本地算法的示例应用。
- `client_call.py`：本地调试脚本，演示如何向主服务发起请求。

## 运行流程
1) 启动算法主服务（默认 9001），提供对外接口。
2) 启动模拟远程数据服务（默认 9002），充当被轮询的数据源。
3) 如需演示自动拉取与处理，启动轮询示例（默认 9003），后台任务每 5 秒取一次数据并调用 `run_algo`。
4) 使用 `client_call.py` 或 curl 调用接口验证链路。

## 快速上手
准备 Python 3.10+，安装依赖（建议虚拟环境）：
```bash
pip install fastapi uvicorn requests httpx
```

启动各组件（可按需选择）：
```bash
# 1) 主服务：提供 /run_algo、/data_callback、/health
uvicorn service:app --host 0.0.0.0 --port 9001 --reload

# 2) 模拟远程数据源：供轮询示例读取
uvicorn send_data:app --host 0.0.0.0 --port 9002 --reload

# 3) 轮询示例（可选）：定时拉取数据并调用 run_algo
uvicorn get_data:app --host 0.0.0.0 --port 9003 --reload
```

本地请求示例（`/run_algo` 需要 `X-Token: SECRET_123`）：
```bash
curl -X POST "http://localhost:9001/run_algo" \
  -H "Content-Type: application/json" \
  -H "X-Token: SECRET_123" \
  -d '{"x":1,"y":2,"z":3}'
```

## API 详情（主服务 `service.py`）
- `POST /run_algo`
  - 请求：JSON `{"x": float, "y": float, "z": float}`，需 Header `X-Token: SECRET_123`。
  - 响应：`{"result": number, "success": true, "elapsed_sec": <耗时>, "client_host": "<调用方IP>"}`。
- `POST /data_callback`
  - 请求：`{"param": {"x": "...","y": "...","z": "..."}, "source": "...", "timestamp": "..."}`，无需鉴权。
  - 行为：按回调数据调用 `run_algo`，返回执行结果及来源信息。
- `GET /health`
  - 返回服务状态与时间戳，用于存活探测。

## 模拟远程数据源（`send_data.py`）
- `GET /api/latest_data?since_id=<id>`：获取最新数据；传 `since_id` 时只返回更大的 id。
- `POST /api/produce`：新增一条数据（字段为 `value`），会自动生成递增 `id` 并追加到内存列表。

## 轮询示例（`get_data.py`）
- 后台任务 `poll_remote_data` 每 5 秒请求一次 `REMOTE_API`（默认 `http://localhost:9002/api/latest_data`）。
- 记录 `last_id` 实现增量拉取；对每条数据调用 `run_algo` 并打印处理结果。
- 使用 FastAPI `lifespan` 管理后台任务的启动/取消，示例应用本身也可作为一个轻量 API 服务。

## 调试与扩展
- 将真实算法填入 `core_alog.py::run_algo`，保持“无副作用、纯输入输出”便于测试。
- 如需接入真实数据源，将 `REMOTE_API` 指向目标地址，并在 `poll_remote_data` 中调整解析逻辑。
- 可在 `data_callback_endpoint` 内增加持久化（数据库/消息队列）或更多数据清洗逻辑。
