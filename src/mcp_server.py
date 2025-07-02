import os
from typing import Dict, Any

import PyPtt  # type: ignore
from dotenv import load_dotenv
from fastmcp import FastMCP

import basic_api

load_dotenv(override=True)

PTT_ID = os.getenv("PTT_ID")
PTT_PW = os.getenv("PTT_PW")

if not PTT_ID or not PTT_PW:
    raise ValueError("PTT_ID and PTT_PW environment variables must be set.")

mcp: FastMCP = FastMCP("Ptt MCP Server")

MEMORY_STORAGE: Dict[str, Any] = {
    "ptt_bot": None,
    'ptt_id': PTT_ID,
    'ptt_pw': PTT_PW
}

if __name__ == '__main__':
    basic_api.register_tools(mcp, MEMORY_STORAGE)
    mcp.run()
