"""저장용 비밀값 암호화.

Windows 에서는 DPAPI(CryptProtectData)로 암호화한다.
  - 현재 Windows 사용자 + 그 PC 에서만 복호화 가능
  - 파일이 유출돼도 다른 계정/PC 에서는 못 푼다
  - 별도 설치 없이 OS 내장 기능(ctypes) 사용

Windows 가 아니면(예: 개발/테스트) 평문으로 두되 enc='plain' 으로 표시한다.
"""

from __future__ import annotations

import base64
import sys


def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _dpapi(method: str, data: bytes) -> bytes:
    import ctypes
    import ctypes.wintypes as wt

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wt.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    buf = ctypes.create_string_buffer(data, len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()

    fn = getattr(ctypes.windll.crypt32, method)
    ok = fn(
        ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)
    )
    if not ok:
        raise OSError(f"{method} 실패")
    try:
        out = ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return out


def encrypt(text: str) -> tuple[str, str]:
    """(enc, value) 를 돌려준다. enc 는 'dpapi' 또는 'plain'."""
    if _is_windows():
        try:
            enc_bytes = _dpapi("CryptProtectData", text.encode("utf-8"))
            return "dpapi", base64.b64encode(enc_bytes).decode("ascii")
        except Exception:
            pass
    return "plain", text


def decrypt(enc: str, value: str) -> str:
    if enc == "dpapi":
        try:
            raw = base64.b64decode(value)
            return _dpapi("CryptUnprotectData", raw).decode("utf-8")
        except Exception:
            return ""
    return value
