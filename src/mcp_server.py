import os
from typing import Dict, Any

import PyPtt
from PyPtt import ReplyTo
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv(override=True)

PTT_ID = os.getenv("PTT_ID")
PTT_PW = os.getenv("PTT_PW")

if not PTT_ID or not PTT_PW:
    raise ValueError("PTT_ID and PTT_PW environment variables must be set.")

mcp = FastMCP("Ptt MCP Server")

SESSION_STORAGE: Dict[str, Any] = {
    "ptt_bot": None
}


@mcp.tool()
def logout() -> Dict[str, Any]:
    """
    Logs out from the PTT service.

    This function terminates the current PTT session if one is active.

    Returns:
        Dict[str, Any]: A dictionary indicating the result of the logout attempt.
                        On success: {'success': True, 'message': '登出成功'}
                        On failure: {'success': False, 'message': '登出失敗或尚未登入'}
    """
    ptt_service = SESSION_STORAGE.get("ptt_bot")

    if ptt_service is None:
        return {'success': False, 'message': '尚未登入，無需登出'}

    try:
        ptt_service.call('logout')
        SESSION_STORAGE["ptt_bot"] = None  # 清除 session
        return {'success': True, 'message': '登出成功'}
    except Exception as e:
        print(f"An error occurred during logout: {e}")
        # 即使登出失敗，也清除本地 session，讓使用者可以重新登入
        SESSION_STORAGE["ptt_bot"] = None
        return {'success': False, 'message': f'登出時發生錯誤: {e}'}


@mcp.tool()
def login() -> Dict[str, Any]:
    """
    Logs into the PTT service using credentials from environment variables.

    This function initializes a connection to PTT and attempts to log in.
    The login status is maintained on the server for subsequent calls.

    Returns:
        Dict[str, Any]: A dictionary containing the result of the login attempt.
                        On success: {'success': True, 'message': '登入成功'}
                        On failure: {'success': False, 'message': '...', 'code': '...'}
    """
    # 如果已經有一個 bot 實例，先登出舊的
    if SESSION_STORAGE["ptt_bot"] is not None:
        try:
            SESSION_STORAGE["ptt_bot"].call('logout')
            SESSION_STORAGE["ptt_bot"] = None  # 清除 session
        except Exception:
            pass

    ptt_service = PyPtt.Service({})
    try:
        ptt_service.call('login', {'ptt_id': PTT_ID, 'ptt_pw': PTT_PW, 'kick_other_session': True})
        # 登入成功後，將 bot 實例存起來
        SESSION_STORAGE["ptt_bot"] = ptt_service

        return {'success': True, 'message': '登入成功'}
    except PyPtt.LoginError:
        SESSION_STORAGE["ptt_bot"] = None
        return {'success': False, 'message': '登入失敗', 'code': 'LOGIN_FAILED'}
    except PyPtt.WrongIDorPassword:
        SESSION_STORAGE["ptt_bot"] = None
        return {'success': False, 'message': '帳號或密碼錯誤', 'code': 'WRONG_CREDENTIALS'}
    except Exception as e:
        SESSION_STORAGE["ptt_bot"] = None
        return {'success': False, 'message': '登入時發生未知錯誤', 'code': f'UNKNOWN_ERROR: {e}'}


@mcp.tool()
def get_post(board: str, aid: str = None, index: int = 0) -> Dict[str, Any]:
    """
    從 PTT 取得指定文章。

    必須先登入 PTT。

    Args:
        board (str): 文章所在的看板名稱。
        aid (str): 文章的 ID (AID)。
        index (int): 文章的索引，從 1 開始。

    Returns:
        Dict[str, Any]: 一個包含文章資料的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': {...}}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    ptt_service = SESSION_STORAGE.get("ptt_bot")
    if ptt_service is None:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}

    try:
        post_data = ptt_service.call('get_post', {
            'board': board,
            'aid': aid,
            'index': index
        })

        if not post_data:
            return {'success': False, 'message': '找不到文章或文章可能已被刪除', 'code': 'POST_NOT_FOUND'}

        return {'success': True, 'data': post_data}
    except PyPtt.RequireLogin:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}
    except PyPtt.NoSuchBoard:
        return {'success': False, 'message': f'找不到看板: {board}', 'code': 'NO_SUCH_BOARD'}
    except PyPtt.NoSuchPost:
        return {'success': False, 'message': f'在看板 {board} 中找不到文章 AID: {aid}', 'code': 'NO_SUCH_POST'}
    except Exception as e:
        return {'success': False, 'message': f'取得文章時發生未知錯誤: {e}', 'code': 'UNKNOWN_ERROR'}


@mcp.tool()
def get_board_newest_index(board) -> Dict[str, Any]:
    """
    取得 PTT 看板的最新文章 index。

    必須先登入 PTT。

    Args:
        board (str): 需要查詢的看板名稱。
    """

    ptt_service = SESSION_STORAGE.get("ptt_bot")
    if ptt_service is None:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}

    try:
        newest_index = ptt_service.call('get_newest_index', {
            'index_type': PyPtt.NewIndex.BOARD,
            'board': board
        })

        return {'success': True, 'newest_index': newest_index}
    except PyPtt.RequireLogin:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}
    except PyPtt.NoSuchBoard:
        return {'success': False, 'message': f'找不到看板: {board}', 'code': 'NO_SUCH_BOARD'}
    except Exception as e:
        return {'success': False, 'message': f'取得文章時發生未知錯誤: {e}', 'code': 'UNKNOWN_ERROR'}


@mcp.tool()
def post(board, title_index: int, title: str, content: str, sign_file: str = 0) -> Dict[str, Any]:
    """
    到看板發佈文章。

    必須先登入 PTT。

    Args:
        board (str): 需要查詢的看板名稱。
        title_index (int): 文章標題編號。
        title (str): 文章標題。
        content (str): 文章內容。
        sign_file (str | int): 編號或隨機簽名檔 (x)，預設為 0 (不選)。
    """

    ptt_service = SESSION_STORAGE.get("ptt_bot")
    if ptt_service is None:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}

    try:
        ptt_service.call('post', {
            'board': board,
            'title_index': title_index,
            'title': title,
            'content': content,
            'sign_file': sign_file
        })

        return {'success': True, 'message': '發文成功'}

    except PyPtt.NoPermission:
        return {'success': False, 'message': '沒有權限發文', 'code': 'NO_PERMISSION'}
    except PyPtt.RequireLogin:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}
    except PyPtt.UnregisteredUser:
        return {'success': False, 'message': '未註冊使用者', 'code': 'VERIFY_FIRST'}
    except PyPtt.NoSuchBoard:
        return {'success': False, 'message': f'找不到看板: {board}', 'code': 'NO_SUCH_BOARD'}
    except Exception as e:
        return {'success': False, 'message': f'取得文章時發生未知錯誤: {e}', 'code': 'UNKNOWN_ERROR'}


@mcp.tool()
def reply_post(reply_to: str, board, content: str, sign_file: str = 0, aid: str = None, index: int = 0) -> Dict[str, Any]:
    """
    到看板回覆文章。

    必須先登入 PTT。

    Args:
        reply_to: 回復到看板、信箱或者皆是，BOARD、EMAIL、BOARD_MAIL
        board (str): 需要查詢的看板名稱。
        content (str): 文章內容。
        sign_file (str | int): 編號或隨機簽名檔 (x)，預設為 0 (不選)。
        aid (str): 文章的 ID (AID)。
        index (int): 文章的索引，從 1 開始。
    """

    ptt_service = SESSION_STORAGE.get("ptt_bot")
    if ptt_service is None:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}

    try:
        ptt_service.call('reply_post', {
            'reply_to': reply_to,
            'board': board,
            'content': content,
            'sign_file': sign_file,
            'aid': aid,
            'index': index
        })

        return {'success': True, 'message': '回覆成功'}

    except PyPtt.NoPermission:
        return {'success': False, 'message': '沒有權限發文', 'code': 'NO_PERMISSION'}
    except PyPtt.RequireLogin:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}
    except PyPtt.UnregisteredUser:
        return {'success': False, 'message': '未註冊使用者', 'code': 'VERIFY_FIRST'}
    except PyPtt.CantResponse:
        return {'success': False, 'message': '已結案並標記, 不得回應', 'code': 'CANT_RESPONSE'}
    except PyPtt.NoSuchBoard:
        return {'success': False, 'message': f'找不到看板: {board}', 'code': 'NO_SUCH_BOARD'}
    except Exception as e:
        return {'success': False, 'message': f'取得文章時發生未知錯誤: {e}', 'code': 'UNKNOWN_ERROR'}




if __name__ == '__main__':
    mcp.run()
