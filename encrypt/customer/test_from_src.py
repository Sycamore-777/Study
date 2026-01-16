# -*- coding: utf-8 -*-
# %%
"""
文件名    : test_from_src.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-13
版本号    : v1.0.0

■ 用途说明:
  提供一个可直接运行的 RESTful 服务示例（FastAPI），包含健康检查与资源 CRUD 接口。

■ 主要函数功能:

■ 功能特性:
  ✓ FastAPI + Pydantic：自动校验与 OpenAPI 文档
  ✓ 日志输出到控制台与文件
  ✓ 内存数据存储（便于替换为真实数据库）
  ⚠ 未集成鉴权/数据库（可按需扩展）

■ 待办事项:
  - [ ] 接入数据库（SQLite/MySQL/PostgreSQL）
  - [ ] 加入鉴权（JWT / API Key）
  - [ ] 增加统一错误码与全局异常处理

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


# =============================👐Seperate👐=============================
# 0) 日志配置
# =============================👐Seperate👐=============================

def setup_logger(log_dir: str = "logs", log_name: str = "rest_service.log") -> logging.Logger:
    # -------------- step: 创建日志目录 ---------
    os.makedirs(log_dir, exist_ok=True)

    # -------------- step: 创建 logger ---------
    logger = logging.getLogger("rest_service")
    logger.setLevel(logging.INFO)

    # -------------- step: 避免重复添加 handler（多次 import 时常见） ---------
    if logger.handlers:
        return logger

    # -------------- step: 日志格式 ---------
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # -------------- step: 控制台 handler ---------
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    # -------------- step: 文件 handler ---------
    fh = logging.FileHandler(os.path.join(log_dir, log_name), encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(fmt)

    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger


LOGGER = setup_logger()


# =============================👐Seperate👐=============================
# 1) 数据模型（Pydantic）
# =============================👐Seperate👐=============================


class ApiResponse(BaseModel):
    # -------------- step: 统一返回结构（你也可以不用统一结构，直接返回 ItemOut） ---------
    success: bool
    message: str
    data: Optional[object] = None


# =============================👐Seperate👐=============================
# 3) FastAPI 应用与全局异常处理
# =============================👐Seperate👐=============================

app = FastAPI(
    title="Sycamore REST Service",
    version="1.0.0",
    description="A minimal but production-friendly RESTful service template.",
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # -------------- step: 记录异常日志（带路径） ---------
    LOGGER.exception("Unhandled exception: path=%s, err=%s", request.url.path, str(exc))

    # -------------- step: 返回统一错误响应（生产可区分 4xx/5xx 或加入 error_code） ---------
    return JSONResponse(
        status_code=500,
        content=ApiResponse(success=False, message="Internal Server Error", data=None).model_dump(),
    )


# =============================👐Seperate👐=============================
# 4) 路由定义（RESTful）
# =============================👐Seperate👐=============================

@app.get("/healthz", response_model=ApiResponse)
def healthz():
    # -------------- step: 服务健康检查 ---------
    return ApiResponse(success=True, message="ok", data={"time_utc": datetime.now(timezone.utc).isoformat()})


@app.post("/api/v1/items", response_model=ApiResponse)
def create_item(payload: ItemCreate):
    # -------------- step: 创建资源 ---------
    result = "yes？！？！"
    return ApiResponse(success=True, message="created", data=result)



# =============================👐Seperate👐=============================
# 5) 启动入口
# =============================👐Seperate👐=============================

if __name__ == "__main__":
    # -------------- step: 本地启动（生产部署建议用命令行 uvicorn/gunicorn） ---------
    import uvicorn
    from license_guard import check_license
    import sys
    encrypt = False 
    if encrypt:
        try:
            check_license()
        except Exception as e:
            # 不要打印 raw 指纹源，避免泄露
            print(f"License check failed: {e}", file=sys.stderr)

    uvicorn.run(
        "rest_service:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # 开发调试可改 True
        log_level="info",
    )
