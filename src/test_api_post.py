import os
import sys
import types

# Allow running from the repo root: `python src/test_api_post.py`.
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# api_post (via utils) imports PyPtt and fastmcp at module load time. Those are
# heavy runtime deps that may not be installed in a test environment, so stub
# them out before importing the pure date helpers we actually want to test.
sys.modules.setdefault("PyPtt", types.ModuleType("PyPtt"))
if "fastmcp" not in sys.modules:
    fastmcp_stub = types.ModuleType("fastmcp")
    fastmcp_stub.FastMCP = object
    sys.modules["fastmcp"] = fastmcp_stub

from api_post import _md, parse_date_str

# A target date carrying a year (e.g. "1987/09/06") must match a yearless PTT
# list_date ("9/06") once compared via _md(). This was the original broken case.
assert _md(parse_date_str("1987/09/06")) == _md(parse_date_str("9/06"))

assert _md(parse_date_str("6/29")) == (6, 29)

assert _md(parse_date_str("6/29")) != _md(parse_date_str("6/30"))

print("OK")
