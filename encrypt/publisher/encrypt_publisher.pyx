# -*- coding: utf-8 -*-
# %%
"""
文件名    : encrypt_publisher.pyx
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
import issue_keys
import issue_license


# -------------- func: 生成一组私钥-公钥 ---------
cpdef public create_keys():
    """
    生成一组私钥-公钥，并以 base64 编码返回
    """
    try:
        sk_b64, pk_b64 = issue_keys.issue_keys()
    except Exception as e:
        print("生成密钥对时出错:", e)
        return False
    print("private_key_b64:", sk_b64)
    print("public_key_b64 :", pk_b64)
    return True

# -------------- func: 生成license ---------
cpdef public create_license(private_key_b64: str,
                            app_secret_b64: str,
                            target_fingerprint_sha256: str,
                            issued_to: str,
                            license_id: str,
                            not_before_utc: str,
                            not_after_utc: str):
    """
    生成license
    """
    try:
      issue_license.create_write_lic(private_key_b64=private_key_b64,
                                      app_secret_b64=app_secret_b64,
                                      target_fingerprint_sha256=target_fingerprint_sha256,
                                      issued_to=issued_to,
                                      license_id=license_id,
                                      not_before_utc=not_before_utc,
                                      not_after_utc=not_after_utc,
                                      )
    except Exception as e:
        print("生成 license 时出错,请检查各项参数是否正确！")
        print("错误信息:", e )
        return False
    return True
