# send_data.py
# 主动向其他系统发送数据的示例代码,模拟远程服务
from fastapi import FastAPI
from typing import List, Optional
from pydantic import BaseModel

app = FastAPI(title="模拟远程数据服务", version="0.1")

FAKE_DATA = [
    {"id": 1, "value": 10.0, "timestamp": "2024-01-01T12:00:00"},
    {"id": 2, "value": 20.0, "timestamp": "2024-01-01T12:05:00"},
    {"id": 3, "value": 30.0, "timestamp": "2024-01-01T12:10:00"},
    {"id": 4, "value": 40.0, "timestamp": "2024-01-01T12:15:00"},
]

# 定义数据模型
class DataItem(BaseModel):
    id: int
    value: float
    timestamp: str

@app.get("/api/latest_data", response_model=List[DataItem])
def get_latest_data(since_id: Optional[int] = None):
    """
    这个接口模拟“对外提供最新数据”的场景：
    - 如果不传 since_id，就返回全部
    - 如果传了 since_id，就返回 id > since_id 的数据
    """

    if since_id is None:
        return FAKE_DATA

    return [item for item in FAKE_DATA if item["id"] > since_id]


@app.post("/api/produce")
def produce_new_data(value: float):
    """
    模拟“对方系统在不停产生新数据”：
    - 每调用一次，就往 FAKE_DATA 里塞一条新数据
    """
    new_id = FAKE_DATA[-1]["id"] + 1 if FAKE_DATA else 1
    item = {"id": new_id, "value": value,"timestamp": "2024-01-01T12:20:00"}
    FAKE_DATA.append(item)
    print("FAKE_DATA:", FAKE_DATA)
    return {"success": True, "item": item}