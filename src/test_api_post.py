import os
import sys
import types


def _load_helpers():
    # Allow running from the repo root: `python src/test_api_post.py`.
    src_dir = os.path.dirname(os.path.abspath(__file__))
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

    # api_post (via utils) imports PyPtt and fastmcp at module load time. Those
    # are heavy runtime deps that may not be installed in a test environment, so
    # stub them out before importing the pure date helpers we want to test.
    sys.modules.setdefault("PyPtt", types.ModuleType("PyPtt"))
    if "fastmcp" not in sys.modules:
        fastmcp_stub = types.ModuleType("fastmcp")
        setattr(fastmcp_stub, "FastMCP", object)
        sys.modules["fastmcp"] = fastmcp_stub

    from api_post import _md, parse_date_str

    return _md, parse_date_str


def test_md_compare():
    _md, parse_date_str = _load_helpers()

    # A target date carrying a year (e.g. "1987/09/06") must match a yearless
    # PTT list_date ("9/06") once compared via _md(). The original broken case.
    assert _md(parse_date_str("1987/09/06")) == _md(parse_date_str("9/06"))
    assert _md(parse_date_str("6/29")) == (6, 29)
    assert _md(parse_date_str("6/29")) != _md(parse_date_str("6/30"))


if __name__ == "__main__":
    test_md_compare()
    print("OK")
