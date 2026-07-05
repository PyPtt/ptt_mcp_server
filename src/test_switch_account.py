import os
import sys
import types


class _FakeMCP:
    # Minimal stand-in for FastMCP that just records registered tools.
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def _load_api_ptt():
    # Allow running from the repo root: `python src/test_switch_account.py`.
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # api_ptt (and utils) import PyPtt and fastmcp at module load time. Those
    # are heavy runtime deps that may not be installed in a test environment,
    # so stub them out before importing.
    sys.modules.setdefault("PyPtt", types.ModuleType("PyPtt"))
    if "fastmcp" not in sys.modules:
        fastmcp_stub = types.ModuleType("fastmcp")
        setattr(fastmcp_stub, "FastMCP", object)
        sys.modules["fastmcp"] = fastmcp_stub

    import api_ptt

    return api_ptt


def _register_tools(api_ptt):
    mcp = _FakeMCP()
    memory_storage = {
        "ptt_bot": None,
        "ptt_id": "acc1",
        "ptt_pw": "pw1",
        "accounts": {
            "default": {"id": "acc1", "pw": "pw1"},
            "alt": {"id": "acc2", "pw": "pw2"},
        },
        "current_account": "default",
    }
    api_ptt.register_tools(mcp, memory_storage, "0.0.0")
    return mcp.tools, memory_storage


def test_switch_account_unknown_name():
    api_ptt = _load_api_ptt()
    tools, memory_storage = _register_tools(api_ptt)

    original = api_ptt._perform_login
    setattr(api_ptt, "_perform_login", lambda storage: {"success": True})
    try:
        result = tools["switch_account"]("nope")
    finally:
        setattr(api_ptt, "_perform_login", original)

    assert result["success"] is False
    assert sorted(result["available"]) == ["alt", "default"]
    # 找不到帳號時不得改動現有帳密與登入狀態
    assert memory_storage["ptt_id"] == "acc1"
    assert memory_storage["ptt_pw"] == "pw1"
    assert memory_storage["current_account"] == "default"


def test_switch_account_success():
    api_ptt = _load_api_ptt()
    tools, memory_storage = _register_tools(api_ptt)

    original = api_ptt._perform_login
    setattr(api_ptt, "_perform_login", lambda storage: {"success": True})
    try:
        result = tools["switch_account"]("alt")
    finally:
        setattr(api_ptt, "_perform_login", original)

    assert result["success"] is True
    assert result["current"] == "alt"
    assert result["message"] == "已切換到帳號 'alt' 並登入成功"
    assert memory_storage["ptt_id"] == "acc2"
    assert memory_storage["ptt_pw"] == "pw2"
    assert memory_storage["current_account"] == "alt"


def test_list_accounts():
    api_ptt = _load_api_ptt()
    tools, memory_storage = _register_tools(api_ptt)

    result = tools["list_accounts"]()
    assert result["success"] is True
    assert sorted(result["accounts"]) == ["alt", "default"]
    assert result["current"] == "default"

    memory_storage["current_account"] = "alt"
    assert tools["list_accounts"]()["current"] == "alt"


if __name__ == "__main__":
    test_switch_account_unknown_name()
    test_switch_account_success()
    test_list_accounts()
    print("OK")
