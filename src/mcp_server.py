import os
from typing import Dict, Any

from fastmcp import FastMCP

import api_post
import api_ptt
from _version import __version__


def parse_accounts(raw: str) -> Dict[str, Dict[str, str]]:
    """解析 PTT_ACCOUNTS 字串：'名稱=帳號:密碼,名稱2=帳號2:密碼2'。"""
    accounts: Dict[str, Dict[str, str]] = {}
    # ponytail: 逗號分隔項目、= 分名稱、: 分帳密；名稱不可含 =、帳號不可含 :、密碼不可含 ,。
    # PTT 帳號為英數、密碼 ≤8 碼，實務上不會撞到這些分隔字元；若未來要支援特殊字元再換 JSON/檔案。
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ValueError(
                f"PTT_ACCOUNTS 項目格式錯誤（需 名稱=帳號:密碼）: {entry!r}"
            )
        name, cred = entry.split("=", 1)
        name = name.strip()
        if ":" not in cred:
            raise ValueError(f"PTT_ACCOUNTS['{name}'] 需為 帳號:密碼 格式")
        acc_id, acc_pw = cred.split(":", 1)
        acc_id, acc_pw = acc_id.strip(), acc_pw.strip()
        if not name or not acc_id or not acc_pw:
            raise ValueError(f"PTT_ACCOUNTS 項目名稱/帳號/密碼不可為空: {entry!r}")
        accounts[name] = {"id": acc_id, "pw": acc_pw}
    return accounts


PTT_ID = os.getenv("PTT_ID")
PTT_PW = os.getenv("PTT_PW")
PTT_ACCOUNTS_RAW = os.getenv("PTT_ACCOUNTS")

accounts: Dict[str, Dict[str, str]] = (
    parse_accounts(PTT_ACCOUNTS_RAW) if PTT_ACCOUNTS_RAW else {}
)

# 相容舊設定：PTT_ID/PTT_PW 視為名為 default 的帳號
if PTT_ID and PTT_PW:
    accounts.setdefault("default", {"id": PTT_ID, "pw": PTT_PW})

if not accounts:
    raise ValueError("請設定 PTT_ACCOUNTS，或 PTT_ID 與 PTT_PW 環境變數。")

initial = "default" if "default" in accounts else next(iter(accounts))

mcp: FastMCP = FastMCP(f"Ptt MCP Server v{__version__}")

MEMORY_STORAGE: Dict[str, Any] = {
    "ptt_bot": None,
    "ptt_id": accounts[initial]["id"],
    "ptt_pw": accounts[initial]["pw"],
    "accounts": accounts,
    "current_account": initial,
}


def main():
    api_ptt.register_tools(mcp, MEMORY_STORAGE, __version__)
    api_post.register_tools(mcp, MEMORY_STORAGE, __version__)

    mcp.run()


if __name__ == "__main__":
    main()
