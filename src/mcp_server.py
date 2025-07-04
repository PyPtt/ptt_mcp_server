import os
from typing import Dict, Any

from dotenv import load_dotenv
from fastmcp import FastMCP

import basic_api
from _version import __version__

load_dotenv(override=True)

PTT_ID = os.getenv("PTT_ID")
PTT_PW = os.getenv("PTT_PW")

if not PTT_ID or not PTT_PW:
    raise ValueError("PTT_ID and PTT_PW environment variables must be set.")

mcp: FastMCP = FastMCP(f"Ptt MCP Server v{__version__}")

MEMORY_STORAGE: Dict[str, Any] = {"ptt_bot": None, "ptt_id": PTT_ID, "ptt_pw": PTT_PW}


def main():
    basic_api.register_tools(mcp, MEMORY_STORAGE, __version__)
    mcp.run()


if __name__ == "__main__":
    main()
