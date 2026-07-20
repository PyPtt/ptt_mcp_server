import os
import sys

import pytest

# api_ptt / utils / PyPtt are shared via sys.modules. Sibling tests stub PyPtt
# (an empty ModuleType) so they can run without it installed, and monkeypatch
# api_ptt.PyPtt. This test needs the REAL PyPtt.BadPostType, so it briefly
# swaps in the real modules and restores the exact prior sys.modules state in a
# finally block — otherwise reloading api_ptt would leak into those tests.
_SHARED = ("PyPtt", "utils", "api_ptt")


def _load_real_api_ptt():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)
    # Evict any stub PyPtt (no __file__) and the modules that bound it.
    if not getattr(sys.modules.get("PyPtt"), "__file__", None):
        for m in _SHARED:
            sys.modules.pop(m, None)
    import PyPtt

    if not hasattr(PyPtt, "BadPostType"):
        pytest.skip("real PyPtt not installed; helper needs PyPtt.BadPostType")
    import api_ptt

    return api_ptt, PyPtt


def test_bad_post_type_from_name():
    snapshot = {m: sys.modules.get(m) for m in _SHARED}
    try:
        api_ptt, PyPtt = _load_real_api_ptt()

        # Every valid name maps to the same IntEnum member (MCP sends a string,
        # PyPtt wants the enum).
        for name in ("AD", "BAD_LANGUAGE", "PERSONAL_ATTACK", "OTHER"):
            assert api_ptt._bad_post_type_from_name(name) is PyPtt.BadPostType[name]

        # None means "no bad-post", passes straight through.
        assert api_ptt._bad_post_type_from_name(None) is None

        # Unknown name raises ValueError (del_post turns it into a BAD_PARAM error).
        with pytest.raises(ValueError):
            api_ptt._bad_post_type_from_name("NOPE")
    finally:
        for m in _SHARED:
            mod = snapshot[m]
            if mod is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = mod


if __name__ == "__main__":
    test_bad_post_type_from_name()
    print("OK")
