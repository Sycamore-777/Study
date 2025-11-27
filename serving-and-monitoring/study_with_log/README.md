# Serving & Monitoring（带日志版）

在基础流程上增加日志与鉴权中间件，演示如何为 FastAPI 服务补充观测性与安全控制。

- `service.py`：主服务，装载 `LoggingMiddleware` 与 `LoggingAuthMiddleware`，提供 `/run_algo`、`/data_callback`、`/health`。
- `logging_middleware.py`：全局请求日志与 X-Token 鉴权中间件，自动生成 `X-Request-ID`、`X-Process-Time` 响应头。
- `core_alog.py`：算法核心（默认 `x*2 + y*3 + z*4`），保持纯输入输出。
- `send_data.py`：模拟远程数据源，可被轮询。
- `get_data.py`：后台轮询示例应用。
- `client_call.py`：本地调用示例。

## 请求生命周期
进入路由前，中间件先执行：
- `LoggingAuthMiddleware`：除 `/health` 外校验 `X-Token`（默认 `SECRET_123`），失败返回 401。
- `LoggingMiddleware`：生成请求 ID，记录开始/结束时间，将客户端 IP 放入 `request.state`，并把耗时与请求 ID 写入响应头。

随后由路由处理请求，返回 dict，FastAPI 封装为 HTTP 响应后再回到中间件完成日志写入。

## 快速上手
安装依赖：
```bash
pip install fastapi uvicorn requests httpx
```

启动各组件：
```bash
# 主服务（含日志与鉴权）
uvicorn service:app --host 0.0.0.0 --port 9001 --reload

# 模拟远程数据源
uvicorn send_data:app --host 0.0.0.0 --port 9002 --reload

# 轮询示例（可选）
uvicorn get_data:app --host 0.0.0.0 --port 9003 --reload
```

调用示例（所有非 `/health` 请求都需要 `X-Token: SECRET_123`）：
```bash
curl -X POST "http://localhost:9001/run_algo" \
  -H "Content-Type: application/json" \
  -H "X-Token: SECRET_123" \
  -d '{"x":1,"y":2,"z":3}'
```

## API 说明（`service.py`）
- `POST /run_algo`：请求体 `{"x": float, "y": float, "z": float}`；响应包含算法结果、耗时、调用方 IP。
- `POST /data_callback`：接收外部系统回调数据 `{"param": {...}, "source": "...", "timestamp": "..."}`，按回调内容调用 `run_algo`。
- `GET /health`：健康检查，不需要 Token。

## 日志与响应头
- 日志：记录请求 ID、路径、客户端 IP、耗时、状态码，异常时写入堆栈。
- 响应头：`X-Request-ID`（UUID）、`X-Process-Time`（秒级耗时）便于链路追踪与监控。

## 模拟数据源与轮询
- `send_data.py`：`GET /api/latest_data?since_id=<id>`、`POST /api/produce`（生成递增 id 的数据）。
- `get_data.py`：后台任务每 5 秒拉取一次数据，使用 `last_id` 增量读取，对每条记录调用 `run_algo`。

## 调试/扩展建议
- 若在实际环境使用，将 `API_TOKEN` 配置成环境变量或配置中心，并补充更多鉴权逻辑（如签名/白名单）。
- 在 `LoggingMiddleware` 中可根据需要增加 trace_id 注入、请求/响应体采样、日志脱敏等能力。
- 若要对接真实数据源，修改 `REMOTE_API` 及数据解析逻辑；算法实现放在 `core_alog.py` 以保持可测试性。
