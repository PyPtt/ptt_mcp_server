import os
import sys
import types


class _FakeFastMCP:
    # mcp_server 會在模組載入時執行 FastMCP(name)，stub 需可帶參數實例化。
    def __init__(self, *args, **kwargs):
        pass


def _load_parse_accounts():
    # Allow running from the repo root: `python src/test_parse_accounts.py`.
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # mcp_server (via api_ptt/api_post/utils) imports PyPtt and fastmcp at
    # module load time. Those are heavy runtime deps that may not be installed
    # in a test environment, so stub them out before importing.
    sys.modules.setdefault("PyPtt", types.ModuleType("PyPtt"))
    fastmcp_mod = sys.modules.get("fastmcp")
    if fastmcp_mod is None:
        fastmcp_mod = types.ModuleType("fastmcp")
        sys.modules["fastmcp"] = fastmcp_mod
    # 其他測試檔的 stub 以 object 佔位，無法帶參數實例化，這裡一併升級。
    if getattr(fastmcp_mod, "FastMCP", None) in (None, object):
        setattr(fastmcp_mod, "FastMCP", _FakeFastMCP)

    # mcp_server 載入時會讀取環境變數並驗證至少有一組帳號。
    os.environ.pop("PTT_ACCOUNTS", None)
    os.environ.setdefault("PTT_ID", "testid")
    os.environ.setdefault("PTT_PW", "testpw")

    from mcp_server import parse_accounts

    return parse_accounts


def test_parse_accounts_basic():
    parse_accounts = _load_parse_accounts()

    assert parse_accounts("default=a:b,alt=c:d") == {
        "default": {"id": "a", "pw": "b"},
        "alt": {"id": "c", "pw": "d"},
    }


def test_parse_accounts_strips_whitespace():
    parse_accounts = _load_parse_accounts()

    assert parse_accounts(" default = a:b ") == {"default": {"id": "a", "pw": "b"}}


def test_parse_accounts_invalid():
    parse_accounts = _load_parse_accounts()

    for raw in [
        "noequal",  # 缺 =
        "name=nocolon",  # 缺 :
        "=a:b",  # 空名稱
        "name=:pw",  # 空帳號
        "name=a:",  # 空密碼
    ]:
        try:
            parse_accounts(raw)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {raw!r}")


if __name__ == "__main__":
    test_parse_accounts_basic()
    test_parse_accounts_strips_whitespace()
    test_parse_accounts_invalid()
    print("OK")
