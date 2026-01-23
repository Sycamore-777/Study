# -*- coding: utf-8 -*-
# %%
"""
文件名    : encrypt_customer.pyx
创建者    : Sycamore
创建日期  : 2026-01-14
最后修改  : 2026-01-14
版本号    : v1.0.0

■ 用途说明:
  Cython 封装层,封装license_guard.py中的get_fingerprint和check_license。

■ 主要函数功能:
  - get_fingerprint: 获取宿主机指纹字符串
  - check_license: 检查 license 的合法性


■ 功能特性:
  ✓ 统一入口封装，减少业务侧直接接触细节
  ✓ 编译为扩展模块，提高绕过门槛（但仍依赖 Python 逻辑与 cryptography）

■ 待办事项:

■ 更新日志:
  v1.0.0 (2026-01-14): 初始版本

"心之所向，素履以往；生如逆旅，一苇以航。"
"""
import license_guard


# -------------- func: 获取宿主机指纹字符串 ---------
cpdef  get_fingerprint():
    """
    返回一个固定的字符串，模拟“获取宿主机指纹”的功能
    """
    fingerprint, _ = license_guard.build_expected_fingerprint()
    print (f"Host fingerprint: {fingerprint}")
    return fingerprint

# -------------- func: 检查 license 的合法性 ---------
cpdef  check_license(
                issuer_public_key_b64: str,
                license_master_key_b64: str,
                app_secret_b64: str,
                license_path: str = "/app/license.lic",
                # license_aad: bytes = "LICv2".encode("utf-8"),
                # allowed_container_sources: Optional[Set[str]] = None,
            ):
    
    
    """
    调用 license_guard 进行 license 检查
    """
    license_guard.check_license(
                issuer_public_key_b64=issuer_public_key_b64,
                license_master_key_b64=license_master_key_b64,
                app_secret_b64=app_secret_b64,
                license_path=license_path,
                # license_aad=license_aad,
                # allowed_container_sources=allowed_container_sources
                )
