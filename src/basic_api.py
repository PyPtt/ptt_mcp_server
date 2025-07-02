from typing import Dict, Any, Optional, List, Tuple, cast

import PyPtt  # type: ignore
from fastmcp import FastMCP

from utils import _call_ptt_service, _handle_ptt_exception


def register_tools(mcp: FastMCP, memory_storage: Dict[str, Any]):
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
        ptt_service = memory_storage.get("ptt_bot")

        if ptt_service is None:
            return {'success': False, 'message': '尚未登入，無需登出'}

        result = _call_ptt_service(memory_storage, 'logout', success_message='登出成功')
        memory_storage["ptt_bot"] = None
        return result

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
        if memory_storage["ptt_bot"] is not None:
            try:
                memory_storage["ptt_bot"].call('logout')
                memory_storage["ptt_bot"] = None  # 清除 session
            except Exception:
                pass

        ptt_service = PyPtt.Service({})
        try:
            ptt_service.call('login', {'ptt_id': memory_storage['ptt_id'],
                                       'ptt_pw': memory_storage['ptt_pw'],
                                       'kick_other_session': True})
            # 登入成功後，將 bot 實例存起來
            memory_storage["ptt_bot"] = ptt_service

            return {'success': True, 'message': '登入成功'}
        except Exception as e:
            memory_storage["ptt_bot"] = None
            return _handle_ptt_exception(e, {})

    @mcp.tool()
    def get_post(board: str, aid: Optional[str] = None, index: int = 0) -> Dict[str, Any]:
        """
        從 PTT 取得指定文章。

        必須先登入 PTT。

        Args:
            board (str): 文章所在的看板名稱。
            aid (str): 文章的 ID (AID).
            index (int): 文章的索引，從 1 開始。

        Returns:
            Dict[str, Any]: 一個包含文章資料的字典，或是在失敗時回傳錯誤訊息。
                            成功: {'success': True, 'data': {...}}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(memory_storage, 'get_post', board=board, aid=aid, index=index,
                                 empty_data_message='找不到文章或文章可能已被刪除', empty_data_code='POST_NOT_FOUND')

    @mcp.tool()
    def get_newest_index(index_type: str, board: Optional[str] = None,
                         search_list: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
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

        result = _call_ptt_service(memory_storage, 'get_newest_index', **call_args)
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
        return _call_ptt_service(memory_storage, 'post', success_message='發文成功', board=board,
                                 title_index=title_index, title=title, content=content,
                                 sign_file=sign_file)

    @mcp.tool()
    def reply_post(reply_to: str, board: str, content: str, sign_file: str = "0", aid: Optional[str] = None,
                   index: int = 0) -> Dict[str, Any]:
        """
        到看板回覆文章。

        必須先登入 PTT。

        Args:
            reply_to: 回復到看板、信箱或者皆是，BOARD、EMAIL、BOARD_MAIL
            board (str): 需要查詢的看板名稱。
            content (str): 文章內容。
            sign_file (str | int): 編號或隨機簽名檔 (x)，預設為 0 (不選)。
            aid (str): 文章的 ID (AID).
            index (int): 文章的索引，從 1 開始。
        """
        return _call_ptt_service(memory_storage, 'reply_post', success_message='回覆成功', reply_to=reply_to,
                                 board=board, content=content, sign_file=sign_file,
                                 aid=aid, index=index)

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
        return _call_ptt_service(memory_storage, 'del_post', success_message='刪除成功', board=board, aid=aid,
                                 index=index)

    @mcp.tool()
    def comment(board: str, comment_type: str, content: str, aid: Optional[str] = None, index: int = 0) -> Dict[
        str, Any]:
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
        return _call_ptt_service(memory_storage, 'comment', success_message='推文成功', board=board,
                                 comment_type=comment_type_enum, content=content, aid=aid,
                                 index=index)

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
        return _call_ptt_service(memory_storage, 'mail', success_message='寄信成功', ptt_id=ptt_id, title=title,
                                 content=content, sign_file=sign_file, backup=backup)

    @mcp.tool()
    def get_mail(index: int, search_type: Optional[str] = None, search_condition: Optional[str] = None,
                 search_list: Optional[List[Tuple[str, str]]] = None) -> Dict[str, Any]:
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

        return _call_ptt_service(memory_storage, 'get_mail', empty_data_message='找不到信件或信件可能已被刪除',
                                 empty_data_code='MAIL_NOT_FOUND', **call_args)

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
        return _call_ptt_service(memory_storage, 'del_mail', success_message='刪除成功', index=index)

    @mcp.tool()
    def give_money(ptt_id: str, money: int, red_bag_title: Optional[str] = None,
                   red_bag_content: Optional[str] = None) -> \
            Dict[str, Any]:
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

        call_args: Dict[str, Any] = {
            'ptt_id': ptt_id,
            'money': money,
        }

        if red_bag_title:
            call_args['red_bag_title'] = red_bag_title

        if red_bag_content:
            call_args['red_bag_content'] = red_bag_content

        return _call_ptt_service(memory_storage, 'give_money', success_message='轉帳成功', **call_args)

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
        return _call_ptt_service(memory_storage, 'get_user', user_id=user_id,
                                 empty_data_message='找不到使用者: {user_id}', empty_data_code='NO_SUCH_USER')

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
            'ptt_id': ptt_id,
            'min_page': min_page,
            'max_page': max_page
        }

        return _call_ptt_service(memory_storage, 'search_user', empty_data_message='找不到使用者: {ptt_id}',
                                 empty_data_code='NO_SUCH_USER', **call_args)

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
        return _call_ptt_service(memory_storage, 'change_pw', success_message='密碼更改成功', new_password=new_password)

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
        return _call_ptt_service(memory_storage, 'get_time', success_message='取得 PTT 系統時間成功')

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
        return _call_ptt_service(memory_storage, 'get_all_boards', empty_data_message='無法取得看板清單',
                                 empty_data_code='GET_BOARD_LIST_FAILED')

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
        return _call_ptt_service(memory_storage, 'get_favourite_boards', empty_data_message='無法取得我的最愛清單',
                                 empty_data_code='GET_FAVOURITE_BOARDS_FAILED')

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

        return _call_ptt_service(memory_storage, 'get_board_info', empty_data_message='找不到看板: {board}',
                                 empty_data_code='NO_SUCH_BOARD', **call_args)

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
        return _call_ptt_service(memory_storage, 'get_aid_from_url', url=url,
                                 empty_data_message='無法從網址取得看板名稱與文章編號: {url}',
                                 empty_data_code='GET_AID_FROM_URL_FAILED')

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
        return _call_ptt_service(memory_storage, 'get_bottom_post_list', board=board,
                                 empty_data_message='無法取得看板 {board} 的置底文章清單',
                                 empty_data_code='GET_BOTTOM_POST_LIST_FAILED')

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
        return _call_ptt_service(memory_storage, 'set_board_title', success_message='看板標題設定成功', board=board,
                                 new_title=new_title)

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
        return _call_ptt_service(memory_storage, 'bucket', success_message='水桶成功', board=board,
                                 bucket_days=bucket_days, reason=reason, ptt_id=ptt_id)
