import threading
from typing import Dict, Any, Optional, List, Tuple

import PyPtt
from fastmcp import FastMCP

from utils import _call_ptt_service, _handle_ptt_exception

# ponytail: module-level 鎖序列化池變動，防 FastMCP 併發呼叫造成 double-login/race。
_pool_lock = threading.Lock()


def _bad_post_type_from_name(name: Optional[str]) -> Optional["PyPtt.BadPostType"]:
    """劣退／惡退分類的字串名 → PyPtt.BadPostType。

    BadPostType 是 IntEnum（不像 SearchType 是 str 子類），MCP 收到的字串不能
    直接傳給 PyPtt，得先用成員名查回 enum。未知名稱丟 ValueError 由呼叫端轉錯誤。
    """
    if name is None:
        return None
    try:
        return PyPtt.BadPostType[name]
    except KeyError:
        raise ValueError(name)


def _login_new_service(
    ptt_id: str, ptt_pw: str
) -> Tuple[Optional[Any], Dict[str, Any]]:
    """建一個新 Service 並登入。成功回 (svc, 成功dict)；失敗先 close() 掉失敗的 svc
    再回 (None, 錯誤dict)。此 helper 不碰 active session 或池。"""
    ptt_service = PyPtt.Service({})
    try:
        ptt_service.call(
            "login",
            {
                "ptt_id": ptt_id,
                "ptt_pw": ptt_pw,
                "kick_other_session": True,
            },
        )
        return ptt_service, {"success": True, "message": "登入成功"}
    except Exception as e:
        # 洩漏防護：登入失敗的 Service 內有 daemon thread + 連線，離開前必須 close。
        try:
            ptt_service.close()
        except Exception:
            pass
        return None, _handle_ptt_exception(e, {})


def _is_alive(svc: Any) -> bool:
    """驗活：對池裡的 Service 做一個便宜的 authenticated 呼叫探測，丟例外即視為 dead。"""
    # ponytail: PTT 會斷閒置連線，光看 _is_login flag 偵測不到 server 端斷線，故主動用 get_time 探測。
    try:
        svc.call("get_time")
        return True
    except Exception:
        return False


def _activate(memory_storage: Dict[str, Any], name: str) -> Dict[str, Any]:
    """把帳號 name 設為 active（登入並放進池）。原子性：新登入失敗不動 active session。"""
    accounts = memory_storage["accounts"]
    with _pool_lock:
        pool = memory_storage["pool"]
        svc = pool.get(name)

        # 池裡有但已死 → close 汰換（離開池的 Service 都要 close 防洩漏）。
        if svc is not None and not _is_alive(svc):
            try:
                svc.close()
            except Exception:
                pass
            pool.pop(name, None)
            svc = None

        if svc is None:
            svc, result = _login_new_service(accounts[name]["id"], accounts[name]["pw"])
            if svc is None:
                # 原子性關鍵：登入失敗，不動 ptt_bot / current_account / ptt_id / ptt_pw。
                return result
            pool[name] = svc

        memory_storage["ptt_bot"] = svc
        memory_storage["current_account"] = name
        # 同步憑證，讓 bare login() 等仍與 active 帳號一致。
        memory_storage["ptt_id"] = accounts[name]["id"]
        memory_storage["ptt_pw"] = accounts[name]["pw"]
        return {"success": True, "message": "登入成功"}


def register_tools(mcp: FastMCP, memory_storage: Dict[str, Any], version: str):
    @mcp.tool()
    def get_version() -> Dict[str, Any]:
        """
        Returns the current version of the PTT MCP Server.

        Returns:
            Dict[str, Any]: A dictionary containing the version information.
                            Example: {'success': True, 'version': '0.1.0'}
        """
        return {"success": True, "version": version}

    @mcp.tool()
    def logout() -> Dict[str, Any]:
        """Logs out from the PTT service.

        This function terminates the current PTT session if one is active.

        Returns:
            Dict[str, Any]: A dictionary indicating the result of the logout attempt.
                            On success: {'success': True, 'message': '登出成功'}
                            On failure: {'success': False, 'message': '登出失敗或尚未登入'}
        """
        ptt_service = memory_storage.get("ptt_bot")

        if ptt_service is None:
            return {"success": False, "message": "尚未登入，無需登出"}

        # 只登出 active 帳號：logout 後 close、從池移除、ptt_bot=None；其他池內帳號不動。
        with _pool_lock:
            result = _call_ptt_service(
                memory_storage, "logout", success_message="登出成功"
            )
            try:
                ptt_service.close()
            except Exception:
                pass
            pool = memory_storage["pool"]
            for pool_name, pool_svc in list(pool.items()):
                if pool_svc is ptt_service:
                    del pool[pool_name]
            memory_storage["ptt_bot"] = None
        return result

    @mcp.tool()
    def login() -> Dict[str, Any]:
        """Logs into the PTT service using credentials from environment variables.

        This function initializes a connection to PTT and attempts to log in.
        The login status is maintained on the server for subsequent calls.

        Returns:
            Dict[str, Any]: A dictionary containing the result of the login attempt.
                            On success: {'success': True, 'message': '登入成功'}
                            On failure: {'success': False, 'message': '...', 'code': '...'}
                            Possible error codes for 'code' field:
                            - 'NOT_LOGGED_IN': 尚未登入，請先執行 login。
                            - 'UNREGISTERED_USER': 未註冊使用者。
                            - 'NO_SUCH_BOARD': 找不到看板。
                            - 'NO_SUCH_POST': 在看板中找不到文章 AID 或 Index。
                            - 'NO_PERMISSION': 沒有權限。
                            - 'LOGIN_FAILED': 登入失敗。
                            - 'TWO_FACTOR_AUTH_REQUIRED': 需要二階段驗證，請先用一般 BBS 客戶端從這台機器手動登入完成驗證。
                            - 'WRONG_CREDENTIALS': 帳號或密碼錯誤。
                            - 'CANT_RESPONSE': 已結案並標記, 不得回應。
                            - 'NO_FAST_COMMENT': 推文間隔太短。
                            - 'NO_SUCH_USER': 找不到使用者。
                            - 'NO_SUCH_MAIL': 找不到信件 Index。
                            - 'MAILBOX_FULL': 信箱已滿。
                            - 'NO_MONEY': 餘額不足。
                            - 'SET_CONTACT_MAIL_FIRST': 需要先設定聯絡信箱。
                            - 'WRONG_PASSWORD': 密碼錯誤。
                            - 'NEED_MODERATOR_PERMISSION': 需要看板管理員權限。
                            - 'UNKNOWN_ERROR': 操作時發生未知錯誤。
        """
        return _activate(memory_storage, memory_storage["current_account"])

    @mcp.tool()
    def list_accounts() -> Dict[str, Any]:
        """列出已在環境變數設定的 PTT 帳號名稱（不含密碼），以及目前登入中的帳號名稱。

        Returns:
            Dict[str, Any]: {'success': True,
                             'accounts': ['default', 'alt', ...],
                             'current': 'default' 或 None}
        """
        # ponytail: 用 whoami 那套真實狀態判定（讀 PyPtt 私有 _is_login），沒 active 登入才不謊報。
        api = getattr(memory_storage.get("ptt_bot"), "_api", None)
        current = (
            memory_storage.get("current_account")
            if getattr(api, "_is_login", False)
            else None
        )
        return {
            "success": True,
            "accounts": list(memory_storage.get("accounts", {}).keys()),
            "current": current,
        }

    @mcp.tool()
    def switch_account(name: str) -> Dict[str, Any]:
        """切換到指定名稱的 PTT 帳號並登入。

        帳號需事先透過環境變數 PTT_ACCOUNTS 設定（見 README）。切換後會記住此帳號，
        後續 login() 也會使用它。可先用 list_accounts() 查詢可用名稱。

        Args:
            name (str): 帳號名稱。

        Returns:
            Dict[str, Any]: 成功 {'success': True,
                                  'message': "已切換到帳號 'xxx' 並登入成功",
                                  'current': 'xxx'}
                            找不到名稱 {'success': False,
                                        'message': "找不到帳號 'xxx'",
                                        'available': [...]}
                            登入失敗則回傳 login 相同的錯誤格式。
        """
        accounts = memory_storage.get("accounts", {})
        if name not in accounts:
            return {
                "success": False,
                "message": f"找不到帳號 '{name}'",
                "available": list(accounts.keys()),
            }
        result = _activate(memory_storage, name)
        if result.get("success"):
            result["message"] = f"已切換到帳號 '{name}' 並登入成功"
            result["current"] = name
        return result

    @mcp.tool()
    def whoami() -> Dict[str, Any]:
        """回傳目前登入中的 PTT 帳號資訊，實際登入狀態直接向 PyPtt 查詢。

        Returns:
            Dict[str, Any]: {'success': True,
                             'account': 'default',   # 帳號名稱（來自 PTT_ACCOUNTS 標籤）
                             'ptt_id': 'CodingMan',  # PyPtt 目前登入的實際 PTT ID；未登入為 None
                             'logged_in': True}      # PyPtt 回報是否已登入
        """
        # ponytail: 讀 PyPtt 私有屬性取真實狀態；PyPtt 無公開存取方法，改版壞了再換
        api = getattr(memory_storage.get("ptt_bot"), "_api", None)
        logged_in = bool(getattr(api, "_is_login", False))
        # PyPtt 登出不清 ptt_id，未登入時不回報殘留值
        ptt_id = (getattr(api, "ptt_id", "") or None) if logged_in else None
        return {
            "success": True,
            "account": memory_storage.get("current_account"),
            "ptt_id": ptt_id,
            "logged_in": logged_in,
        }

    @mcp.tool()
    def get_post(
        board: str,
        aid: Optional[str] = None,
        index: Optional[int] = None,
        query: bool = False,
        search_list: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """從 PTT 取得指定文章。

        註記：此函式必須先登入 PTT。

        Args:
            board (str): 文章所在的看板名稱。
            aid (str, optional): 文章的 ID (AID)。與 `index` 擇一使用。
            index (int, optional): 文章的索引，從 1 開始。與 `aid` 擇一使用。
            search_list (List[Tuple[str, str]], optional): 搜尋條件清單。每個元組包含搜尋類型和搜尋條件。
                                                            搜尋類型可為 "KEYWORD" (關鍵字)、"AUTHOR" (作者)、
                                                            "COMMENT" (推文數，例如 "100" 或 "M" 代表爆文)、
                                                            "MONEY" (P幣，例如 "5")。
                                                            範例: [("KEYWORD", "PyPtt")], [("AUTHOR", "CodingMan")],
                                                            [("COMMENT", "100")], [("COMMENT", "M")], [("MONEY", "5")]。
            query (bool): 是否為查詢模式。如果是需要文章代碼(AID)、文章網址、文章值多少 Ptt 幣、文章編號(index)，就可以使用查詢模式，速度會快很多。
                          此模式不會包含文章內容。

        Returns:
            Dict[str, Any]: 一個包含文章資料的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含文章詳細資訊，例如：
                            {'success': True, 'data': {
                                'board': '看板名稱',
                                'aid': '文章ID',
                                'index': 文章索引,
                                'author': '作者',
                                'title': '文章標題',
                                'content': '文章內容',
                                'date': '發文日期',
                                'comments': [...] # 推文列表
                            }}
                            失敗時: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "get_post",
            board=board,
            aid=aid,
            index=index,
            query=query,
            search_list=search_list,
        )

    @mcp.tool()
    def get_newest_index(
        index_type: str,
        board: Optional[str] = None,
        search_list: Optional[List[Tuple[str, str]]] = None,
    ) -> Dict[str, Any]:
        """取得最新文章或信箱編號。
        函式回傳的 newest_index 代表的是該類型 (看板文章或信箱信件) 的最大有效編號。
        例如，如果您呼叫 get_newest_index(index_type="BOARD", board="Test") 並得到

        {'success': True, 'newest_index': 100}

        ，這表示在 'Test' 看板中，文章索引從 1 到 100 都是可用的。
        這個函式本身不會回傳一個包含所有可用索引的列表，而是提供一個上限值，讓您可以根據這個上限值來進行後續的操作，例如遍歷文章或信件。

        註記：此函式必須先登入 PTT。

        Args:
            index_type (str): 編號類型，可為 "BOARD" (看板文章) 或 "MAIL" (信箱信件)。
            board (str, optional): 看板名稱。當 `index_type` 為 "BOARD" 時需要提供。
            search_list (List[Tuple[str, str]], optional): 搜尋條件清單。每個元組包含搜尋類型和搜尋條件，不同搜尋條件取得的編號(index) 會不同。
                                                            搜尋類型可為 "KEYWORD" (關鍵字)、"AUTHOR" (作者)、
                                                            "COMMENT" (推文數，例如 "100" 或 "M" 代表爆文)、
                                                            "MONEY" (P幣，例如 "5")。
                                                            範例: [("KEYWORD", "PyPtt")], [("AUTHOR", "CodingMan")],
                                                            [("COMMENT", "100")], [("COMMENT", "M")], [("MONEY", "5")]。

                                                            如果有多個關鍵字，應該使用多次搜尋條件，例如想同時搜尋「蔡英文 新聞」，
                                                            應該使用 [("KEYWORD", "蔡英文"), ("KEYWORD", "新聞")]。

        Returns:
            Dict[str, Any]: 一個包含最新編號的字典，或是在失敗時回傳錯誤訊息。
                            成功: {'success': True, 'newest_index': 最新編號}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "get_newest_index",
            index_type=index_type,
            board=board,
            search_list=search_list,
        )

    @mcp.tool()
    def post(
        board: str, title_index: int, title: str, content: str, sign_file: str = "0"
    ) -> Dict[str, Any]:
        """到看板發佈文章。

        執行前務必顯示內容並與使用者確認後才可以執行。(Must display content and confirm with the user before execution.)

        註記：此函式必須先登入 PTT。

        Args:
            board (str): 需要發文的看板名稱。
            title_index (int): 文章標題分類編號。例如，在某些看板中，1 可能代表「問題」，2 代表「討論」等。
                               此編號可透過 `get_board_info` 函式取得的 `post_kind_list` 來對應，編號從 1 開始。
            title (str): 文章標題。
            content (str): 文章內容。
            sign_file (str | int, optional): 簽名檔編號或隨機簽名檔 (x)。預設為 "0" (不選用簽名檔)。
                                            可用的值為 "0" 到 "9" 的數字字串，或 "x"。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '發文成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "post",
            board=board,
            title_index=title_index,
            title=title,
            content=content,
            sign_file=sign_file,
            success_message="發文成功",
        )

    @mcp.tool()
    def reply_post(
        board: str,
        reply_to: str,
        content: str,
        aid: Optional[str] = None,
        index: int = 0,
        sign_file: str = "0",
    ) -> Dict[str, Any]:
        """到看板回覆文章。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        Args:
            reply_to (str): 回覆目標，可為 "BOARD" (回覆到看板)、"EMAIL" (回覆到信箱) 或 "BOARD_MAIL" (同時回覆到看板和信箱)。
            board (str): 文章所在的看板名稱。
            content (str): 回覆內容。
            sign_file (str | int, optional): 簽名檔編號或隨機簽名檔 (x)。預設為 "0" (不選用簽名檔)。
                                            可用的值為 "0" 到 "9" 的數字字串，或 "x"。
            aid (str, optional): 文章的 ID (AID)。與 `index` 擇一使用。
            index (int, optional): 文章的索引，從 1 開始。與 `aid` 擇一使用。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '回覆成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "reply_post",
            board=board,
            reply_to=reply_to,
            content=content,
            aid=aid,
            index=index,
            sign_file=sign_file,
            success_message="回覆成功",
        )

    @mcp.tool()
    def del_post(
        board: str,
        aid: Optional[str] = None,
        index: int = 0,
        bad_post_type: Optional[str] = None,
        bad_post_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """刪除文章。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        劣退／惡退（劣文退文，PTT 選單上顯示為「惡退」，兩種說法都是同一件事）：
        板主刪除「他人」文章時，可對作者記一支退文（badpost）。
        只有板主刪他人文章時才適用；刪自己的文章請勿傳 bad_post_type。

        Args:
            board (str): 文章所在的看板名稱。
            aid (str, optional): 文章的 ID (AID)。與 `index` 擇一使用。
            index (int, optional): 文章的索引，從 1 開始。與 `aid` 擇一使用。
            bad_post_type (str, optional): 劣退／惡退分類，四選一：
                                           "AD"（廣告）、"BAD_LANGUAGE"（不當用辭）、
                                           "PERSONAL_ATTACK"（人身攻擊）、"OTHER"（其他）。
                                           不傳＝不記劣退／惡退，只單純刪文。
            bad_post_reason (str, optional): 劣退／惡退理由。僅當 bad_post_type 為 "OTHER" 時
                                             必須傳入，且不可超過 50 bytes（Big5 編碼）；
                                             其餘分類請勿傳入。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '刪除成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
                            bad_post_type 無效: {'success': False, 'message': '...',
                                                 'code': 'BAD_PARAM'}
        """
        try:
            bpt = _bad_post_type_from_name(bad_post_type)
        except ValueError:
            return {
                "success": False,
                "message": (
                    f"未知的 bad_post_type: {bad_post_type!r}，"
                    "可用: AD, BAD_LANGUAGE, PERSONAL_ATTACK, OTHER"
                ),
                "code": "BAD_PARAM",
            }
        return _call_ptt_service(
            memory_storage,
            "del_post",
            board=board,
            aid=aid,
            index=index,
            bad_post_type=bpt,
            bad_post_reason=bad_post_reason,
            success_message="刪除成功",
        )

    @mcp.tool()
    def comment(
        board: str,
        comment_type: str,
        content: str,
        aid: Optional[str] = None,
        index: int = 0,
    ) -> Dict[str, Any]:
        """對文章進行推文、噓文或箭頭。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        Args:
            board (str): 文章所在的看板名稱。
            comment_type (str): 推文類型，可為 "PUSH" (推)、"BOO" (噓) 或 "ARROW" (箭頭)。
            content (str): 推文內容。
            aid (str, optional): 文章的 ID (AID)。與 `index` 擇一使用。
            index (int, optional): 文章的索引，從 1 開始。與 `aid` 擇一使用。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '推文成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "comment",
            board=board,
            comment_type=comment_type,
            content=content,
            aid=aid,
            index=index,
            success_message="推文成功",
        )

    @mcp.tool()
    def mail(
        ptt_id: str, title: str, content: str, sign_file: str = "0", backup: bool = True
    ) -> Dict[str, Any]:
        """寄送站內信。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        Args:
            ptt_id (str): 收件人的 PTT ID。
            title (str): 信件標題。
            content (str): 信件內容。
            sign_file (str | int, optional): 簽名檔編號或隨機簽名檔 (x)。預設為 "0" (不選用簽名檔)。
                                            可用的值為 "0" 到 "9" 的數字字串，或 "x"。
            backup (bool, optional): 是否備份信件。預設為 True。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '寄信成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "mail",
            ptt_id=ptt_id,
            title=title,
            content=content,
            sign_file=sign_file,
            backup=backup,
            success_message="寄信成功",
        )

    @mcp.tool()
    def get_mail(
        index: int,
        search_type: Optional[str] = None,
        search_condition: Optional[str] = None,
        search_list: Optional[List[List[str]]] = None,
    ) -> Dict[str, Any]:
        """取得信件。

        註記：此函式必須先登入 PTT。

        Args:
            index (int): 信件編號。
            search_type (str, optional): 搜尋類型，可為 "KEYWORD" (關鍵字) 或 "AUTHOR" (作者)。
                                         如果提供了 `search_list`，則此參數會被忽略。
            search_condition (str, optional): 搜尋條件。如果提供了 `search_list`，則此參數會被忽略。
            search_list (List[Tuple[str, str]], optional): 搜尋清單。每個元組包含搜尋類型和搜尋條件。
                                                            搜尋類型可為 "KEYWORD" (關鍵字) 或 "AUTHOR" (作者)。
                                                            範例: [("KEYWORD", "PyPtt")], [("AUTHOR", "CodingMan")]。

        Returns:
            Dict[str, Any]: 一個包含信件資料的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含信件詳細資訊，例如：
                            {'success': True, 'data': {
                                'origin_mail': '原始信件內容',
                                'author': '寄件人',
                                'title': '信件標題',
                                'date': '寄件日期',
                                'content': '信件內文',
                                'ip': '寄件IP',
                                'location': '寄件地點',
                                'is_red_envelope': 是否為紅包信
                            }}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "get_mail",
            index=index,
            search_type=search_type,
            search_condition=search_condition,
            search_list=search_list,
        )

    @mcp.tool()
    def del_mail(index: int) -> Dict[str, Any]:
        """刪除信件。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        Args:
            index (int): 信件編號。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '刪除成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage, "del_mail", index=index, success_message="刪除成功"
        )

    @mcp.tool()
    def give_money(
        ptt_id: str,
        money: int,
        red_bag_title: Optional[str] = None,
        red_bag_content: Optional[str] = None,
    ) -> Dict[str, Any]:
        """轉帳 Ptt 幣給指定使用者。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        Args:
            ptt_id (str): 接收 Ptt 幣的使用者 ID。
            money (int): 轉帳金額。
            red_bag_title (str, optional): 紅包標題。如果提供，將會以紅包形式轉帳。
            red_bag_content (str, optional): 紅包內容。如果提供，將會以紅包形式轉帳。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '轉帳成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "give_money",
            ptt_id=ptt_id,
            money=money,
            red_bag_title=red_bag_title,
            red_bag_content=red_bag_content,
            success_message="轉帳成功",
        )

    @mcp.tool()
    def get_user(user_id: str) -> Dict[str, Any]:
        """取得使用者資訊。

        註記：此函式必須先登入 PTT。

        Args:
            user_id (str): 目標使用者的 PTT ID。

        Returns:
            Dict[str, Any]: 一個包含使用者資料的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含使用者詳細資訊，例如：
                            {'success': True, 'data': {
                                'ptt_id': '使用者ID',
                                'money': Ptt幣餘額,
                                'login_count': 登入次數,
                                'account_verified': 帳號是否認證,
                                'legal_post': 有效文章數,
                                'illegal_post': 退文數 (PTT1 獨有),
                                'activity': 目前動態,
                                'mail': 私人信箱狀態,
                                'last_login_date': 上次上站日期,
                                'last_login_ip': 上次上站IP,
                                'five_chess': 五子棋戰績,
                                'chess': 象棋戰績,
                                'signature_file': 簽名檔內容
                            }}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(memory_storage, "get_user", user_id=user_id)

    @mcp.tool()
    def search_user(
        ptt_id: str, min_page: Optional[int] = None, max_page: Optional[int] = None
    ) -> Dict[str, Any]:
        """搜尋使用者。

        註記：此函式必須先登入 PTT。

        Args:
            ptt_id (str): 欲搜尋的 PTT ID 關鍵字。
            min_page (int, optional): 最小頁數，從 1 開始。預設為 1。
            max_page (int, optional): 最大頁數。預設為搜尋到的最後一頁。

        Returns:
            Dict[str, Any]: 一個包含搜尋結果的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含符合條件的使用者 ID 列表，例如：
                            {'success': True, 'data': ['user1', 'user2', ...]}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "search_user",
            ptt_id=ptt_id,
            min_page=min_page,
            max_page=max_page,
        )

    @mcp.tool()
    def change_pw(new_password: str) -> Dict[str, Any]:
        """更改 PTT 登入密碼。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        註記：此函式必須先登入 PTT。

        Args:
            new_password (str): 新密碼。密碼長度限制為 8 個字元。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '密碼更改成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "change_pw",
            new_password=new_password,
            success_message="密碼更改成功",
        )

    @mcp.tool()
    def get_time() -> Dict[str, Any]:
        """取得 PTT 系統時間。

        註記：此函式必須先登入 PTT。

        Returns:
            Dict[str, Any]: 一個包含 PTT 系統時間的字典，或是在失敗時回傳錯誤訊息。
                            成功: {'success': True, 'data': 'HH:MM'} (例如: {'success': True, 'data': '14:30'})
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(memory_storage, "get_time")

    @mcp.tool()
    def get_all_boards() -> Dict[str, Any]:
        """取得 PTT 全站看板清單。

        註記：此函式必須先登入 PTT。

        Returns:
            Dict[str, Any]: 一個包含看板清單的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含看板名稱列表，例如：
                            {'success': True, 'data': ['Board1', 'Board2', ...]}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(memory_storage, "get_all_boards")

    @mcp.tool()
    def get_favourite_boards() -> Dict[str, Any]:
        """取得我的最愛看板清單。

        註記：此函式必須先登入 PTT。

        Returns:
            Dict[str, Any]: 一個包含收藏看板清單的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含收藏看板的列表，每個看板是一個字典，例如：
                            {'success': True, 'data': [
                                {'board': '看板名稱', 'type': '看板類型', 'title': '看板標題'},
                                ...
                            ]}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(memory_storage, "get_favourite_boards")

    @mcp.tool()
    def get_board_info(board: str, get_post_types: bool = False) -> Dict[str, Any]:
        """取得看板資訊。

        註記：此函式必須先登入 PTT。

        Args:
            board (str): 看板名稱。
            get_post_types (bool, optional): 是否取得文章類型，例如：八卦板的「問卦」。預設為 False。
                                             回傳的結果，你可以在結果中的 post_kind_list 找到，並可以在 post 功能中用 title_index 指定用哪一個類型。
                                             編號由 1 開始。

        Returns:
            Dict[str, Any]: 一個包含看板資訊的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含看板詳細資訊，例如：
                            {'success': True, 'data': {
                                'board': '看板名稱',
                                'online_user': 在線人數,
                                'mandarin_des': '中文敘述',
                                'moderators': ['板主1', '板主2', ...],
                                'open_status': 是否公開,
                                'into_top_ten_when_hide': 隱板時是否可進十大,
                                'can_non_board_members_post': 非看板會員是否可發文,
                                'can_reply_post': 是否可回應文章,
                                'self_del_post': 是否可自刪文章,
                                'can_comment_post': 是否可推文,
                                'can_boo_post': 是否可噓文,
                                'can_fast_push': 是否可快速連推,
                                'min_interval_between_comments': 推文最短間隔時間,
                                'is_comment_record_ip': 推文是否記錄IP,
                                'is_comment_aligned': 推文是否對齊,
                                'can_moderators_del_illegal_content': 板主是否可刪除違規文字,
                                'does_tran_post_auto_recorded_and_require_post_permissions': 轉錄文章是否自動記錄並需發文權限,
                                'is_cool_mode': 是否為冷靜模式,
                                'is_require18': 是否限制18歲以下進入,
                                'require_login_time': 發文限制登入次數,
                                'require_illegal_post': 發文限制退文篇數,
                                'post_kind_list': 文章類型列表 (如果 get_post_types 為 True)
                            }}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage, "get_board_info", board=board, get_post_types=get_post_types
        )

    @mcp.tool()
    def get_aid_from_url(url: str) -> Dict[str, Any]:
        """從 PTT 文章網址中解析出看板名稱與文章 AID。

        不需要登入 PTT。

        Args:
            url (str): PTT 文章的完整 URL，例如 "https://www.ptt.cc/bbs/BoardName/M.1234567890.A.BCD.html"。

        Returns:
            Dict[str, Any]: 一個包含看板名稱與文章 AID 的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含一個列表，其中第一個元素是看板名稱，第二個元素是文章 AID，例如：
                            {'success': True, 'data': ['BoardName', 'M.1234567890.A.BCD']}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        try:
            board_name, aid = PyPtt.API().get_aid_from_url(url)
            return {"success": True, "data": [board_name, aid]}
        except Exception as e:
            return {"success": False, "message": f"解析網址失敗: {e}"}

    @mcp.tool()
    def get_bottom_post_list(board: str) -> Dict[str, Any]:
        """取得看板置底文章清單。

        註記：此函式必須先登入 PTT。

        Args:
            board (str): 看板名稱。

        Returns:
            Dict[str, Any]: 一個包含置底文章清單的字典，或是在失敗時回傳錯誤訊息。
                            成功時，'data' 鍵包含置底文章的列表，每篇文章是一個字典，包含文章的詳細資訊，例如：
                            {'success': True, 'data': [
                                {'board': '看板名稱', 'aid': '文章ID', ...},
                                ...
                            ]}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(memory_storage, "get_bottom_post_list", board=board)

    @mcp.tool()
    def set_board_title(board: str, new_title: str) -> Dict[str, Any]:
        """設定看板標題。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        必須先登入 PTT，且登入帳號需為該看板板主。

        Args:
            board (str): 看板名稱。
            new_title (str): 新的看板標題。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '看板標題設定成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "set_board_title",
            board=board,
            new_title=new_title,
            success_message="看板標題設定成功",
        )

    @mcp.tool()
    def bucket(
        board: str, ptt_id: str, bucket_days: int, reason: str
    ) -> Dict[str, Any]:
        """將指定使用者水桶。

        重要！務必遵守！執行前務必顯示內容並與使用者確認後才可以執行。
        Important! Be sure to follow! Must display content and confirm with the user before execution.

        必須先登入 PTT，且登入帳號需為該看板板主。

        Args:
            board (str): 看板名稱。
            ptt_id (str): 欲水桶的 PTT ID。
            bucket_days (int): 水桶天數。
            reason (str): 水桶原因。

        Returns:
            Dict[str, Any]: 一個包含操作結果的字典。
                            成功: {'success': True, 'message': '水桶成功'}
                            失敗: {'success': False, 'message': '...', 'code': '...'}
        """
        return _call_ptt_service(
            memory_storage,
            "bucket",
            board=board,
            ptt_id=ptt_id,
            bucket_days=bucket_days,
            reason=reason,
            success_message="水桶成功",
        )
