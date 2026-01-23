# -*- coding: utf-8 -*-
# %%
"""
文件名    : get_fingerprint.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-13
版本号    : v1.0.0

■ 用途说明:
  在 Docker 容器内获取宿主机的fingerprint。

■ 主要函数功能:


■ 功能特性:


■ 待办事项:



■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%

import license_guard

if __name__ == "__main__":
    # fingerprint, _ = license_guard.build_expected_fingerprint()
    # print(f"Host fingerprint: {fingerprint}")
    fingerprint, message = license_guard.build_expected_fingerprint()
    print(f"Host fingerprint: {fingerprint}")
    print()
    print(f"Message: {message}")
