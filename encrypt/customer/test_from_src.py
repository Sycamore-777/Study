# -*- coding: utf-8 -*-
# %%
"""
文件名    : test_from_so.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-21
版本号    : v1.1.0

■ 用途说明:
  提供函数调用接口。

■ 主要函数功能:

■ 功能特性:

■ 待办事项:

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本
  v1.1.0 (2026-01-21): 依据新的接口调整

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
from __future__ import annotations

import license_guard


# =============================👐Seperate👐=============================
# 测试函数
# =============================👐Seperate👐=============================
def test_function():
    return "Function call successful."


# =============================👐Seperate👐=============================
# 启动入口
# =============================👐Seperate👐=============================

if __name__ == "__main__":

    import sys

    with open("public_key_b64.txt", "r") as f:
        issuer_public_key_b64 = f.read().strip()

    with open("master_key_b64.txt", "r") as f:
        app_secret_b64 = f.read().strip()
        f.seek(0)
        license_master_key_b64 = f.read().strip()
    # license_path = "./encrypt/publisher/license.lic" # debug时用
    license_path = "../publisher/license.lic"  # 运行时用

    encrypt = True
    if encrypt:
        ## -------------- step: 检查授权 ----------------
        try:
            print("License check starting...")
            license_guard.check_license(
                issuer_public_key_b64=issuer_public_key_b64,
                license_master_key_b64=license_master_key_b64,
                app_secret_b64=app_secret_b64,
                license_path=license_path,
            )
            print("License check passed.")

        except Exception as e:
            print(f"[ERROR] License check failed: {e}", file=sys.stderr)
        ## -------------- step: 检查指纹生成 --------------
        try:
            print("fingerprint check starting...")
            license_guard.build_expected_fingerprint()
            print("fingerprint check passed.")
        except Exception as e:
            print(f"[ERROR] fingerprint check failed: {e}", file=sys.stderr)

    ## -------------- step: 调用你自己的函数 --------------
    test_function()
