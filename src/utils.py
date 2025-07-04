from typing import Dict, Any, Optional

import PyPtt  # type: ignore


def _handle_ptt_exception(e: Exception, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    EXCEPTION_MAPPING = {
        PyPtt.RequireLogin: ("尚未登入，請先執行 login", "NOT_LOGGED_IN"),
        PyPtt.UnregisteredUser: ("未註冊使用者", "UNREGISTERED_USER"),
        PyPtt.NoSuchBoard: ("找不到看板: {board}", "NO_SUCH_BOARD"),
        PyPtt.NoSuchPost: (
            "在看板 {board} 中找不到文章 AID: {aid} 或 Index: {index}",
            "NO_SUCH_POST",
        ),
        PyPtt.NoPermission: ("沒有權限", "NO_PERMISSION"),
        PyPtt.LoginError: ("登入失敗", "LOGIN_FAILED"),
        PyPtt.WrongIDorPassword: ("帳號或密碼錯誤", "WRONG_CREDENTIALS"),
        PyPtt.CantResponse: ("已結案並標記, 不得回應", "CANT_RESPONSE"),
        PyPtt.NoFastComment: ("推文間隔太短", "NO_FAST_COMMENT"),
        PyPtt.NoSuchUser: ("找不到使用者: {ptt_id}", "NO_SUCH_USER"),
        PyPtt.NoSuchMail: ("找不到信件 Index: {index}", "NO_SUCH_MAIL"),
        PyPtt.MailboxFull: ("信箱已滿", "MAILBOX_FULL"),
        PyPtt.NoMoney: ("餘額不足", "NO_MONEY"),
        PyPtt.SetContactMailFirst: ("需要先設定聯絡信箱", "SET_CONTACT_MAIL_FIRST"),
        PyPtt.WrongPassword: ("密碼錯誤", "WRONG_PASSWORD"),
        PyPtt.NeedModeratorPermission: (
            "需要看板管理員權限",
            "NEED_MODERATOR_PERMISSION",
        ),
    }

    for exc_type, (message_format, code) in EXCEPTION_MAPPING.items():
        if isinstance(e, exc_type):
            message = (
                message_format.format(**kwargs)
                if "{" in message_format
                else message_format
            )
            return {"success": False, "message": message, "code": code}
    return {
        "success": False,
        "message": f"操作時發生未知錯誤: {e}",
        "args": kwargs,
        "code": "UNKNOWN_ERROR",
    }


def _call_ptt_service(
    session_storage_instance,
    method_name: str,
    success_message: Optional[str] = None,
    empty_data_message: Optional[str] = None,
    empty_data_code: Optional[str] = None,
    **kwargs,
) -> Dict[str, Any]:
    ptt_service = session_storage_instance.get("ptt_bot")
    if ptt_service is None:
        return {
            "success": False,
            "message": "尚未登入，請先執行 login",
            "code": "NOT_LOGGED_IN",
        }

    try:
        result = ptt_service.call(method_name, kwargs)
        response = {"success": True, "data": result}

        if success_message:
            response["message"] = success_message
            del response["data"]
        elif not result and empty_data_message and empty_data_code:
            response["success"] = False
            response["message"] = empty_data_message.format(**kwargs)
            response["code"] = empty_data_code

        return response
    except Exception as e:
        return _handle_ptt_exception(e, kwargs)
