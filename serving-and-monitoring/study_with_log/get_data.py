# get_data.py
import asyncio
import contextlib
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from core_alog import run_algo

REMOTE_API = "http://localhost:9002/api/latest_data"


async def poll_remote_data():
    """
    后台循环任务：
    - 每隔 N 秒向对方请求一次最新数据
    - 收到数据后调用本地算法
    """
    last_id = None  # 记住已处理到哪条数据

    async with httpx.AsyncClient() as client:
        while True:
            try:
                # 1. 组织查询参数（如果对方支持 since_id）
                params = {"since_id": last_id} if last_id is not None else {}
                print("请求参数:", params)

                # 2. 向对方接口发起 HTTP GET 请求
                resp = await client.get(REMOTE_API, params=params, timeout=5.0)

                # 3. 如果状态码不是 2xx，抛出异常
                resp.raise_for_status()

                # 4. 解析响应体为 Python 对象（通常是 list 或 dict）
                data = resp.json()
                print("收到数据:", data)

                # 5. 假设 data 是“列表”，每个元素是一条数据
                for item in data:
                    # 5.1 根据对方接口的数据结构，取出你需要的字段
                    value = item["value"]

                    # 5.2 调用你的算法
                    result = run_algo(value, 0.0, 0.0)

                    # 5.3 暂时用打印代替：你可以改成写库/发消息
                    print("处理一条数据:", item, "算法结果:", result)

                    # 5.4 记录这条数据的 id，用于下一轮 since_id
                    last_id = item["id"]

            except Exception as e:
                # 捕获所有异常，仅做日志，防止循环任务直接崩掉
                print("轮询出错：", e)

            # 6. 每一轮结束后，休眠 5 秒再发起下一轮请求
            await asyncio.sleep(5)


# --------------- 新的 lifespan 写法 ---------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理：
    - 进入时：启动后台轮询任务
    - 退出时：可以在这里做清理（比如取消任务）
    """
    # 启动后台任务
    task = asyncio.create_task(poll_remote_data())
    try:
        yield   # 这里之后，FastAPI 会去处理请求
    finally:
        # 关闭时取消后台任务（可选）
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


# 把 lifespan 传入 FastAPI
app = FastAPI(lifespan=lifespan)
