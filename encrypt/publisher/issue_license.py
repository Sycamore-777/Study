# -*- coding: utf-8 -*-
# %%
"""
文件名    : issue_license_aesgcm.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-13
版本号    : v1.0.0

■ 用途说明:
  发行端签发许可证文件（.lic），采用 AES-GCM 加密 payload，并对密文进行 Ed25519 签名。

■ 主要函数功能:
  - derive_aes_key: 由 APP_SECRET + fingerprint 派生 AES-256 key
  - issue_license: 生成 payload -> 加密 -> 签名 -> 输出 lic dict
  - write_lic_file: 写入 license.lic

■ 功能特性:
  ✓ payload 加密后不可读
  ✓ 拷贝到其它机器无法解密（因 AES key 与 fingerprint 绑定）
  ✓ 先验签后解密，防篡改
  ⚠ APP_SECRET 若泄露会降低保密性（仍无法伪造签名，但可解密内容）

■ 待办事项:
  - [ ] 支持 key_id 多公钥轮换
  - [ ] 支持 features/limits 字段与审计信息

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
import base64
import hashlib
import json
import os
from typing import Dict, Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# =============================👐Seperate👐=============================
# 基础工具函数
# =============================👐Seperate👐=============================


def b64e(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")


def b64d(s: str) -> bytes:
    return base64.b64decode(s.encode("utf-8"))


def canonical_json(obj: Dict[str, Any]) -> bytes:
    """
    确定性 JSON 序列化（签名/验签必须一致）
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


# =============================👐Seperate👐=============================
# 关键：AES key 派生（绑定 fingerprint）
# =============================👐Seperate👐=============================


def derive_aes_key(app_secret_b64: str, fingerprint_sha256_hex: str) -> bytes:
    """
    AES-256 key = SHA256( app_secret || "|" || fingerprint_sha256_hex )
    - app_secret: 32 bytes 随机根密钥（base64 输入）
    - fingerprint_sha256_hex: 目标机器指纹（hex 字符串）
    返回 32 bytes key，可直接用于 AESGCM
    """
    # -------------- step: 解码 app_secret ---------
    app_secret = b64d(app_secret_b64)

    # -------------- step: 拼接派生材料并哈希 ---------
    material = (
        app_secret + b"|" + fingerprint_sha256_hex.strip().lower().encode("utf-8")
    )
    return sha256_bytes(material)  # 32 bytes


# =============================👐Seperate👐=============================
# 许可证生成：加密 payload + 签名密文
# =============================👐Seperate👐=============================


def issue_license(
    private_key_b64: str,
    app_secret_b64: str,
    target_fingerprint_sha256: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """
    输出 .lic 内容（JSON dict）结构：
      {
        "v": 2,
        "nonce_b64": "...",     # 12 bytes
        "ct_b64": "...",        # AESGCM.encrypt 输出(含tag)
        "sig_b64": "..."        # 对 {v,nonce_b64,ct_b64} 的 Ed25519 签名
      }
    """
    # -------------- step: 载入私钥 ---------
    sk = Ed25519PrivateKey.from_private_bytes(b64d(private_key_b64))

    # -------------- step: 派生 AES key（与 fingerprint 绑定） ---------
    aes_key = derive_aes_key(app_secret_b64, target_fingerprint_sha256)

    # -------------- step: payload -> bytes（确定性） ---------
    payload_bytes = canonical_json(payload)

    # -------------- step: AES-GCM 加密 ---------
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # GCM 推荐 12 bytes nonce

    # AAD（Additional Authenticated Data 可选）：绑定协议版本，防止密文跨协议复用
    aad = b"LICv2"
    ciphertext = aesgcm.encrypt(nonce, payload_bytes, aad)  # ciphertext 包含 tag

    # -------------- step: 构造待签名结构，并签名 ---------
    lic_core = {
        "v": 2,
        "nonce_b64": b64e(nonce),
        "ct_b64": b64e(ciphertext),
    }
    msg = canonical_json(lic_core)
    sig = sk.sign(msg)

    # -------------- step: 最终 lic ---------
    lic = dict(lic_core)
    lic["sig_b64"] = b64e(sig)
    return lic


def write_lic_file(lic: Dict[str, Any], out_path: str) -> None:
    # -------------- step: 写入 .lic 文件（JSON） ---------
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(lic, f, ensure_ascii=False, indent=2)
    print("written:", out_path)


# =============================👐Seperate👐=============================
# 许可证生成并写入文件
# =============================👐Seperate👐=============================
def create_write_lic(
    private_key_b64,
    app_secret_b64,
    target_fingerprint_sha256,
    issued_to,
    license_id,
    not_before_utc="2026-01-13T00:00:00Z",
    not_after_utc="2027-01-13T00:00:00Z",
):
    """
    许可证生成并写入.lic文件
    """
    # =============================👐Seperate👐=============================
    # 配置区（发行端）
    # - PRIVATE_KEY_B64: 发行方私钥（Raw 32 bytes 的 base64）
    # - APP_SECRET_B64  : 产品级根密钥（建议 32 bytes 随机值 base64）
    # - TARGET_FINGERPRINT_SHA256: 目标宿主机指纹（hex string）
    # =============================👐Seperate👐=============================

    PRIVATE_KEY_B64 = private_key_b64  # WARN: 切记不要发给其他人！！！
    APP_SECRET_B64 = app_secret_b64
    TARGET_FINGERPRINT_SHA256 = target_fingerprint_sha256
    NOT_BEFORE_UTC = not_before_utc
    NOT_AFTER_UTC = not_after_utc
    ISSUED_TO = issued_to
    LICENSE_ID = license_id

    OUT_LIC_PATH = "license.lic"
    # 也可以在 payload 里放更多字段（features/limits 等），也都将被加密保护，就看有没有这个必要了
    payload = {
        "license_id": LICENSE_ID,  # license 唯一 ID,建议按照LIC-{YYYYMMDD}-{NNNN} 格式取名，便于管理
        "issued_to": ISSUED_TO,  # 许可证归属客户标识，根据需要自定义就行
        "fingerprint_sha256": TARGET_FINGERPRINT_SHA256,  # 绑定的指纹
        "not_before_utc": NOT_BEFORE_UTC,  # 授权开始时间
        "not_after_utc": NOT_AFTER_UTC,  # 授权截止时间，开始和结束时间不建议告诉别人，否则别人通过这个就能知道什么时候过期了
    }

    lic = issue_license(
        private_key_b64=PRIVATE_KEY_B64,
        app_secret_b64=APP_SECRET_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
        payload=payload,
    )
    write_lic_file(lic, OUT_LIC_PATH)


# =============================👐Seperate👐=============================
# main（示例）
# =============================👐Seperate👐=============================

if __name__ == "__main__":
    try:
        with open("private_key_b64.txt", "r") as f:  # 这个文件切记不要发给其他人！！！
            PRIVATE_KEY_B64 = f.read().strip()
            print(PRIVATE_KEY_B64)
        with open("app_secret_b64.txt", "r") as f:
            APP_SECRET_B64 = f.read().strip()
    except Exception as e:
        print(
            "请确保当前目录下存在 private_key_b64.txt或 app_secret_b64.txt 文件，或者文件内容不正确。"
        )
        raise e
    TARGET_FINGERPRINT_SHA256 = (
        "6c16e8f8b9ebfa95fa7c5902f98987a5af6d906d8faa752ec84811ebb7c71e05"
    )

    create_write_lic(
        private_key_b64=PRIVATE_KEY_B64,
        app_secret_b64=APP_SECRET_B64,
        target_fingerprint_sha256=TARGET_FINGERPRINT_SHA256,
    )
