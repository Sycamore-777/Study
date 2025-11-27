# client_call.py
# 客户端调用示例代码
import requests

url = "http://localhost:9001/run_algo"
# url = "http://localhost:9001/health"

payload = {
    "x": 1.0,
    "y": 2.0,   
    "z": 3.0
}

response = requests.post(url, json=payload,headers={"X-Token":"SECRET_123"})
print(response.headers)
print(response.json())


# url = "http://localhost:9001/data_callback"
# payload = {
#     "param": {
#         "x": "2024-01-01T12:00:00",
#         "y": "111",
#         "z": "sensor_A"
#     },
#     "source": "system_X",
#     "timestamp": "2024-01-01T12:00:00"
# }

# response = requests.post(url, json=payload)
# print(response.json())