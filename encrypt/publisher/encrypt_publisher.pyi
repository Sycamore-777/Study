# -*- coding: utf-8 -*-
# %%

# -------------- func: 生成一组私钥-公钥 ---------
def create_keys(): ...

# -------------- func: 生成license ---------
def create_license(
    private_key_b64: str,
    master_key_b64: str,
    target_fingerprint_sha256: str,
    fingerprint_source: str,
    issued_to: str,
    license_id: str,
    not_before_utc: str,
    not_after_utc: str,
): ...
