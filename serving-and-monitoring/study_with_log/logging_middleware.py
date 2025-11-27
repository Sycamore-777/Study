# logging_middleware.py
# 日志中间件，用于记录每个请求的日志信息
import time
import uuid
import logging
from fastapi import Request,HTTPException
from starlette.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("service")
API_TOKEN = "SECRET_123"  # 示例：简单的固定 token，实际可以放配置/环境变量中

class LoggingMiddleware(BaseHTTPMiddleware):
    '''
    全局请求日志中间件：
    - 每个进入的请求都会经过这里
    - 记录每个请求的开始时间、结束时间、处理时长、状态码等信息
    '''

    async def dispatch(self, request: Request, call_next):
        '''
        每一个http请求都会调用这个方法
        args:
            request: 请求对象(包含请求方法、url、headers、客户端等信息)
            call_next: 一个可调用的对象，用它吧请求交给下一个中间件或者处理函数
        '''
        # 记录开始时间
        start = time.time()
        # 生成一个本次请求的唯一标识符
        request_id = str(uuid.uuid4())
        logger.info(f"id = {request_id}")
        
        # 获取请求信息
        client_host = request.client.host if request.client else "unknown"
        request.state.client_host = client_host  # 把客户端地址存到 request.state 里，后续处理函数也能用
        # 处理请求,将请求交给下一个中间件或者处理函数
        try:
            response = await call_next(request)
        except Exception as e:
            # 如果处理过程中抛出异常，记录异常日志
            logger.exception(f"request_id = {request_id} ;Request from {client_host} to {request.url.path} failed: {e}")
            raise e
        # 计算耗时
        end = time.time()
        process_time = end - start

        # 在响应头中增加处理时间信息
        response.headers["X-Process-Time"] = str(process_time)
        response.headers["X-Request-ID"] = request_id

        # 记录日志
        logger.info(f"request_id = {request_id} ;Request from {client_host} to {request.url.path} completed in {process_time:.4f} seconds with status code {response.status_code}")
        # 返回响应 切记，中间件必须返回响应对象，不能返回字典
        return response

class LoggingAuthMiddleware(BaseHTTPMiddleware):
    '''
    API Token 验证中间件：
    - 每个进入的请求都会经过这里
    - 验证请求头中的 X-Token 是否正确
    '''

    async def dispatch(self, request: Request, call_next):
        '''
        每一个http请求都会调用这个方法
        args:
            request: 请求对象(包含请求方法、url、headers、客户端等信息)
            call_next: 一个可调用的对象，用它吧请求交给下一个中间件或者处理函数
        '''
        # 验证 API Token
        if request.url.path != "/health":
            if request.headers.get("X-Token") != API_TOKEN:
                logger.warning(f"Unauthorized access attempt from {request.client.host if request.client else 'unknown'} to {request.url.path}")
                return JSONResponse(
                    status_code=401,
                    content = {"detail": "Invalid or missing X-Token header"}
                )
        # 通过验证，继续处理请求
        response = await call_next(request)
        return response
