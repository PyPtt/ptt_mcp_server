import os
import signal
import sys
from typing import Dict, Any, Optional, List, Tuple, cast

import PyPtt # type: ignore
from dotenv import load_dotenv
from fastmcp import FastMCP

load_dotenv(override=True)

PTT_ID = os.getenv("PTT_ID")
PTT_PW = os.getenv("PTT_PW")

if not PTT_ID or not PTT_PW:
    raise ValueError("PTT_ID and PTT_PW environment variables must be set.")

mcp: FastMCP = FastMCP("Ptt MCP Server")

SESSION_STORAGE: Dict[str, Any] = {
    "ptt_bot": None
}

def _handle_ptt_exception(e: Exception, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(e, PyPtt.RequireLogin):
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}
    elif isinstance(e, PyPtt.UnregisteredUser):
        return {'success': False, 'message': '未註冊使用者', 'code': 'UNREGISTERED_USER'}
    elif isinstance(e, PyPtt.NoSuchBoard):
        return {'success': False, 'message': f'找不到看板: {kwargs.get("board", "")}', 'code': 'NO_SUCH_BOARD'}
    elif isinstance(e, PyPtt.NoSuchPost):
        return {'success': False, 'message': f'在看板 {kwargs.get("board", "")} 中找不到文章 AID: {kwargs.get("aid", "")} 或 Index: {kwargs.get("index", "")}', 'code': 'NO_SUCH_POST'}
    elif isinstance(e, PyPtt.NoPermission):
        return {'success': False, 'message': '沒有權限', 'code': 'NO_PERMISSION'}
    elif isinstance(e, PyPtt.LoginError):
        return {'success': False, 'message': '登入失敗', 'code': 'LOGIN_FAILED'}
    elif isinstance(e, PyPtt.WrongIDorPassword):
        return {'success': False, 'message': '帳號或密碼錯誤', 'code': 'WRONG_CREDENTIALS'}
    elif isinstance(e, PyPtt.CantResponse):
        return {'success': False, 'message': '已結案並標記, 不得回應', 'code': 'CANT_RESPONSE'}
    elif isinstance(e, PyPtt.NoFastComment):
        return {'success': False, 'message': '推文間隔太短', 'code': 'NO_FAST_COMMENT'}
    elif isinstance(e, PyPtt.NoSuchUser):
        return {'success': False, 'message': f'找不到使用者: {kwargs.get("ptt_id", "")}', 'code': 'NO_SUCH_USER'}
    elif isinstance(e, PyPtt.NoSuchMail):
        return {'success': False, 'message': f'找不到信件 Index: {kwargs.get("index", "")}', 'code': 'NO_SUCH_MAIL'}
    elif isinstance(e, PyPtt.MailboxFull):
        return {'success': False, 'message': '信箱已滿', 'code': 'MAILBOX_FULL'}
    elif isinstance(e, PyPtt.NoMoney):
        return {'success': False, 'message': '餘額不足', 'code': 'NO_MONEY'}
    elif isinstance(e, PyPtt.SetContactMailFirst):
        return {'success': False, 'message': '需要先設定聯絡信箱', 'code': 'SET_CONTACT_MAIL_FIRST'}
    elif isinstance(e, PyPtt.WrongPassword):
        return {'success': False, 'message': '密碼錯誤', 'code': 'WRONG_PASSWORD'}
    elif isinstance(e, PyPtt.NeedModeratorPermission):
        return {'success': False, 'message': '需要看板管理員權限', 'code': 'NEED_MODERATOR_PERMISSION'}
    else:
        return {'success': False, 'message': f'操作時發生未知錯誤: {e}', 'args': kwargs, 'code': 'UNKNOWN_ERROR'}

def _call_ptt_service(method_name: str, **kwargs) -> Dict[str, Any]:
    ptt_service = SESSION_STORAGE.get("ptt_bot")
    if ptt_service is None:
        return {'success': False, 'message': '尚未登入，請先執行 login', 'code': 'NOT_LOGGED_IN'}

    try:
        result = ptt_service.call(method_name, kwargs)
        return {'success': True, 'data': result}
    except Exception as e:
        return _handle_ptt_exception(e, kwargs)

def graceful_shutdown(signum, frame):
    print("Received shutdown signal, logging out from PTT...")
    logout() # Call the existing logout function
    sys.exit(0)


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
        return _handle_ptt_exception(e, {})


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
    except Exception as e:
        SESSION_STORAGE["ptt_bot"] = None
        return _handle_ptt_exception(e, {})


@mcp.tool()
def get_post(board: str, aid: Optional[str] = None, index: int = 0) -> Dict[str, Any]:
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
    result = _call_ptt_service('get_post', board=board, aid=aid, index=index)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = '找不到文章或文章可能已被刪除'
        result['code'] = 'POST_NOT_FOUND'
    return result


@mcp.tool()
def get_newest_index(index_type: str, board: Optional[str] = None, search_list: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
    """
    取得最新文章或信箱編號。

    必須先登入 PTT。

    Args:
        index_type (str): 編號類型 (BOARD, MAIL)。
        board (str): 看板名稱 (當 index_type 為 BOARD 時需要)。
        search_list (List[Tuple[str, str]]): 搜尋清單，例如: [("KEYWORD", "PyPtt")], [("AUTHOR", "CodingMan")], [("COMMENT", "100")], [("COMMENT", "M")], [("MONEY", "5")]

    Returns:
        Dict[str, Any]: 一個包含最新編號的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'newest_index': ...}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    call_args: Dict[str, Any] = {
        'index_type': getattr(PyPtt.NewIndex, index_type.upper()),
        'board': board
    }

    if search_list:
        converted_search_list = []
        for search_type_str, search_condition in search_list:
            search_type_enum = getattr(PyPtt.SearchType, search_type_str.upper())
            converted_search_list.append((search_type_enum, search_condition))
        call_args['search_list'] = cast(Any, converted_search_list)

    result = _call_ptt_service('get_newest_index', **call_args)
    if result.get('success'):
        result['newest_index'] = result.pop('data')
    return result


@mcp.tool()
def post(board: str, title_index: int, title: str, content: str, sign_file: str = "0") -> Dict[str, Any]:
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
    result = _call_ptt_service('post', board=board, title_index=title_index, title=title, content=content, sign_file=sign_file)
    if result.get('success'):
        result['message'] = '發文成功'
        del result['data']
    return result


@mcp.tool()
def reply_post(reply_to: str, board: str, content: str, sign_file: str = "0", aid: Optional[str] = None, index: int = 0) -> Dict[str, Any]:
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
    result = _call_ptt_service('reply_post', reply_to=reply_to, board=board, content=content, sign_file=sign_file, aid=aid, index=index)
    if result.get('success'):
        result['message'] = '回覆成功'
        del result['data']
    return result


@mcp.tool()
def del_post(board: str, aid: Optional[str] = None, index: int = 0) -> Dict[str, Any]:
    """
    刪除文章。

    必須先登入 PTT。

    Args:
        board (str): 看板名稱。
        aid (str): 文章編號。
        index (int): 文章編號。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '刪除成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('del_post', board=board, aid=aid, index=index)
    if result.get('success'):
        result['message'] = '刪除成功'
        del result['data']
    return result


@mcp.tool()
def comment(board: str, comment_type: str, content: str, aid: Optional[str] = None, index: int = 0) -> Dict[str, Any]:
    """
    推文。

    必須先登入 PTT。

    Args:
        board (str): 看板名稱。
        comment_type (str): 推文類型 (PUSH, BOO, ARROW)。
        content (str): 推文內容。
        aid (str): 文章編號。
        index (int): 文章編號。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '推文成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    comment_type_enum = getattr(PyPtt.CommentType, comment_type.upper())
    result = _call_ptt_service('comment', board=board, comment_type=comment_type_enum, content=content, aid=aid, index=index)
    if result.get('success'):
        result['message'] = '推文成功'
        del result['data']
    return result


@mcp.tool()
def mail(ptt_id: str, title: str, content: str, sign_file: str = "0", backup: bool = True) -> Dict[str, Any]:
    """
    寄信。

    必須先登入 PTT。

    Args:
        ptt_id (str): PTT ID。
        title (str): 信件標題。
        content (str): 信件內容。
        sign_file (str | int): 編號或隨機簽名檔 (x)，預設為 0 (不選)。
        backup (bool): 如果是 True 寄信時將會備份信件，預設為 True。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '寄信成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('mail', ptt_id=ptt_id, title=title, content=content, sign_file=sign_file, backup=backup)
    if result.get('success'):
        result['message'] = '寄信成功'
        del result['data']
    return result


@mcp.tool()
def get_mail(index: int, search_type: Optional[str] = None, search_condition: Optional[str] = None, search_list: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
    """
    取得信件。

    必須先登入 PTT。

    Args:
        index (int): 信件編號。
        search_type (str): 搜尋類型 (KEYWORD, AUTHOR)。
        search_condition (str): 搜尋條件。
        search_list (List[Tuple[str, str]]): 搜尋清單，例如 [("KEYWORD", "PyPtt")], [("AUTHOR", "CodingMan")]。

    Returns:
        Dict[str, Any]: 一個包含信件資料的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': {...}}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    call_args: Dict[str, Any] = {
        'index': index
    }

    if search_type and search_condition:
        search_type_enum = getattr(PyPtt.SearchType, search_type.upper())
        call_args['search_type'] = cast(Any, search_type_enum)
        call_args['search_condition'] = cast(Any, search_condition)
    elif search_list:
        converted_search_list = []
        for st_str, sc in search_list:
            st_enum = getattr(PyPtt.SearchType, st_str.upper())
            converted_search_list.append((st_enum, sc))
        call_args['search_list'] = cast(Any, converted_search_list)

    result = _call_ptt_service('get_mail', **call_args)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = '找不到信件或信件可能已被刪除'
        result['code'] = 'MAIL_NOT_FOUND'
    return result


@mcp.tool()
def del_mail(index: int) -> Dict[str, Any]:
    """
    刪除信件。

    必須先登入 PTT。

    Args:
        index (int): 信件編號。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '刪除成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('del_mail', index=index)
    if result.get('success'):
        result['message'] = '刪除成功'
        del result['data']
    return result


@mcp.tool()
def give_money(ptt_id: str, money: int, red_bag_title: Optional[str] = None, red_bag_content: Optional[str] = None) -> Dict[str, Any]:
    """
    轉帳，詳見 P 幣。

    必須先登入 PTT。

    Args:
        ptt_id (str): PTT ID。
        money (int): 轉帳金額。
        red_bag_title (str): 紅包標題。
        red_bag_content (str): 紅包內容。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '轉帳成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    call_args = {
        'ptt_id': ptt_id,
        'money': money
    }
    if red_bag_title:
        call_args['red_bag_title'] = red_bag_title
    if red_bag_content:
        call_args['red_bag_content'] = red_bag_content

    result = _call_ptt_service('give_money', **call_args)
    if result.get('success'):
        result['message'] = '轉帳成功'
        del result['data']
    return result


@mcp.tool()
def get_user(user_id: str) -> Dict[str, Any]:
    """
    取得使用者資訊。

    必須先登入 PTT。

    Args:
        user_id (str): 使用者 ID。

    Returns:
        Dict[str, Any]: 一個包含使用者資料的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': {...}}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('get_user', user_id=user_id)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = f'找不到使用者: {user_id}'
        result['code'] = 'NO_SUCH_USER'
    return result


@mcp.tool()
def search_user(ptt_id: str, min_page: Optional[int] = None, max_page: Optional[int] = None) -> Dict[str, Any]:
    """
    搜尋使用者。

    必須先登入 PTT。

    Args:
        ptt_id (str): PTT ID。
        min_page (int): 最小頁數。
        max_page (int): 最大頁數。

    Returns:
        Dict[str, Any]: 一個包含搜尋結果的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': [...]}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    call_args: Dict[str, Any] = {
        'ptt_id': ptt_id
    }
    if min_page is not None:
        call_args['min_page'] = min_page
    if max_page is not None:
        call_args['max_page'] = max_page

    result = _call_ptt_service('search_user', **call_args)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = f'找不到使用者: {ptt_id}'
        result['code'] = 'NO_SUCH_USER'
    return result


@mcp.tool()
def change_pw(new_password: str) -> Dict[str, Any]:
    """
    更改密碼。

    必須先登入 PTT。

    Args:
        new_password (str): 新密碼。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '密碼更改成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('change_pw', new_password=new_password)
    if result.get('success'):
        result['message'] = '密碼更改成功'
        del result['data']
    return result


@mcp.tool()
def get_time() -> Dict[str, Any]:
    """
    取得 PTT 系統時間。

    必須先登入 PTT。

    Returns:
        Dict[str, Any]: 一個包含 PTT 系統時間的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': '...'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('get_time')
    if result.get('success'):
        result['message'] = '取得 PTT 系統時間成功'
    return result


@mcp.tool()
def get_all_boards() -> Dict[str, Any]:
    """
    取得全站看板清單。

    必須先登入 PTT。

    Returns:
        Dict[str, Any]: 一個包含看板清單的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': [...]}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('get_all_boards')
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = '無法取得看板清單'
        result['code'] = 'GET_BOARD_LIST_FAILED'
    return result


@mcp.tool()
def get_favourite_boards() -> Dict[str, Any]:
    """
    取得我的最愛清單。

    必須先登入 PTT。

    Returns:
        Dict[str, Any]: 一個包含收藏看板清單的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': [...]}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('get_favourite_boards')
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = '無法取得我的最愛清單'
        result['code'] = 'GET_FAVOURITE_BOARDS_FAILED'
    return result


@mcp.tool()
def get_board_info(board: str, get_post_types: bool = False) -> Dict[str, Any]:
    """
    取得看板資訊。

    必須先登入 PTT。

    Args:
        board (str): 看板名稱。
        get_post_types (bool): 是否取得文章類型，例如：八卦板的「問卦」。

    Returns:
        Dict[str, Any]: 一個包含看板資訊的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': {...}}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    call_args: Dict[str, Any] = {
        'board': board,
        'get_post_types': get_post_types
    }
    result = _call_ptt_service('get_board_info', **call_args)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = f'找不到看板: {board}'
        result['code'] = 'NO_SUCH_BOARD'
    return result


@mcp.tool()
def get_aid_from_url(url: str) -> Dict[str, Any]:
    """
    從網址取得看板名稱與文章編號。

    Args:
        url (str): 網址。

    Returns:
        Dict[str, Any]: 一個包含看板名稱與文章編號的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': [board, aid]}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('get_aid_from_url', url=url)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = f'無法從網址取得看板名稱與文章編號: {url}'
        result['code'] = 'GET_AID_FROM_URL_FAILED'
    return result


@mcp.tool()
def get_bottom_post_list(board: str) -> Dict[str, Any]:
    """
    取得看板置底文章清單。

    必須先登入 PTT。

    Args:
        board (str): 看板名稱。

    Returns:
        Dict[str, Any]: 一個包含置底文章清單的字典，或是在失敗時回傳錯誤訊息。
                        成功: {'success': True, 'data': [...]}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('get_bottom_post_list', board=board)
    if result.get('success') and not result.get('data'):
        result['success'] = False
        result['message'] = f'無法取得看板 {board} 的置底文章清單'
        result['code'] = 'GET_BOTTOM_POST_LIST_FAILED'
    return result


@mcp.tool()
def set_board_title(board: str, new_title: str) -> Dict[str, Any]:
    """
    設定看板標題。

    必須先登入 PTT。

    Args:
        board (str): 看板名稱。
        new_title (str): 新標題。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '看板標題設定成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('set_board_title', board=board, new_title=new_title)
    if result.get('success'):
        result['message'] = '看板標題設定成功'
        del result['data']
    return result


@mcp.tool()
def bucket(board: str, bucket_days: int, reason: str, ptt_id: str) -> Dict[str, Any]:
    """
    水桶。

    必須先登入 PTT。

    Args:
        board (str): 看板名稱。
        bucket_days (int): 水桶天數。
        reason (str): 水桶原因。
        ptt_id (str): PTT ID。

    Returns:
        Dict[str, Any]: 一個包含操作結果的字典。
                        成功: {'success': True, 'message': '水桶成功'}
                        失敗: {'success': False, 'message': '...', 'code': '...'}
    """
    result = _call_ptt_service('bucket', board=board, bucket_days=bucket_days, reason=reason, ptt_id=ptt_id)
    if result.get('success'):
        result['message'] = '水桶成功'
        del result['data']
    return result


if __name__ == '__main__':
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)
    mcp.run()
