# -*- coding: utf-8 -*-
# %%
"""
文件名    : license_guard.py
创建者    : Sycamore
创建日期  : 2026-01-13
最后修改  : 2026-01-16
版本号    : v1.1.0

■ 用途说明:
  离线授权守护（可运行于：Windows 本机 / Linux 本机 / Docker 容器）：
  1) 计算“期望机器指纹 expected_fingerprint_sha256”
     - v1.0.0: 仅支持 Docker 中从 /host 读取宿主机标识（见旧版 build_host_fingerprint）。[CHANGED]
     - v1.1.0: 使用 host_fingerprint.build_fingerprint() 自动选择可用来源：
               host-attest > docker-host-mount > native （并由 guard 二次约束容器内禁止 native）。[CHANGED]
  2) 读取加密许可证 .lic（JSON 包裹密文结构）
  3) Ed25519 验签：防篡改（改日期/字段会导致验签失败）
  4) AES-GCM 解密 payload：使许可证内容不可直接读懂
  5) 规则校验：
     - 指纹绑定校验 fingerprint_sha256
     - （可选）fingerprint_source 与当前 source 一致性校验 [NEW]
     - not_before_utc / not_after_utc 时间窗口校验

■ 主要函数功能:
  - build_expected_fingerprint: 生成 expected_fingerprint_sha256，并返回 material（含 source 等审计信息）[CHANGED]
  - load_lic_file: 读取 .lic 文件内容
  - verify_lic_signature: 使用发行方公钥对 lic_core 验签（防篡改）
  - decrypt_lic_payload: 使用 AES-GCM 解密 payload
  - verify_payload_rules: 校验 fingerprint 绑定、fingerprint_source（可选）、有效期窗口 [CHANGED]
  - check_license_or_raise: 一次性完成全部校验并返回 payload

■ 功能特性:
  ✓ 多环境统一：Windows / Linux / Docker
  ✓ Ed25519 公钥验签，防篡改
  ✓ AES-GCM 加密 payload，内容不可读
  ✓ 容器内默认禁止 native 指纹（防止“绑定容器/WSL/VM”导致可迁移授权）[NEW]
  ⚠ 若攻击者可修改镜像内代码/二进制，可绕过本地校验（需编译加固/完整性自检）

■ 待办事项:
  - [ ] host_attest 文件做签名验签（Ed25519），防止伪造（推荐）
  - [ ] 增加 key_id 支持多公钥轮换
  - [ ] 增加反回拨策略（离线场景需持久化“最后成功校验时间”并做防篡改）

■ 更新日志:
  v1.0.0 (2026-01-13): 初始版本
  v1.1.0 (2026-01-16): 接入 host_fingerprint、多环境支持、容器内禁止 native、增加 fingerprint_source 校验与环境变量注入

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
import base64
import hashlib
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set, Tuple

# -------------- step: 导入加密依赖（cryptography） ---------
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except Exception as e:
    raise (f"Failed to import cryptography,Please install it.\n {e}")


# -------------- step: 导入宿主机指纹模块 ---------
import host_fingerprint


# =============================👐Seperate👐=============================
# 配置区（仅保留 DEBUG_TRACEBACK / ALLOW_INSECURE_CONTAINER_NATIVE）
# 其余配置全部移入函数入参（见 check_license_or_raise / check_license）
# =============================👐Seperate👐=============================

# [NEW] 输出控制：发布版默认不打印 traceback（减少内部信息暴露）
DEBUG_TRACEBACK = os.getenv("DEBUG_TRACEBACK", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)

# [NEW] 容器内是否允许 native fingerprint
# 交付建议保持默认 0；仅内部调试可设为 1
ALLOW_INSECURE_CONTAINER_NATIVE = os.getenv(
    "ALLOW_INSECURE_CONTAINER_NATIVE", "0"
).strip().lower() in (
    "1",
    "true",
    "yes",
)


# =============================👐Seperate👐=============================
# 基础工具函数
# =============================👐Seperate👐=============================


def _b64d(s: str) -> bytes:
    """base64 解码（输入字符串）"""
    return base64.b64decode(s.strip().encode("utf-8"))


def _b64e(b: bytes) -> str:
    """base64 编码（输出字符串）"""
    # -------------- step: 编码为 utf-8 字符串 ---------
    return base64.b64encode(b).decode("utf-8")


def _sha256_hex(s: str) -> str:
    """SHA-256(hex)，用于 fingerprint（文本 -> hex）"""
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def _sha256_bytes(b: bytes) -> bytes:
    """SHA-256(bytes)，用于 AES key 派生（bytes -> 32 bytes digest）"""
    return hashlib.sha256(b).digest()


def _canonical_json(obj: Dict[str, Any]) -> bytes:
    """
    确定性 JSON 序列化（签名/验签必须一致）：
      - sort_keys=True     : key 排序，避免 dict 顺序影响签名
      - separators=(",",":"): 去掉空格，保证字节级一致
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _utc_now() -> datetime:
    """返回当前 UTC 时间（统一用 UTC，避免时区歧义）"""
    return datetime.now(timezone.utc)


def _parse_utc_iso8601(s: str) -> datetime:
    """
    解析 UTC ISO8601（推荐格式：2026-01-13T00:00:00Z）
    - 兼容以 Z 结尾
    - 统一转换到 UTC tz
    """
    s2 = s.strip()
    if s2.endswith("Z"):
        s2 = s2[:-1] + "+00:00"
    return datetime.fromisoformat(s2).astimezone(timezone.utc)


def _is_running_in_container_best_effort() -> bool:
    """
    [NEW]
    目的：guard 侧做“容器内禁止 native”约束时，需要知道自己是否在容器中运行。
    注意：启发式判断无法 100% 准确；因此 guard 的策略是：
      - 容器内若 source 非白名单 -> 直接拒绝（fail closed）
      - 若误判为容器：会更严格（可能拒绝 native），但不会带来“授权放松”
    """
    if os.path.exists("/.dockerenv"):
        return True
    if os.path.exists("/run/.containerenv"):
        return True
    # cgroup 线索
    for p in ("/proc/1/cgroup", "/proc/self/cgroup"):
        try:
            if not os.path.exists(p):
                continue
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                txt = f.read()
            if ("docker" in txt) or ("kubepods" in txt) or ("containerd" in txt):
                return True
        except Exception:
            pass
    return False


def _require_config_or_fail(
    issuer_public_key_b64: str,
    effective_app_secret_b64: str,
) -> None:
    """
    [NEW]
    配置强校验：避免用户忘了配置密钥导致“看似能跑但实际验签/解密一定失败”。
    """

    if not issuer_public_key_b64:
        raise RuntimeError(
            "缺少发行方公钥：请设置环境变量 ISSUER_PUBLIC_KEY_B64（Raw 32 bytes 的 base64）"
        )

    if not effective_app_secret_b64:
        raise RuntimeError(
            "缺少产品根密钥：请设置 LICENSE_MASTER_KEY_B64（推荐）或 APP_SECRET_B64（兼容）"
        )


# =============================👐Seperate👐=============================
# [CHANGED] 指纹生成：从旧版 build_host_fingerprint -> 新版 build_expected_fingerprint
# =============================👐Seperate👐=============================


def build_expected_fingerprint(
    allowed_container_sources: Set[str] = {"host-attest", "docker-host-mount"},
) -> Tuple[str, Dict[str, Any]]:
    """
    [CHANGED]
    生成“期望指纹 expected_fingerprint_sha256”，并返回 material（审计用）。

    - v1.0.0: build_host_fingerprint() 固定从 /host 读取（只能 Docker Linux host-mount）。
    - v1.1.0: 使用 host_fingerprint.build_fingerprint() 自动选择来源（支持多环境）。[CHANGED]

    返回：
      - expected_fingerprint_sha256: hex
      - material: dict，至少包含：
          - platform: "windows"/"linux"（通常有）
          - source: "host-attest"/"docker-host-mount"/"native"
          - 其他 id 字段（机器标识）
    """
    if host_fingerprint is None:
        raise RuntimeError(
            f"无法导入 host_fingerprint.py "
            "请确保 host_fingerprint.py 与 license_guard.py 同目录或在 PYTHONPATH 中。"
        )

    fp, material = host_fingerprint.build_fingerprint()

    # -------------- step: material 基础校验（尽量早发现异常） ---------
    if not isinstance(material, dict):
        raise RuntimeError(
            "host_fingerprint.build_fingerprint() 返回 material 非 dict，属于实现错误"
        )

    source = str(material.get("source", "")).strip()

    # -------------- step: [NEW] 容器内强约束：禁止 source=native（除非明确允许） ---------
    in_container = _is_running_in_container_best_effort()
    if in_container:
        if source not in allowed_container_sources:
            # 若你内部要临时放开，可通过 ALLOW_INSECURE_CONTAINER_NATIVE=1
            if ALLOW_INSECURE_CONTAINER_NATIVE and source == "native":
                pass
            else:
                raise RuntimeError(
                    "容器内禁止使用 native 指纹（防止绑定到容器/WSL/VM）。\n"
                    f"当前 source={source!r}，允许的 source={sorted(allowed_container_sources)}。\n"
                    "请在 docker run 中提供：\n"
                    "  - Linux 宿主机：挂载 /etc/machine-id 与 /sys/class/dmi/id 到 /host（只读）\n"
                    "  - Windows 宿主机：挂载 host_attest.json 到 /host/attest/host_attest.json（只读）"
                )

    return fp, material


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
    if not os.path.exists(path):
        raise FileNotFoundError(f"未找到许可证文件: {path}")

    with open(path, "r", encoding="utf-8") as f:
        lic = json.load(f)

    if not isinstance(lic, dict):
        raise ValueError("许可证文件格式错误：根对象不是 JSON dict")

    return lic


def verify_lic_signature(issuer_pubkey_b64: str, lic: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用 Ed25519 公钥对 lic_core 验签（防篡改）。
    返回 lic_core（用于后续解密）。

    说明：
      - 只对 lic_core（v/nonce_b64/ct_b64）做签名：
        这样即便外层 JSON 多了字段，也不影响签名语义。
    """
    if Ed25519PublicKey is None:
        raise RuntimeError(
            "缺少依赖 cryptography，无法验签。请安装：pip install cryptography"
        )

    v = lic.get("v", None)
    nonce_b64 = str(lic.get("nonce_b64", "")).strip()
    ct_b64 = str(lic.get("ct_b64", "")).strip()
    sig_b64 = str(lic.get("sig_b64", "")).strip()

    if v is None or nonce_b64 == "" or ct_b64 == "" or sig_b64 == "":
        raise ValueError("许可证文件缺少字段：需要 v, nonce_b64, ct_b64, sig_b64")

    lic_core = {"v": int(v), "nonce_b64": nonce_b64, "ct_b64": ct_b64}
    msg = _canonical_json(lic_core)

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

    注意：
      - 必须与发行端保持一致（否则解密必然失败）
      - fingerprint_sha256_hex 统一 lower，以避免大小写差异
    """
    app_secret = _b64d(app_secret_b64)

    material = (
        app_secret + b"|" + fingerprint_sha256_hex.strip().lower().encode("utf-8")
    )
    return _sha256_bytes(material)


def decrypt_lic_payload(
    app_secret_b64: str,
    expected_fingerprint_sha256: str,
    lic_core: Dict[str, Any],
    license_aad: bytes,
) -> Dict[str, Any]:
    """
    AES-GCM 解密 payload：
      - AES key 由 APP_SECRET(或 LICENSE_MASTER_KEY) + expected_fingerprint 派生
      - nonce / ct 从 lic_core 中读取
      - AAD 必须与发行端一致（默认 LICENSE_AAD）
    """
    if AESGCM is None:
        raise RuntimeError(
            "缺少依赖 cryptography，无法解密。请安装：pip install cryptography"
        )

    nonce = _b64d(str(lic_core["nonce_b64"]))
    ct = _b64d(str(lic_core["ct_b64"]))

    aes_key = derive_aes_key(app_secret_b64, expected_fingerprint_sha256)

    aesgcm = AESGCM(aes_key)
    try:
        payload_bytes = aesgcm.decrypt(nonce, ct, license_aad)
    except Exception:
        raise RuntimeError(
            "许可证解密失败：可能为非授权机器 / 许可证损坏 / AAD 或派生规则不一致"
        )

    try:
        payload = json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        raise RuntimeError("许可证 payload 解析失败：解密结果不是合法 JSON")

    if not isinstance(payload, dict):
        raise RuntimeError("许可证 payload 格式错误：payload 不是 JSON dict")

    return payload


# =============================👐Seperate👐=============================
# [CHANGED] payload 业务规则校验（绑定 + 有效期 + fingerprint_source）
# =============================👐Seperate👐=============================


def verify_payload_rules(
    payload: Dict[str, Any],
    expected_fingerprint_sha256: str,
    fingerprint_material: Dict[str, Any],
) -> None:
    """
    [CHANGED]
    校验规则：
      1) fingerprint_sha256 绑定校验
      2) fingerprint_source（可选）与当前 material["source"] 一致 [NEW]
      3) not_before_utc / not_after_utc 时间窗口（UTC）

    设计说明：
      - 1) 是强绑定：确保这份 license 是给“当前机器指纹”签发的
      - 2) 是语义绑定：确保这份 license 的“绑定来源”不被误用（例如容器里用 native）
      - 3) 是时间授权窗口：别人即便复制 license，也无法靠改日期绕过（改了会验签失败）
    """
    # -------------- step: 1) fingerprint 绑定校验 ---------
    fp_in_payload = str(payload.get("fingerprint_sha256", "")).strip().lower()
    if fp_in_payload and fp_in_payload != expected_fingerprint_sha256.strip().lower():
        raise RuntimeError(
            "许可证绑定校验失败：payload 内 fingerprint_sha256 与当前机器不匹配"
        )

    # -------------- step: 2) [NEW] fingerprint_source 语义绑定（可选） ---------
    # 若发行端未写此字段，则不强制；建议你后续在签发端写入，避免误签发。
    src_in_payload = str(payload.get("fingerprint_source", "")).strip()
    src_now = str(fingerprint_material.get("source", "")).strip()
    if src_in_payload:
        if src_in_payload != src_now:
            raise RuntimeError(
                "许可证绑定来源校验失败：当前环境与许可证绑定规定来源不一致"
            )

    # -------------- step: 3) 时间窗口字段检查 ---------
    nb = str(payload.get("not_before_utc", "")).strip()
    na = str(payload.get("not_after_utc", "")).strip()
    if not nb or not na:
        raise RuntimeError("许可证缺少有效期字段：not_before_utc / not_after_utc")

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


def check_license_or_raise(
    issuer_public_key_b64: str,
    license_master_key_b64: str,
    app_secret_b64: str,
    license_aad: bytes = "LICv2".encode("utf-8"),
    license_path: str = "/app/license.lic",
    allowed_container_sources: Optional[Set[str]] = None,
) -> Dict[str, Any]:
    """
    主入口：
      - 校验配置（依赖/密钥）
      - 生成 expected_fingerprint_sha256（并获得 material/source）[CHANGED]
      - 读取 .lic
      - 验签（公钥）
      - 解密（AES-GCM）
      - 校验绑定与有效期（以及 fingerprint_source 可选校验）[CHANGED]

    成功返回 payload（你可用来做 features/limits 等授权策略）
    """
    # -------------- step: 统一命名优先 LICENSE_MASTER_KEY_B64，否则 APP_SECRET_B64 ---------
    effective_app_secret_b64 = license_master_key_b64 or app_secret_b64

    # -------------- step: [NEW] 配置/依赖强校验 ---------
    _require_config_or_fail(
        issuer_public_key_b64=issuer_public_key_b64,
        effective_app_secret_b64=effective_app_secret_b64,
    )

    # -------------- step: [NEW] 容器内允许的 source（白名单） ---------
    # - host-attest        : Windows 宿主机 Docker 推荐
    # - docker-host-mount  : Linux 宿主机 Docker 推荐
    if allowed_container_sources is None:
        allowed_container_sources = {"host-attest", "docker-host-mount"}

    # -------------- step: [CHANGED] 生成期望指纹（多环境统一） ---------
    expected_fingerprint_sha256, fp_material = build_expected_fingerprint(
        allowed_container_sources=allowed_container_sources
    )

    # -------------- step: 读取 .lic ---------
    lic = load_lic_file(license_path)

    # -------------- step: 验签（防篡改） ---------
    lic_core = verify_lic_signature(issuer_public_key_b64, lic)

    # -------------- step: 解密 payload（防止直接读取 license） ---------
    payload = decrypt_lic_payload(
        effective_app_secret_b64,
        expected_fingerprint_sha256,
        lic_core,
        license_aad,
    )

    # -------------- step: [CHANGED] 业务规则校验（绑定+来源+有效期） ---------
    verify_payload_rules(payload, expected_fingerprint_sha256, fp_material)

    return payload


# =============================👐Seperate👐=============================
# main（示例）：作为 entrypoint 的最小守护
# =============================👐Seperate👐=============================


def check_license(
    issuer_public_key_b64: str,
    license_master_key_b64: str,
    app_secret_b64: str,
    license_path: str = "/app/license.lic",
    license_aad: bytes = "LICv2".encode("utf-8"),
    allowed_container_sources: Optional[Set[str]] = None,
) -> int:
    """
    检查许可证有效性
    """
    _payload = check_license_or_raise(
        issuer_public_key_b64=issuer_public_key_b64,
        license_master_key_b64=license_master_key_b64,
        app_secret_b64=app_secret_b64,
        license_aad=license_aad,
        license_path=license_path,
        allowed_container_sources=allowed_container_sources,
    )
    # 通过后可继续启动你的服务；这里只示例打印
    print("License OK. Host authorized.")
    return 0


if __name__ == "__main__":
    pass
