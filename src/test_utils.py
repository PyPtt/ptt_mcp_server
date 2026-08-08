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


def test_two_factor_auth_required_maps_to_dedicated_code():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    snapshot = {m: sys.modules.get(m) for m in _SHARED}
    try:
        if not getattr(sys.modules.get("PyPtt"), "__file__", None):
            for m in _SHARED:
                sys.modules.pop(m, None)
        import PyPtt

        if not hasattr(PyPtt, "TwoFactorAuthRequired"):
            pytest.skip("real PyPtt (>=2.3.6) not installed")
        import utils

        # PyPtt 例外的 message 來自 i18n，建構前得先 init，否則
        # 存取 .message 會噴 AttributeError（PyPtt.API 平常會幫你做這步）。
        import PyPtt.data_type as pyptt_data_type
        import PyPtt.i18n as pyptt_i18n

        pyptt_i18n.init(pyptt_data_type.Language.MANDARIN)

        # TwoFactorAuthRequired 繼承 LoginError，須確認沒被父類搶先攔截，
        # 且保留 PyPtt 的原始訊息（不是被換成「登入失敗」）。
        exc = PyPtt.TwoFactorAuthRequired()
        result = utils._handle_ptt_exception(exc, {})
        assert result["success"] is False
        assert result["code"] == "TWO_FACTOR_AUTH_REQUIRED"
        assert result["message"] == str(exc)
        assert result["message"] != "登入失敗"

        # 回歸保護：LoginError 本身仍要維持 LOGIN_FAILED，不能被上面的分支搶走。
        login_error_result = utils._handle_ptt_exception(PyPtt.LoginError(), {})
        assert login_error_result["code"] == "LOGIN_FAILED"
        assert login_error_result["message"] == "登入失敗"
    finally:
        for m in _SHARED:
            mod = snapshot[m]
            if mod is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = mod


if __name__ == "__main__":
    test_parameter_error_maps_to_parameter_error_code()
    test_two_factor_auth_required_maps_to_dedicated_code()
    print("OK")
