# -*- coding: utf-8 -*-
# %%
"""
文件名    : issue_license.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-16
版本号    : v1.1.0

■ 用途说明:
  发行端签发许可证文件（.lic），采用 AES-GCM 加密 payload，并对密文结构进行 Ed25519 签名。
  与验证端 license_guard.py 配套使用。

  你当前的整体安全闭环：
    1) payload(含 fingerprint+时间窗+source等) -> canonical_json
    2) AES-GCM 加密 payload（key 由 MASTER_KEY + fingerprint 派生）
    3) 对 {v,nonce_b64,ct_b64} 做 Ed25519 签名（防篡改）
    4) 输出 license.lic（JSON）

■ 主要函数功能:
  - derive_aes_key: 由 LICENSE_MASTER_KEY(APP_SECRET) + fingerprint 派生 AES-256 key
  - issue_license: 生成 payload -> 加密 -> 签名 -> 输出 lic dict
  - write_lic_file: 写入 license.lic
  - create_write_lic: 组装 payload 并写文件（给人直接调用的“上层入口”）
  - (可选) build_fingerprint_request: 生成“指纹申请信息”（不需要私钥，方便你让客户提供 fingerprint/source）

■ 功能特性:
  ✓ payload 加密后不可读（非授权机器/非正确 key 无法解密）
  ✓ 修改 license 中日期/字段会导致验签失败
  ✓ 增加 fingerprint_source（与验证端 source 语义闭环） [NEW]
  ✓ 支持 LICENSE_MASTER_KEY_B64 / APP_SECRET_B64 两种命名（兼容） [NEW]
  ✓ AAD 可配置（必须与验证端一致） [CHANGED]
  ✓ 修复 create_write_lic 参数默认值，确保示例 main 可运行 [FIX]

■ 待办事项:
  - [ ] 支持 key_id 多公钥轮换
  - [ ] payload 增加 features/limits 与审计字段
  - [ ] 若引入 host_attest：建议 attest 文件再做签名验签（防止伪造）

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本
  v1.1.0 (2026-01-16): 增加 fingerprint_source、key 命名兼容、AAD 配置与示例可运行修复

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
import argparse
import base64
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple, Literal
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


# =============================👐Seperate👐=============================
# 基础工具函数
# =============================👐Seperate👐=============================


def b64e(b: bytes) -> str:
    """bytes -> base64 str"""
    return base64.b64encode(b).decode("utf-8")


def b64d(s: str) -> bytes:
    """base64 str -> bytes"""
    return base64.b64decode(s.encode("utf-8"))


def canonical_json(obj: Dict[str, Any]) -> bytes:
    """
    确定性 JSON 序列化（签名/验签必须一致）
      - sort_keys=True：键排序
      - separators=(",", ":")：去掉空格，保证字节级一致
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> bytes:
    """返回 SHA-256 digest（32 bytes）"""
    return hashlib.sha256(data).digest()


def utc_now_isoz() -> str:
    """返回当前 UTC 时间（ISO8601，Z 结尾）"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =============================👐Seperate👐=============================
# [CHANGED] 配置区：命名兼容与 AAD 统一
# =============================👐Seperate👐=============================

# [CHANGED] AAD（Additional Authenticated Data）
# - 必须与验证端 license_guard.py 中 LICENSE_AAD 完全一致
# - 默认 LICv2（与你现有 guard 默认一致）
LICENSE_AAD = os.getenv("LICENSE_AAD", "LICv2").encode("utf-8")

# [NEW] 根密钥命名兼容：优先使用 LICENSE_MASTER_KEY_B64，其次 APP_SECRET_B64
# - 发行端、验证端要一致
LICENSE_MASTER_KEY_B64 = os.getenv("LICENSE_MASTER_KEY_B64", "").strip()
APP_SECRET_B64 = os.getenv("APP_SECRET_B64", "").strip()
EFFECTIVE_MASTER_KEY_B64 = LICENSE_MASTER_KEY_B64 or APP_SECRET_B64


# =============================👐Seperate👐=============================
# 关键：AES key 派生（绑定 fingerprint）
# =============================👐Seperate👐=============================


def derive_aes_key(master_key_b64: str, fingerprint_sha256_hex: str) -> bytes:
    """
    AES-256 key = SHA256( master_key || "|" || fingerprint_sha256_hex )

    参数：
      - master_key_b64         : 32 bytes 随机根密钥（base64 输入）
                                （注意：不是签名私钥；但仍应视为机密，泄露会降低 payload 保密性）
      - fingerprint_sha256_hex : 目标机器指纹（hex 字符串）

    返回：
      - 32 bytes key，可直接用于 AESGCM

    设计要点：
      - 这样做的意义是：同一份 license 拷贝到别的 fingerprint 上无法解密 payload（即使验签通过也解密失败）
      - fingerprint_sha256_hex 统一 lower，避免大小写造成派生不一致
    """
    # -------------- step: 解码 master_key ---------
    master_key = b64d(master_key_b64)

    # -------------- step: 拼接派生材料并哈希 ---------
    material = (
        master_key + b"|" + fingerprint_sha256_hex.strip().lower().encode("utf-8")
    )
    return sha256_bytes(material)  # 32 bytes


# =============================👐Seperate👐=============================
# 许可证生成：加密 payload + 签名密文结构
# =============================👐Seperate👐=============================


def issue_license(
    private_key_b64: str,
    master_key_b64: str,
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

    安全设计：
      - 先验签后解密：验证端应先用公钥验签 {v,nonce_b64,ct_b64}，通过后才尝试 AES-GCM 解密 payload
      - 防篡改：任何改动 v/nonce/ct 都会导致验签失败
      - 防直读：payload 加密后不可读
    """
    # -------------- step: 载入私钥（签名用） ---------
    # Ed25519 私钥 raw bytes = 32 bytes
    sk = Ed25519PrivateKey.from_private_bytes(b64d(private_key_b64))

    # -------------- step: 派生 AES key（与 fingerprint 绑定） ---------
    aes_key = derive_aes_key(master_key_b64, target_fingerprint_sha256)

    # -------------- step: payload -> bytes（确定性） ---------
    payload_bytes = canonical_json(payload)

    # -------------- step: AES-GCM 加密 ---------
    aesgcm = AESGCM(aes_key)
    nonce = os.urandom(12)  # GCM 推荐 12 bytes nonce
    ciphertext = aesgcm.encrypt(
        nonce, payload_bytes, LICENSE_AAD
    )  # ciphertext 包含 tag

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
    """
    将 lic dict 写入 .lic 文件（JSON）。

    说明：
      - 这里写的是 JSON，目的是便于你排查与版本升级
      - 因为 payload 已加密，所以即使 JSON 可读，也看不到明文授权信息
    """
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(lic, f, ensure_ascii=False, indent=2)
    print("written:", out_path)


# =============================👐Seperate👐=============================
# [NEW] 可选：生成“指纹申请信息”（让客户提供 fingerprint/source 时可用）
# =============================👐Seperate👐=============================


def build_fingerprint_request() -> Tuple[str, str]:
    """
    可选工具函数（不需要私钥/主密钥）：
      - 用于在“目标运行环境”生成 fingerprint + source，给发行端签发使用
      - 对于 Docker 场景：
          * Linux 宿主机 Docker：应由容器内挂载 /host/... 后运行 host_fingerprint 得到 source=docker-host-mount
          * Windows 宿主机 Docker：应挂载 host_attest.json 得到 source=host-attest
      - 对于本机场景：
          * Windows/Linux 本机运行得到 source=native（一般不用于“容器绑定宿主机”的交付）
    """
    try:
        import host_fingerprint  # 需要与 host_fingerprint.py 同目录/可 import
    except Exception as e:
        raise RuntimeError(f"无法导入 host_fingerprint.py：{e}")

    fp, material = host_fingerprint.build_fingerprint()
    src = str(material.get("source", "")).strip()
    return fp, src


# =============================👐Seperate👐=============================
# 许可证生成并写入文件（上层入口）
# =============================👐Seperate👐=============================


def create_write_lic(
    private_key_b64: str,
    master_key_b64: str,
    target_fingerprint_sha256: str,
    fingerprint_source: Literal["host-attest", "docker-host-mount", "native", None],
    issued_to: str,
    license_id: str,
    not_before_utc: str = "2026-01-13T00:00:00Z",
    not_after_utc: str = "2027-01-13T00:00:00Z",
    out_lic_path: str = "license.lic",
) -> None:
    """
    发行端入口：组装 payload 并签发 lic 文件。

    参数说明：
      - private_key_b64         : Ed25519 私钥（base64，32 bytes raw）
      - master_key_b64          : LICENSE_MASTER_KEY_B64 / APP_SECRET_B64（base64，建议 32 bytes）
      - target_fingerprint_sha256: 目标机器 fingerprint（hex）
      - fingerprint_source      : 绑定来源语义（host-attest / docker-host-mount / native）
                                 建议与 host_fingerprint.material["source"] 一致。
                                 这样验证端可拒绝“容器内 native”等语义错误。
      - out_lic_path            : 输出文件路径
      - issued_to               : 客户标识
      - license_id              : license 唯一 ID（建议 LIC-YYYYMMDD-NNNN）
      - not_before_utc / not_after_utc : UTC 授权时间窗


    重要提示：
      - fingerprint_source 不写也能用（验证端若只在字段存在时校验），但会削弱“防误签发/防语义降级”的效果。
      - 建议你在签发流程中强制要求 fingerprint_source 必填。
    """
    # =============================👐Seperate👐=============================
    # 参数与安全检查
    # =============================👐Seperate👐=============================

    if not private_key_b64.strip():
        raise ValueError("private_key_b64 为空：发行端必须提供 Ed25519 私钥")

    if not master_key_b64.strip():
        raise ValueError(
            "master_key_b64 为空：请提供 LICENSE_MASTER_KEY_B64 或 APP_SECRET_B64"
        )

    if not target_fingerprint_sha256.strip():
        raise ValueError("target_fingerprint_sha256 为空：请提供目标机器 fingerprint")

        # fingerprint_source 建议强约束（这里给出“强烈建议”，你可按需要改成强制 raise）
    if (
        fingerprint_source is None
        or fingerprint_source.strip() == ""
        or fingerprint_source
        not in [
            "host-attest",
            "docker-host-mount",
            "native",
        ]
    ):
        # 不直接 raise：为了兼容旧流程
        # 但会提示你：最好写入 source，形成验证端闭环
        print(
            "[WARN] fingerprint_source 未提供或提供有误：建议填写 'host-attest' 或 'docker-host-mount' 或 'native'，以便验证端做语义闭环校验。"
        )

    # =============================👐Seperate👐=============================
    # payload 组装（明文阶段，仅在发行端可见；落盘后将被 AES-GCM 加密）
    # =============================👐Seperate👐=============================

    payload: Dict[str, Any] = {
        "license_id": license_id,
        "issued_to": issued_to,
        "fingerprint_sha256": target_fingerprint_sha256.strip().lower(),
        # [NEW] 与验证端 license_guard.py 对齐：可选写入 fingerprint_source
        # - 推荐你在生产签发时强制写入，并只允许 host-attest / docker-host-mount（容器交付）
        "fingerprint_source": (
            fingerprint_source.strip() if fingerprint_source else ""
        ),
        "not_before_utc": not_before_utc,
        "not_after_utc": not_after_utc,
        # 你可以继续扩展：
        # "features": {"algoA": True, "algoB": False},
        # "limits": {"qps": 10, "max_targets": 200},
        # "issued_at_utc": utc_now_isoz(),
    }

    # =============================👐Seperate👐=============================
    # 加密 + 签名 -> lic dict
    # =============================👐Seperate👐=============================

    lic = issue_license(
        private_key_b64=private_key_b64,
        master_key_b64=master_key_b64,
        target_fingerprint_sha256=target_fingerprint_sha256,
        payload=payload,
    )

    # =============================👐Seperate👐=============================
    # 写入文件
    # =============================👐Seperate👐=============================

    write_lic_file(lic, out_lic_path)


# =============================👐Seperate👐=============================
# main（示例 + CLI）
# =============================👐Seperate👐=============================


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


from typing import Literal


def issue_license_or_fingerprint(
    fingerprint: str,
    fingerprint_source: Literal["host-attest", "docker-host-mount", "native"],
    issued_to: str,
    license_id: str,
    private_key_file: str = "private_key_b64.txt",
    master_key_file: str = "master_key_b64.txt",
    not_before_utc: str = "2026-01-13T00:00:00Z",
    not_after_utc: str = "2027-01-13T00:00:00Z",
    out_lic_path: str = "license.lic",
    gen_fingerprint_request: bool = False,
) -> Tuple[int, Optional[str], Optional[str]]:
    """
    以函数入参方式执行 License 流程（替代原 argparse main）。

    ## 典型用法（推荐）

    ### A) 发行端签发（安全环境）
    发行端应准备以下敏感材料（不要给客户）：
    - private_key_file: Ed25519 私钥（base64，32 bytes raw）
    - master_key_file : 产品主密钥（base64，建议 32 bytes；也不要给客户）

    客户侧应提供以下信息（建议使用你提供的采集器生成）：
    - fingerprint: 目标机器 fingerprint_sha256（hex）
    - fingerprint_source: fingerprint 来源（如 docker-host-mount / host-attest / native）

    示例（函数调用）：
        code, _, _ = issue_license_main(
            private_key_file="private_key_b64.txt",
            master_key_file="master_key_b64.txt",
            fingerprint="<hex>",
            fingerprint_source="docker-host-mount",
            issued_to="CustomerA",
            license_id="LIC-20260116-0001",
            not_before_utc="2026-01-16T00:00:00Z",
            not_after_utc="2027-01-16T00:00:00Z",
            out_lic_path="license.lic",
            gen_fingerprint_request=False,
        )

    ### B) 仅生成 fingerprint 申请信息（不签发）
    用于在“当前运行环境”生成 fingerprint 与 source 并返回，方便客户把申请信息发给你。

    示例：
        code, fp, src = issue_license_main(gen_fingerprint_request=True)
        # fp / src 可用于向发行端申请 license

    ## 参数说明
    - private_key_file:
        发行方私钥文件路径（base64，32 bytes raw）。仅发行端保管。
    - master_key_file:
        产品主密钥文件路径（base64，建议 32 bytes）。仅发行端保管。
    - fingerprint:
        目标机器 fingerprint_sha256（hex）。签发模式必须提供并绑定目标。
    - fingerprint_source:
        fingerprint 来源标识：host-attest / docker-host-mount / native。
        为空则在写 lic 时传 None（与原逻辑一致）。
    - issued_to:
        客户标识（字符串）。
    - license_id:
        license 唯一 ID（建议 LIC-YYYYMMDD-NNNN）。
    - not_before_utc / not_after_utc:
        UTC 生效/过期时间（ISO8601，例：2026-01-16T00:00:00Z）。
    - out_lic_path:
        输出 .lic 文件路径。
    - gen_fingerprint_request:
        True：仅生成 fingerprint+source（不签发，不读取密钥文件）
        False：执行签发流程（读取密钥、校验 fingerprint、写 lic）

    ## 返回值
    返回 (code, fingerprint_sha256, fingerprint_source)
    - code:
        0 表示流程成功（申请模式或签发模式均如此）
    - fingerprint_sha256 / fingerprint_source:
        仅在 gen_fingerprint_request=True 时返回实际值；否则返回 (None, None)

    ## 异常
    - RuntimeError:
        * 读取密钥文件失败
        * 签发模式下 fingerprint 缺失
    """
    # -------------- step: 可选模式：只生成 fingerprint 申请信息 ---------
    if gen_fingerprint_request:
        fp, src = build_fingerprint_request()
        return 0, fp, src

    # -------------- step: 读取密钥文件（发行端敏感） ---------
    try:
        private_key_b64 = _read_text_file(private_key_file)
        master_key_b64 = _read_text_file(master_key_file)
    except Exception as e:
        raise RuntimeError(
            "读取密钥文件失败：请确保 private_key_file / master_key_file 指向的文件存在，且内容为 base64 字符串。"
        ) from e

    # -------------- step: fingerprint 必须提供（签发必须绑定目标） ---------
    if not fingerprint.strip():
        raise RuntimeError(
            "缺少 fingerprint。\n"
            "你可以让客户在目标环境调用 issue_license_main(gen_fingerprint_request=True)\n"
            "然后把 fingerprint + source 发给你（不要让客户拿到你的私钥）。"
        )

    create_write_lic(
        private_key_b64=private_key_b64,
        master_key_b64=master_key_b64,
        target_fingerprint_sha256=fingerprint.strip(),
        issued_to=issued_to,
        license_id=license_id,
        not_before_utc=not_before_utc,
        not_after_utc=not_after_utc,
        fingerprint_source=(
            fingerprint_source.strip() if fingerprint_source.strip() else None
        ),
        out_lic_path=out_lic_path,
    )
    return 0, None, None


if __name__ == "__main__":
    private_key_file = "private_key_b64.txt"
    master_key_file = "master_key_b64.txt"
    fingerprint = "bd66cd841be81af479a7c5eb738c891e8818308fcc7f4cff9339f9b3d12f5fca"
    fingerprint_source = "native"
    issued_to = "customer-01"
    license_id = "LIC-20230113-0001"
    not_before_utc = "2026-01-13T00:00:00Z"
    not_after_utc = "2027-01-13T00:00:00Z"

    try:
        private_key_b64 = _read_text_file(private_key_file)
        master_key_b64 = _read_text_file(master_key_file)
    except Exception as e:
        raise RuntimeError(
            "读取密钥文件失败：请确保 private_key_file / master_key_file 指向的文件存在，且内容为 base64 字符串。"
        )
    target_fingerprint_sha256 = fingerprint.strip()
    create_write_lic(
        private_key_b64=private_key_b64,
        master_key_b64=master_key_b64,
        target_fingerprint_sha256=target_fingerprint_sha256,
        fingerprint_source=fingerprint_source,
        issued_to=issued_to,
        license_id=license_id,
        not_before_utc=not_before_utc,
        not_after_utc=not_after_utc,
    )
    print("生成license成功！")
