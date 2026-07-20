import os
import sys

import pytest

# utils._handle_ptt_exception builds EXCEPTION_MAPPING from real PyPtt exception
# classes, so it needs the real PyPtt (not the empty stub sibling tests inject).
# Swap it in, then restore sys.modules so those tests aren't disturbed.
_SHARED = ("PyPtt", "utils")


def test_parameter_error_maps_to_parameter_error_code():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    snapshot = {m: sys.modules.get(m) for m in _SHARED}
    try:
        if not getattr(sys.modules.get("PyPtt"), "__file__", None):
            for m in _SHARED:
                sys.modules.pop(m, None)
        import PyPtt

        if not hasattr(PyPtt, "ParameterError"):
            pytest.skip("real PyPtt not installed")
        import utils

        # ParameterError → 專屬 PARAMETER_ERROR，且保留 PyPtt 的原始訊息。
        result = utils._handle_ptt_exception(PyPtt.ParameterError("boom"), {})
        assert result["success"] is False
        assert result["code"] == "PARAMETER_ERROR"
        assert "boom" in result["message"]

        # 其他未收錄的例外仍走 UNKNOWN_ERROR（回歸保護）。
        other = utils._handle_ptt_exception(RuntimeError("x"), {})
        assert other["code"] == "UNKNOWN_ERROR"
    finally:
        for m in _SHARED:
            mod = snapshot[m]
            if mod is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = mod


if __name__ == "__main__":
    test_parameter_error_maps_to_parameter_error_code()
    print("OK")
