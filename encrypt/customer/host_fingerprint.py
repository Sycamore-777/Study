# -*- coding: utf-8 -*-
# %%
"""
文件名    : host_fingerprint.py
创建者    : Sycamore
创建日期  : 2026-01-16
最后修改  : 2026-01-16
版本号    : v1.1.0

■ 用途说明:
  统一的宿主机指纹生成模块（fingerprint_sha256），覆盖：
  - Windows 本机（native）
  - Linux 本机（native）
  - Linux 宿主机 Docker（通过 /host 挂载读取宿主机标识：docker-host-mount）
  - Windows 宿主机 Docker Desktop/WSL2（通过 host_attest.json 只读挂载读取：host-attest）

  重点目标：
  1) “绑定物理机”时，避免容器内 native 退化为“绑定容器/WSL/VM”。
  2) 每一种来源都做“至少一个关键标识存在”的强校验，避免生成空/弱指纹。
  3) 提供明确的运行模式控制（host/native/auto），使行为可控、可审计。

■ 主要函数功能:
  - build_fingerprint: 选择 Provider 并生成 fingerprint_sha256（hex）
  - is_running_in_container: 尽力检测容器环境（用于策略判断，非绝对）
  - load_host_attest: 读取宿主机证明文件（Windows Docker 推荐）
  - collect_linux_ids: 读取 Linux 标识（本机或 /host 挂载）
  - collect_windows_ids: 读取 Windows 标识（本机）
  - validate_*: 各 Provider 强校验（machine-id/uuid 至少一个等）

■ 功能特性:
  ✓ Provider 优先级：host-attest > docker-host-mount > native
  ✓ 模式控制：FINGERPRINT_MODE=host/native/auto（默认 auto）
  ✓ Docker 场景默认拒绝 native（防止绑定容器/VM），除非显式放行
  ✓ 每一种 Provider 都做“必需字段至少一个”的强校验
  ⚠ host_attest 的可信度取决于 attest 文件本身是否做了签名/验签（建议配合 Ed25519）

■ 待办事项:
  - [ ] host_attest 文件增加签名验签（建议 Ed25519），避免客户伪造
  - [ ] 增加更多 Windows 标识来源与容错（如 CIM/WMI 兼容、权限受限提示）
  - [ ] 增加“指纹材料脱敏输出”工具（便于排障但不泄露敏感信息）

■ 更新日志:
  v1.1.0 (2026-01-16): 增加模式控制、容器内禁止 native、以及各 Provider 的强校验

"心之所向，素履以往；生如逆旅，一苇以航。"
"""

# ==============================================================
# %%
import hashlib
import json
import os
import platform
import subprocess
from typing import Any, Dict, Optional, Tuple


# =============================👐Seperate👐=============================
# 配置区
# =============================👐Seperate👐=============================

# -------------- step: Docker(Linux) 宿主机标识挂载路径（容器内读取） ---------
# docker run 示例（Linux 宿主机）：
#   -v /etc/machine-id:/host/etc/machine-id:ro
#   -v /sys/class/dmi/id:/host/sys/class/dmi/id:ro
HOST_MOUNT_MACHINE_ID = os.getenv("HOST_MACHINE_ID_PATH", "/host/etc/machine-id")
HOST_MOUNT_DMI_DIR = os.getenv("HOST_DMI_DIR", "/host/sys/class/dmi/id")

# -------------- step: Windows 宿主机 Docker 推荐：host_attest.json 挂载路径 ---------
# docker run 示例（Windows 宿主机）：
#   -v C:\path\host_attest.json:/host/attest/host_attest.json:ro
HOST_ATTEST_PATH = os.getenv("HOST_ATTEST_PATH", "/host/attest/host_attest.json")

# -------------- step: 模式控制（非常关键） ---------
# FINGERPRINT_MODE:
#   - host  : 只允许宿主机来源（host-attest / docker-host-mount）；拿不到就失败（交付推荐）
#   - native: 只允许本机来源（Windows/Linux 本机工具）；Docker 内默认拒绝
#   - auto  : 非容器 -> native；容器 -> host（更安全的自动）
FINGERPRINT_MODE = os.getenv("FINGERPRINT_MODE", "auto").strip().lower()

# -------------- step: 是否允许“容器内 native” ---------
# 仅用于你内部调试（强烈不建议交付时开启）
ALLOW_INSECURE_DOCKER_NATIVE = os.getenv(
    "ALLOW_INSECURE_DOCKER_NATIVE", "0"
).strip().lower() in (
    "1",
    "true",
    "yes",
)

# -------------- step: 调试输出（生产建议关闭） ---------
# 为了避免泄露敏感信息，默认不打印 material
DEBUG_PRINT_MATERIAL = os.getenv("DEBUG_PRINT_MATERIAL", "0").strip().lower() in (
    "1",
    "true",
    "yes",
)


# =============================👐Seperate👐=============================
# 工具函数
# =============================👐Seperate👐=============================


def canonical_json(obj: Dict[str, Any]) -> bytes:
    """
    确定性 JSON 序列化：
      - sort_keys=True        : 键排序，保证跨平台/跨进程一致
      - separators=(",", ":") : 去掉多余空格，保证字节级一致
      - ensure_ascii=False    : 保留原字符（不影响一致性）
    """
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """对 bytes 做 SHA-256，输出 hex 字符串"""
    return hashlib.sha256(data).hexdigest()


def read_text(path: str) -> str:
    """
    安全读取文本文件并 strip。
    读取失败/文件不存在时返回空串，便于上层做“至少一个字段存在”的判断。
    """
    try:
        if not os.path.exists(path):
            return ""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read().strip()
    except Exception:
        return ""


# =============================👐Seperate👐=============================
# 容器环境检测（尽力而为：不能保证不漏检/误检）
# =============================👐Seperate👐=============================


def is_running_in_container() -> bool:
    """
    目的：
      - 识别当前进程是否大概率运行在 Docker/容器环境中
      - 用于策略选择（例如：auto 模式下容器强制走 host；native 模式下容器默认拒绝）

    注意：
      - 这是启发式检测，无法做到 100% 不漏检/不误检。
      - 交付场景推荐用 FINGERPRINT_MODE=host 来“强制要求宿主机来源”，
        从而不依赖该检测的绝对正确性。
    """
    # -------------- step: Docker 常见标记文件 ---------
    if os.path.exists("/.dockerenv"):
        return True

    # -------------- step: Podman 等环境常见标记 ---------
    if os.path.exists("/run/.containerenv"):
        return True

    # -------------- step: cgroup 特征（docker/containerd/k8s） ---------
    cgroup_paths = ("/proc/1/cgroup", "/proc/self/cgroup")
    for p in cgroup_paths:
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


# =============================👐Seperate👐=============================
# Provider 1: 宿主机证明文件（Windows 宿主机 Docker 推荐）
# =============================👐Seperate👐=============================


def load_host_attest(path: str = HOST_ATTEST_PATH) -> Optional[Dict[str, Any]]:
    """
    读取宿主机证明文件（host_attest.json）。

    设计意图：
      - Windows 宿主机 Docker Desktop/WSL2 场景下，容器无法直读 Windows 的注册表/WMI/DMI，
        因此需要 Windows 侧小工具生成一份证明文件并只读挂载到容器。
      - 未来建议对 attest 文件做签名（Ed25519），容器内做验签，防止伪造。

    最简结构建议（示例）：
      {
        "platform": "windows",
        "source": "host-attest",
        "machine_guid": "...",
        "wmi_uuid": "...",
        "ts_utc": "2026-01-16T00:00:00Z"
      }

    返回：
      - 合法 dict -> dict
      - 文件不存在/格式不符 -> None
    """
    if not os.path.exists(path):
        return None

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # -------------- step: 类型与来源字段最基本校验 ---------
        if not isinstance(data, dict):
            return None
        if data.get("source") != "host-attest":
            return None

        return data
    except Exception:
        return None


# =============================👐Seperate👐=============================
# Provider 2: Linux 标识（本机或 /host 挂载）
# =============================👐Seperate👐=============================


def collect_linux_ids(machine_id_path: str, dmi_dir: str) -> Dict[str, str]:
    """
    读取 Linux 标识：
      - machine_id    : /etc/machine-id（或容器内挂载 /host/etc/machine-id）
      - product_uuid  : /sys/class/dmi/id/product_uuid
      - board_serial  : /sys/class/dmi/id/board_serial
      - chassis_serial: /sys/class/dmi/id/chassis_serial

    注意：
      - 在容器中读取 /etc/machine-id 通常是“容器自身/镜像层”的标识，不能代表宿主机。
      - 因此容器场景下务必读取 /host/...（host-mount）或 host-attest。
    """
    machine_id = read_text(machine_id_path)

    product_uuid = read_text(os.path.join(dmi_dir, "product_uuid"))
    board_serial = read_text(os.path.join(dmi_dir, "board_serial"))
    chassis_serial = read_text(os.path.join(dmi_dir, "chassis_serial"))

    return {
        "machine_id": machine_id,
        "product_uuid": product_uuid,
        "board_serial": board_serial,
        "chassis_serial": chassis_serial,
    }


# =============================👐Seperate👐=============================
# Provider 3: Windows 标识（本机）
# =============================👐Seperate👐=============================


def _run_cmd(cmd: str) -> str:
    """
    执行命令并返回 stdout（失败返回空串）。
    这里用 shell=True 是为了兼容 Windows 的 reg/wmic 调用方式。
    """
    try:
        out = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore").strip()
    except Exception:
        return ""


def collect_windows_ids() -> Dict[str, str]:
    """
    读取 Windows 标识（本机）：
      - machine_guid: 注册表 HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid
      - wmi_uuid    : wmic csproduct get uuid

    说明：
      - 在某些企业环境或权限受限环境，reg/wmic 可能不可用。
      - wmic 在较新 Windows 版本中可能被弱化/移除；你可后续改为 powershell CIM 查询。
    """
    # -------------- step: 读取 MachineGuid（注册表） ---------
    machine_guid_raw = _run_cmd(
        r'reg query "HKLM\SOFTWARE\Microsoft\Cryptography" /v MachineGuid'
    )
    machine_guid = ""
    if machine_guid_raw:
        # reg query 输出一般是：MachineGuid    REG_SZ    xxxxxxxx-....
        parts = machine_guid_raw.split()
        machine_guid = parts[-1] if parts else machine_guid_raw.strip()

    # -------------- step: WMI 读取 UUID ---------
    # 输出示例：
    #   UUID
    #   XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
    wmi_uuid_raw = _run_cmd("wmic csproduct get uuid")
    wmi_uuid = ""
    if wmi_uuid_raw:
        lines = [ln.strip() for ln in wmi_uuid_raw.splitlines() if ln.strip()]
        # 通常最后一行是 UUID 值（第一行是标题 UUID）
        wmi_uuid = lines[-1] if lines else ""

    return {
        "machine_guid": machine_guid,
        "wmi_uuid": wmi_uuid,
    }


# =============================👐Seperate👐=============================
# 强校验：确保每一种来源至少有一个“可绑定标识”
# =============================👐Seperate👐=============================


def validate_linux_ids(ids: Dict[str, str], context: str) -> None:
    """
    Linux 侧强校验：
      - machine_id / product_uuid 至少一个非空

    为什么：
      - 这些字段可能因为挂载失败、权限限制、或系统裁剪而为空
      - 若不校验直接哈希，可能得到“弱指纹”（可迁移/可复现风险增大）
    """
    if (not ids.get("machine_id")) and (not ids.get("product_uuid")):
        raise RuntimeError(
            f"[{context}] Missing linux ids: need machine_id or product_uuid at least one"
        )


def validate_windows_ids(ids: Dict[str, str], context: str) -> None:
    """
    Windows 侧强校验：
      - machine_guid / wmi_uuid 至少一个“有效”

    常见无效 UUID（部分环境会返回这种占位值）：
      - FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF
      - 00000000-0000-0000-0000-000000000000
    """
    machine_guid = (ids.get("machine_guid") or "").strip()
    wmi_uuid = (ids.get("wmi_uuid") or "").strip()

    invalid_wmi = {
        "",
        "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF",
        "00000000-0000-0000-0000-000000000000",
    }

    ok_guid = bool(machine_guid)
    ok_uuid = bool(wmi_uuid) and (wmi_uuid.upper() not in invalid_wmi)

    if (not ok_guid) and (not ok_uuid):
        raise RuntimeError(
            f"[{context}] Missing windows ids: need machine_guid or valid wmi_uuid at least one"
        )


def validate_host_attest(attest: Dict[str, Any], context: str) -> None:
    """
    host_attest 强校验：
      建议 attest 至少包含以下之一：
        - fingerprint_sha256（强烈推荐由宿主机端计算好）
        - Windows: machine_guid / wmi_uuid
        - Linux  : machine_id / product_uuid

    说明：
      - 最佳实践：attest 文件携带 fingerprint_sha256，并且对整个 attest 做签名。
      - 若没有 fingerprint_sha256，本模块会对 attest 全量 dict canonical_json 后做 sha256，
        也能工作，但更依赖字段齐全与稳定性。
    """
    fp = str(attest.get("fingerprint_sha256", "")).strip()
    if fp:
        return

    # windows-like
    mg = str(attest.get("machine_guid", "")).strip()
    wu = str(attest.get("wmi_uuid", "")).strip()

    # linux-like
    mid = str(attest.get("machine_id", "")).strip()
    pu = str(attest.get("product_uuid", "")).strip()

    if not (mg or wu or mid or pu):
        raise RuntimeError(
            f"[{context}] Invalid host_attest: need fingerprint_sha256 or at least one id field"
        )


# =============================👐Seperate👐=============================
# 统一入口：自动选择 Provider 并生成 fingerprint
# =============================👐Seperate👐=============================


def build_fingerprint() -> Tuple[str, Dict[str, Any]]:
    """
    返回:
      - fingerprint_sha256 (hex)
      - material dict（可用于日志审计；生产建议不要完整输出）

    Provider 选择（优先级固定）：
      1) host-attest        : 读取 host_attest.json（Windows 宿主机 Docker 推荐）
      2) docker-host-mount  : 读取 /host/etc/machine-id 与 /host/sys/class/dmi/id（Linux 宿主机 Docker）
      3) native             : Windows/Linux 本机直读（非容器/或明确允许）

    模式控制（决定是否允许回退）：
      - FINGERPRINT_MODE=host
          只允许 1/2；拿不到直接失败（交付推荐：防止绑定容器/WSL/VM）
      - FINGERPRINT_MODE=native
          只允许 3；Docker 内默认拒绝（避免容器绑定）
      - FINGERPRINT_MODE=auto
          非容器 -> native；容器 -> host（更安全的自动）

    安全提示：
      - 如果你要实现“镜像只能在某台物理机运行”，交付时应设置 FINGERPRINT_MODE=host，
        并要求客户正确挂载 /host/... 或 /host/attest/...。
    """
    # -------------- step: 判断是否在容器中（用于 auto/native 策略） ---------
    in_container = is_running_in_container()

    # -------------- step: 规范化 mode ---------
    mode = FINGERPRINT_MODE
    if mode not in ("host", "native", "auto"):
        raise RuntimeError(
            f"Invalid FINGERPRINT_MODE: {mode} (allowed: host/native/auto)"
        )

    # -------------- step: auto 模式：容器优先 host；非容器走 native ---------
    if mode == "auto":
        mode = "host" if in_container else "native"

    # =========================
    # host 模式：只允许宿主机来源
    # =========================
    if mode == "host":
        # -------------- step: Provider 1 - host-attest ---------
        attest = load_host_attest()
        if attest is not None:
            validate_host_attest(attest, context="host-attest")

            # material 直接使用 attest 全量 dict（canonical_json 后稳定哈希）
            material = dict(attest)
            fp = sha256_hex(canonical_json(material))
            return fp, material

        # -------------- step: Provider 2 - docker-host-mount（Linux 宿主机） ---------
        linux_ids = collect_linux_ids(HOST_MOUNT_MACHINE_ID, HOST_MOUNT_DMI_DIR)
        if linux_ids.get("machine_id") or linux_ids.get("product_uuid"):
            validate_linux_ids(linux_ids, context="docker-host-mount")

            material = {
                "platform": "linux",
                "source": "docker-host-mount",
                **linux_ids,
            }
            fp = sha256_hex(canonical_json(material))
            return fp, material

        # -------------- step: host 模式下不能回退到 native，必须失败 ---------
        raise RuntimeError(
            "Host fingerprint source not found.\n"
            "If running in Docker:\n"
            "  - Linux host: mount /etc/machine-id and /sys/class/dmi/id into /host (read-only)\n"
            "  - Windows host: provide /host/attest/host_attest.json (read-only)\n"
            f"Checked paths:\n"
            f"  HOST_ATTEST_PATH={HOST_ATTEST_PATH}\n"
            f"  HOST_MOUNT_MACHINE_ID={HOST_MOUNT_MACHINE_ID}\n"
            f"  HOST_MOUNT_DMI_DIR={HOST_MOUNT_DMI_DIR}\n"
        )

    # =========================
    # native 模式：只允许本机来源
    # =========================
    if mode == "native":
        # -------------- step: 容器内默认拒绝 native（防止绑定容器/WSL/VM） ---------
        if in_container and (not ALLOW_INSECURE_DOCKER_NATIVE):
            raise RuntimeError(
                "Refuse to use native fingerprint inside container.\n"
                "Reason: native fingerprint inside Docker/WSL/VM may bind to container/VM instead of shown physical host.\n"
                "Fix:\n"
                "  - Use FINGERPRINT_MODE=host and mount host ids/attest properly.\n"
                "Debug only:\n"
                "  - Set ALLOW_INSECURE_DOCKER_NATIVE=1 (NOT recommended for delivery).\n"
            )

        sysname = platform.system().lower()

        # -------------- step: Windows 本机 ---------
        if sysname == "windows":
            win_ids = collect_windows_ids()
            validate_windows_ids(win_ids, context="native-windows")

            material = {"platform": "windows", "source": "native", **win_ids}
            fp = sha256_hex(canonical_json(material))
            return fp, material

        # -------------- step: Linux 本机 ---------
        if sysname == "linux":
            linux_native = collect_linux_ids("/etc/machine-id", "/sys/class/dmi/id")
            validate_linux_ids(linux_native, context="native-linux")

            material = {"platform": "linux", "source": "native", **linux_native}
            fp = sha256_hex(canonical_json(material))
            return fp, material

        raise RuntimeError(f"Unsupported platform: {platform.system()}")

    # -------------- step: 理论不可达 ---------
    raise RuntimeError("Unreachable state in build_fingerprint()")


# =============================👐Seperate👐=============================
# CLI 测试入口
# =============================👐Seperate👐=============================

if __name__ == "__main__":
    fp, mat = build_fingerprint()
    print(fp)

    # -------------- step: 调试时可输出 material（生产慎用） ---------
    if DEBUG_PRINT_MATERIAL:
        print(json.dumps(mat, ensure_ascii=False, indent=2))
