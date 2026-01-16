# -*- coding: utf-8 -*-
# %%
"""
文件名    : license_guard.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-13
版本号    : v1.0.0

■ 用途说明:
  Docker 容器内授权守护：读取宿主机只读挂载的硬件/系统标识生成指纹，
  再读取加密版许可证(.lic)，执行“验签 -> 解密 -> 绑定校验 -> 有效期校验”，
  校验通过后才允许程序继续运行。

■ 主要函数功能:
  - build_host_fingerprint: 从 /host 挂载读取宿主机标识并生成 fingerprint_sha256
  - load_lic_file: 读取 .lic 文件内容（JSON 包裹的密文结构）
  - verify_lic_signature: 使用发行方公钥对 lic_core 进行 Ed25519 验签（防篡改）
  - decrypt_lic_payload: 使用 AES-GCM 解密 payload（使 license 内容不可读）
  - verify_payload_rules: 校验 fingerprint 绑定与有效期窗口

■ 功能特性:
  ✓ 宿主机指纹绑定（非容器自身）
  ✓ Ed25519 公钥验签，防篡改
  ✓ AES-GCM 加密 payload，文件内容不可读
  ✓ 拷贝到其他物理机通常无法解密（AES key 与 fingerprint 派生绑定）
  ⚠ 若攻击者可修改镜像内代码/二进制，可绕过本地校验（需编译加固/完整性自检）

■ 待办事项:
  - [ ] 支持公钥和APPSECRET通过环境变量导入，提高维护性
  - [ ] 将关键校验逻辑编译为 .so
  - [ ] 增加 key_id 支持多公钥轮换
  - [ ] 增加反回拨策略（离线场景需持久化“最后成功校验时间”并做防篡改）

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
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

# -------------- step: 导入加密依赖（cryptography） ---------
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception:
    Ed25519PublicKey = None
    AESGCM = None


# =============================👐Seperate👐=============================
# 配置区（建议后续通过环境变量注入，便于部署与轮换，目前先放在这）
# =============================👐Seperate👐=============================

# -------------- step: 发行方公钥（base64，Raw 32 bytes） ---------
ISSUER_PUBLIC_KEY_B64 = "改成你自己的密钥"
# -------------- step: 产品根密钥（base64，建议 Raw 32 bytes） ---------
# 注意：这不是签名私钥；它用于 AES key 派生以加密 payload，防止许可证中的内容被读取，但是加上这个也不全是好处，自己看起来也比较困难了。
APP_SECRET_B64 = "改成你自己的密钥"
# -------------- step: AAD（必须与发行端一致） ---------
# 目前发行端使用 "LICv2"；如你改了发行端，这里也必须同步修改
LICENSE_AAD = os.getenv("LICENSE_AAD", "LICv2").encode("utf-8")

# -------------- step: 宿主机标识挂载路径（docker run -v ... 对应） ---------
HOST_MACHINE_ID_PATH = os.getenv("HOST_MACHINE_ID_PATH", "/host/etc/machine-id")
HOST_DMI_DIR = os.getenv("HOST_DMI_DIR", "/host/sys/class/dmi/id")

# -------------- step: 许可证文件路径（容器内） ---------
# 你要生成 .lic 文件并挂载到该路径
LICENSE_PATH = os.getenv("LICENSE_PATH", "/app/license.lic")


# =============================👐Seperate👐=============================
# 数据结构
# =============================👐Seperate👐=============================


@dataclass
class HostIds:
    machine_id: str
    product_uuid: str
    board_serial: str
    chassis_serial: str


# =============================👐Seperate👐=============================
# 基础工具函数
# =============================👐Seperate👐=============================


def _b64d(s: str) -> bytes:
    """base64 解码（输入字符串）"""
    # -------------- step: 去空白并解码 ---------
    return base64.b64decode(s.strip().encode("utf-8"))


def _b64e(b: bytes) -> str:
    """base64 编码（输出字符串）"""
    # -------------- step: 编码为 utf-8 字符串 ---------
    return base64.b64encode(b).decode("utf-8")


def _sha256_hex(s: str) -> str:
    """SHA-256(hex)，用于宿主机指纹输出"""
    # -------------- step: 计算哈希并转 hex ---------
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_bytes(b: bytes) -> bytes:
    """SHA-256(bytes)，用于 AES key 派生"""
    # -------------- step: 计算 32 bytes digest ---------
    return hashlib.sha256(b).digest()


def _canonical_json(obj: Dict[str, Any]) -> bytes:
    """
    确定性 JSON 序列化（签名/验签必须一致）
    - sort_keys=True
    - separators=(",", ":") 去空格
    """
    # -------------- step: 固定序列化规则，避免跨端不一致 ---------
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _utc_now() -> datetime:
    """返回当前 UTC 时间"""
    # -------------- step: 统一使用 UTC，避免时区歧义 ---------
    return datetime.now(timezone.utc)


def _parse_utc_iso8601(s: str) -> datetime:
    """
    解析 UTC ISO8601（推荐格式：2026-01-13T00:00:00Z）
    """
    # -------------- step: 兼容 Z 结尾 ---------
    s2 = s.strip()
    if s2.endswith("Z"):
        s2 = s2[:-1] + "+00:00"
    # -------------- step: 解析并规范到 UTC ---------
    return datetime.fromisoformat(s2).astimezone(timezone.utc)


def _read_text_file(path: str) -> str:
    """读取文本文件并 strip；失败返回空串"""
    # -------------- step: 检查存在性并读取 ---------
    try:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


# =============================👐Seperate👐=============================
# 宿主机指纹生成（从 /host 挂载读取）
# =============================👐Seperate👐=============================


def read_host_ids() -> HostIds:
    """
    从宿主机挂载文件读取标识：
      - machine-id: /host/etc/machine-id
      - dmi: /host/sys/class/dmi/id/{product_uuid, board_serial, chassis_serial}
    """
    # -------------- step: 读取 machine-id ---------
    machine_id = _read_text_file(HOST_MACHINE_ID_PATH)

    # -------------- step: 读取 DMI（更偏物理机） ---------
    product_uuid = _read_text_file(os.path.join(HOST_DMI_DIR, "product_uuid"))
    board_serial = _read_text_file(os.path.join(HOST_DMI_DIR, "board_serial"))
    chassis_serial = _read_text_file(os.path.join(HOST_DMI_DIR, "chassis_serial"))

    return HostIds(
        machine_id=machine_id,
        product_uuid=product_uuid,
        board_serial=board_serial,
        chassis_serial=chassis_serial,
    )


def build_host_fingerprint() -> Tuple[str, HostIds, str]:
    """
    生成宿主机指纹：
      - raw_source: 拼接字符串（不建议外泄）
      - fingerprint_sha256: SHA-256(raw_source) 的 hex 字符串
    """
    # -------------- step: 读取宿主机标识 ---------
    host_ids = read_host_ids()

    # -------------- step: 至少要有 machine-id 或 product_uuid ---------
    if not host_ids.machine_id and not host_ids.product_uuid:
        raise RuntimeError(
            "无法获取宿主机标识。请确认 docker run 已只读挂载 /etc/machine-id 和/或 /sys/class/dmi/id 到 /host。"
        )

    # -------------- step: 组合原始材料（缺失字段用空串占位） ---------
    raw_source = (
        f"machine_id={host_ids.machine_id}|"
        f"product_uuid={host_ids.product_uuid}|"
        f"board_serial={host_ids.board_serial}|"
        f"chassis_serial={host_ids.chassis_serial}"
    )

    # -------------- step: 计算 fingerprint（hex） ---------
    fingerprint_sha256 = _sha256_hex(raw_source)
    return fingerprint_sha256, host_ids, raw_source


# =============================👐Seperate👐=============================
# 许可证读取（.lic 文件）与验签/解密
# =============================👐Seperate👐=============================


def load_lic_file(path: str) -> Dict[str, Any]:
    """
    读取 .lic 文件（JSON 格式），期望字段：
      - v: 版本号（当前示例为 2）
      - nonce_b64: AES-GCM nonce（base64）
      - ct_b64: AES-GCM 密文（base64，含 tag）
      - sig_b64: Ed25519 签名（base64），签名对象为 lic_core 的 canonical_json
    """
    # -------------- step: 检查文件存在 ---------
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到许可证文件: {path}")

    # -------------- step: 读取 JSON ---------
    with open(path, "r", encoding="utf-8") as f:
        lic = json.load(f)

    # -------------- step: 基础字段检查 ---------
    if not isinstance(lic, dict):
        raise ValueError("许可证文件格式错误：根对象不是 JSON dict")

    return lic


def verify_lic_signature(issuer_pubkey_b64: str, lic: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 Ed25519 公钥对 lic_core 验签（防篡改）。
    返回 lic_core（用于后续解密）。
    """
    # -------------- step: 依赖检查 ---------
    if Ed25519PublicKey is None:
        raise RuntimeError(
            "缺少依赖 cryptography，无法验签。请安装：pip install cryptography"
        )

    # -------------- step: 取出必要字段 ---------
    v = lic.get("v", None)
    nonce_b64 = str(lic.get("nonce_b64", "")).strip()
    ct_b64 = str(lic.get("ct_b64", "")).strip()
    sig_b64 = str(lic.get("sig_b64", "")).strip()

    # -------------- step: 格式校验（尽量明确报错） ---------
    if v is None or nonce_b64 == "" or ct_b64 == "" or sig_b64 == "":
        raise ValueError("许可证文件缺少字段：需要 v, nonce_b64, ct_b64, sig_b64")

    # -------------- step: 构造验签对象（只签核心字段） ---------
    lic_core = {
        "v": int(v),
        "nonce_b64": nonce_b64,
        "ct_b64": ct_b64,
    }

    msg = _canonical_json(lic_core)

    # -------------- step: 公钥验签 ---------
    pub = Ed25519PublicKey.from_public_bytes(_b64d(issuer_pubkey_b64))
    try:
        pub.verify(_b64d(sig_b64), msg)
    except Exception:
        raise RuntimeError("许可证验签失败：签名不合法或文件被篡改")

    return lic_core


def derive_aes_key(app_secret_b64: str, fingerprint_sha256_hex: str) -> bytes:
    """
    派生 AES-256 key（32 bytes）：
      key = SHA256( app_secret_bytes || "|" || fingerprint_sha256_hex )
    注意：这个函数必须与发行端保持一致
    """
    # -------------- step: 解码 app_secret ---------
    app_secret = _b64d(app_secret_b64)

    # -------------- step: 拼接派生材料并哈希 ---------
    material = (
        app_secret + b"|" + fingerprint_sha256_hex.strip().lower().encode("utf-8")
    )
    return _sha256_bytes(material)  # 32 bytes


def decrypt_lic_payload(
    app_secret_b64: str, expected_fingerprint_sha256: str, lic_core: Dict[str, Any]
) -> Dict[str, Any]:
    """
    AES-GCM 解密 payload：
      - AES key 由 APP_SECRET + expected_fingerprint 派生
      - nonce / ct 从 lic_core 中读取
      - AAD 必须与发行端一致（默认 LICENSE_AAD）
    """
    # -------------- step: 依赖检查 ---------
    if AESGCM is None:
        raise RuntimeError(
            "缺少依赖 cryptography，无法解密。请在镜像内安装：pip install cryptography"
        )

    # -------------- step: 解码 nonce 与密文 ---------
    nonce = _b64d(str(lic_core["nonce_b64"]))
    ct = _b64d(str(lic_core["ct_b64"]))

    # -------------- step: 派生 AES key（与宿主机 fingerprint 绑定） ---------
    aes_key = derive_aes_key(app_secret_b64, expected_fingerprint_sha256)

    # -------------- step: AES-GCM 解密（失败通常是错误机器或文件损坏） ---------
    aesgcm = AESGCM(aes_key)
    try:
        payload_bytes = aesgcm.decrypt(nonce, ct, LICENSE_AAD)
    except Exception:
        raise RuntimeError("许可证解密失败：可能为非授权物理机或许可证文件损坏/不匹配")

    # -------------- step: bytes -> dict ---------
    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise RuntimeError("许可证 payload 解析失败：解密结果不是合法 JSON")

    if not isinstance(payload, dict):
        raise RuntimeError("许可证 payload 格式错误：payload 不是 JSON dict")

    return payload


# =============================👐Seperate👐=============================
# payload 业务规则校验（绑定 + 有效期）
# =============================👐Seperate👐=============================


def verify_payload_rules(
    payload: Dict[str, Any], expected_fingerprint_sha256: str
) -> None:
    """
    校验：
      1) payload 内 fingerprint_sha256（如存在）与 expected 一致
      2) not_before_utc / not_after_utc 时间窗口
    """
    # -------------- step: 绑定校验（冗余保护，建议保留） ---------
    fp_in_payload = str(payload.get("fingerprint_sha256", "")).strip().lower()
    if fp_in_payload and fp_in_payload != expected_fingerprint_sha256.strip().lower():
        raise RuntimeError(
            "许可证绑定校验失败：payload 内 fingerprint 不匹配当前宿主机"
        )

    # -------------- step: 时间窗口字段检查 ---------
    nb = str(payload.get("not_before_utc", "")).strip()
    na = str(payload.get("not_after_utc", "")).strip()
    if not nb or not na:
        raise RuntimeError("许可证缺少有效期字段：not_before_utc / not_after_utc")

    # -------------- step: 解析时间并对比（UTC） ---------
    not_before = _parse_utc_iso8601(nb)
    not_after = _parse_utc_iso8601(na)
    now = _utc_now()

    if now < not_before:
        raise RuntimeError("许可证未生效：当前时间早于 not_before_utc")
    if now > not_after:
        raise RuntimeError("许可证已过期：当前时间晚于 not_after_utc")


# =============================👐Seperate👐=============================
# 对外入口：一次性完成全部校验
# =============================👐Seperate👐=============================


def check_license_or_raise() -> Dict[str, Any]:
    """
    主入口：
      - 计算宿主机指纹 expected_fingerprint_sha256
      - 读取 .lic
      - 验签（公钥）
      - 解密（AES-GCM）
      - 校验绑定与有效期
    成功返回 payload（你可用来做 features/limits 等授权策略）
    """
    # -------------- step: 生成宿主机指纹 ---------
    expected_fingerprint_sha256, _host_ids, _raw_source = build_host_fingerprint()

    # -------------- step: 读取 .lic ---------
    lic = load_lic_file(LICENSE_PATH)

    # -------------- step: 验签（防篡改） ---------
    lic_core = verify_lic_signature(ISSUER_PUBLIC_KEY_B64, lic)

    # -------------- step: 解密 payload（防止直接读取license） ---------
    payload = decrypt_lic_payload(APP_SECRET_B64, expected_fingerprint_sha256, lic_core)

    # -------------- step: 业务规则校验（绑定+有效期） ---------
    verify_payload_rules(payload, expected_fingerprint_sha256)

    return payload


# =============================👐Seperate👐=============================
# main（示例）：作为容器 entrypoint 的最小守护
# =============================👐Seperate👐=============================


def check_license() -> int:
    """
    返回退出码：
      0: 通过
      2: 授权失败（通用）
    """
    # -------------- step: 执行校验 ---------
    _payload = check_license_or_raise()

    # -------------- step: 通过后可继续启动你的服务 ---------
    # 这里仅示例打印；生产环境建议直接进入你的业务入口（import + run）
    print("License OK. Host authorized.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(check_license())
    except Exception as e:
        # 注意：不要打印 raw_source，避免泄露宿主机敏感标识拼接材料
        print(f"License check failed: {e}", file=sys.stderr)
        sys.exit(2)
