# -*- coding: utf-8 -*-
# %%
"""
文件名    : rest_service.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-13
版本号    : v1.0.0

■ 用途说明:
  提供函数调用接口。

■ 主要函数功能:

■ 功能特性:


■ 待办事项:
  - [ ] 增加统一错误码与全局异常处理

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
from __future__ import annotations
import sys
from publisher_init import publisher_init
import issue_license


# =============================👐Seperate👐=============================
# 测试函数
# =============================👐Seperate👐=============================
def test_function():
    return "Function call successful."


# =============================👐Seperate👐=============================
# 启动入口
# =============================👐Seperate👐=============================

if __name__ == "__main__":
    ## -------------- step: 初始化测试环境 --------------
    print("初始化测试环境...")
    publisher_init()

    ## -------------- step: 测试license生成 --------------

    try:
        with open("private_key_b64.txt", "r") as f:  # 这个文件切记不要发给其他人！！！
            PRIVATE_KEY_B64 = f.read().strip()
        with open("master_key_b64.txt", "r") as f:
            MASTER_KEY_B64 = f.read().strip()
    except Exception as e:
        print(f"读取密钥文件时出错: {e}")
        print("请确保 private_key_b64.txt 和 master_key_b64.txt 文件存在且格式正确。")
        sys.exit(1)
    TARGET_FINGERPRINT_SHA256 = "替换成你自己的机器码"
    FINGERPRINT_SOURCE = "native"
    ISSUED_TO = "Customer-01"
    LICENSE_ID = "LIC-Customer-20260116-001"
    NOT_BEFORE_UTC = "2026-01-13T00:00:00Z"
    NOT_AFTER_UTC = "2027-01-13T00:00:00Z"

    print("check issue license starting...")
    issue_license.create_write_lic(
        private_key_b64=PRIVATE_KEY_B64,
        master_key_b64=MASTER_KEY_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
        fingerprint_source=FINGERPRINT_SOURCE,
        issued_to=ISSUED_TO,
        license_id=LICENSE_ID,
        not_before_utc=NOT_BEFORE_UTC,
        not_after_utc=NOT_AFTER_UTC,
    )
    print("check issue license passed")
    # create_keys()

# %%
