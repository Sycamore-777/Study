# host_attest_gen.py  （在 Windows 宿主机运行）
import json
from datetime import datetime, timezone

import host_fingerprint  # 复用你已有的 collect_windows_ids()


def main():
    win_ids = host_fingerprint.collect_windows_ids()

    attest = {
        "platform": "windows",
        "source": "host-attest",
        "machine_guid": win_ids.get("machine_guid", ""),
        "wmi_uuid": win_ids.get("wmi_uuid", ""),
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    with open("host_attest.json", "w", encoding="utf-8") as f:
        json.dump(attest, f, ensure_ascii=False, indent=2)

    print("written: host_attest.json")


if __name__ == "__main__":
    main()
