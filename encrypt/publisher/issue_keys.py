# -*- coding: utf-8 -*-
# %%
"""
文件名    : issue_keys.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-13
版本号    : v1.0.0

■ 用途说明:
  生成 Ed25519 keypair，用于许可证签名（私钥）与镜像内验签（公钥）。

■ 主要函数功能:
  - issue_keys: 生成并输出 base64 私钥/公钥

■ 功能特性:
  ✓ 输出 base64编码的一对私钥与公钥
  ⚠ 私钥必须妥善保管，不可进入镜像，不可外发他人

■ 待办事项:
  - [ ] 支持加密存储

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ============================================================== 
# %%
import base64
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def issue_keys():
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()
    from cryptography.hazmat.primitives import serialization
    sk_b64 = b64e(sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    ))
    pk_b64 = b64e(pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ))

    return sk_b64, pk_b64




if __name__ == "__main__":
    sk_b64, pk_b64 = issue_keys()
    print("private_key_b64:", sk_b64)
    print("public_key_b64 :", pk_b64)
