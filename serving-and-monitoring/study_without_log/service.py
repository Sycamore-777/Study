# service_main.py
# 服务的主入口,为他人提供接口，或者被动接受他人的回调
from fastapi import FastAPI, Header,HTTPException,Request
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from core_alog import run_algo
import time
import requests

# --------------------
# 1. 定义请求数据模型
# --------------------

class algo_input(BaseModel): # 算法输入数据格式
    x: float
    y: float
    z: float

class Param(BaseModel):
    x: str
    y: str
    z: str
class callback_data(BaseModel): # 调用另外一个系统的接口
    param: Param
    source: str
    timestamp: str



# ---------------------
# 2. 创建 FastAPI 应用
# ---------------------
app = FastAPI(title="学习算法服务", version="0.1")
API_TOKEN = "SECRET_123"  # 示例：简单的固定 token，实际可以放配置/环境变量中

# ---------------------
# 3. 接收外部调用的接口
# ---------------------
@app.post("/run_algo")
async def run_algo_endpoint(input_data: algo_input, request:Request,xtoken: Optional[str] = Header(default=None, alias="X-Token")):
    '''
    接收外部调用，运行算法并返回结果；
    调用方式：POST /run_algo，传入 JSON 格式的算法输入数据
    body 示例：
    {
        "x": 1.0,
        "y": 2.0,   
        "z": 3.0
    }
    '''
    # 验证 API Token
    if xtoken != API_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid API Token or missing X-Token header")
    
    # 记录请求开始时间
    start = time.time()

    # 获取客户端 IP 地址,如果拿不到就用"unknown"
    client_host = request.client.host if request.client else "unknown"
    # 打印一条日志，记录一下谁来调用的，传了什么数据
    print(f"Received request from {client_host} with data: {input_data}")

    # 调用核心算法
    try:
        result = run_algo(input_data.x, input_data.y, input_data.z)
    except Exception as e:
        print(f"[run_algo]算法执行错误: {e}")
        raise HTTPException(status_code=500, detail="Algorithm execution error")
    
    
    # 记录请求处理时间
    end = time.time()
    elapsed = end - start
    print(f"Request processed in {elapsed:.2f} seconds")

    # 返回响应
    return {
        "result": result,
        "success": True,
        "elapsed_sec": elapsed,
        "client_host": client_host,
    }
    
# -------------------
# 4. 对外暴露的回调接口
# -------------------
@app.post("/data_callback")
def data_callback_endpoint(data: callback_data):
    '''
    接收外部系统的回调数据；,其他系统一有新数据，就会POST到这里
    POST /data_callback
    body:{
        "param":{
            "x": "2024-01-01T12:00:00",
            "y": "111",
            "z": "sensor_A"
        }
        "source": "system_X",
        "timestamp": "2024-01-01T12:00:00"
    }
    '''
    # 根据对方推送过来的数据，组织成算法需要的输入
    x = data.param.x
    y = data.param.y
    z = data.param.z
    print("Received callback data from ", data.source)

    # 这里可以调用算法，或者把数据存储起来，供后续处理
    result = run_algo(x, y, z)

    # 将结果保存到数据库中，或者发送到其他系统（TODO 后面要增加保存到数据库的功能）
    return{
        "success": True,
        "result": result,
        "source": data.source,
        "timestamp": data.timestamp,
    }

# -------------------
# 5. 健康检查接口
# -------------------
@app.get("/health")
def health_check():
    '''
    健康检查接口，外部系统可以调用这个接口来检查服务是否正常运行
    GET /health
    '''
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }