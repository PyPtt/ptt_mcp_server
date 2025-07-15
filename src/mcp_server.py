import os
from typing import Dict, Any

from fastmcp import FastMCP

import api_post
import api_ptt
from _version import __version__

PTT_ID = os.getenv("PTT_ID")
PTT_PW = os.getenv("PTT_PW")

if not PTT_ID or not PTT_PW:
    raise ValueError("PTT_ID and PTT_PW environment variables must be set.")

mcp: FastMCP = FastMCP(f"Ptt MCP Server v{__version__}")

MEMORY_STORAGE: Dict[str, Any] = {"ptt_bot": None, "ptt_id": PTT_ID, "ptt_pw": PTT_PW}


def main():
    api_ptt.register_tools(mcp, MEMORY_STORAGE, __version__)
    api_post.register_tools(mcp, MEMORY_STORAGE, __version__)

    mcp.run()


if __name__ == "__main__":
    main()
