"""Service 池行為測試：原子切換、死連線汰換、洩漏防護（close）、真實登入狀態。

沿用 test_switch_account 的 _load_api_ptt/_register_tools 與假 Service。
以「工廠依預排順序發假 Service」驅動 _login_new_service 的真實路徑，
藉此連 close-on-failed-login 一併驗到。
"""

from test_switch_account import _FakeService, _load_api_ptt, _register_tools

# _handle_ptt_exception 會參照這些 PyPtt 例外類別，stub 需補上才不會 AttributeError。
_PTT_EXCEPTIONS = [
    "RequireLogin", "UnregisteredUser", "NoSuchBoard", "NoSuchPost",
    "NoPermission", "LoginError", "WrongIDorPassword", "CantResponse",
    "NoFastComment", "NoSuchUser", "NoSuchMail", "MailboxFull", "NoMoney",
    "SetContactMailFirst", "WrongPassword", "NeedModeratorPermission",
]


class _ServiceFactory:
    # 取代 PyPtt.Service：依測試預排順序把假 Service 發給 _login_new_service。
    def __init__(self):
        self.handed_out = []
        self._queue = []

    def prepare(self, *svcs):
        self._queue.extend(svcs)

    def __call__(self, config=None):
        svc = self._queue.pop(0)
        self.handed_out.append(svc)
        return svc

    @property
    def login_total(self):
        return sum(s.login_calls for s in self.handed_out)


def _setup(api_ptt):
    ptt = api_ptt.PyPtt
    for name in _PTT_EXCEPTIONS:
        if not hasattr(ptt, name):
            setattr(ptt, name, type(name, (Exception,), {}))
    factory = _ServiceFactory()
    setattr(ptt, "Service", factory)
    return factory


def test_atomic_on_failed_switch():
    # (a)(e) 切到密碼錯的帳號後，active session 與 current 維持不變；失敗的 svc 被 close。
    api_ptt = _load_api_ptt()
    factory = _setup(api_ptt)
    tools, ms = _register_tools(api_ptt)
    ms["accounts"]["bad"] = {"id": "accX", "pw": "wrong"}

    svc_default = _FakeService()
    wrong = api_ptt.PyPtt.WrongIDorPassword("bad pw")
    svc_bad = _FakeService(login_error=wrong)
    factory.prepare(svc_default, svc_bad)

    assert tools["switch_account"]("default")["success"] is True
    assert ms["ptt_bot"] is svc_default
    assert ms["current_account"] == "default"

    result = tools["switch_account"]("bad")
    assert result["success"] is False
    assert ms["ptt_bot"] is svc_default          # 原子性：active 不變
    assert ms["current_account"] == "default"
    assert ms["ptt_id"] == "acc1"
    assert svc_bad.close_calls == 1              # 洩漏防護
    assert "bad" not in ms["pool"]


def test_switch_to_new_account():
    # (b) 成功切到新帳號：池多一筆、ptt_bot 指到新 svc、current 更新。
    api_ptt = _load_api_ptt()
    factory = _setup(api_ptt)
    tools, ms = _register_tools(api_ptt)

    svc_default = _FakeService()
    svc_alt = _FakeService()
    factory.prepare(svc_default, svc_alt)

    tools["switch_account"]("default")
    result = tools["switch_account"]("alt")

    assert result["success"] is True
    assert set(ms["pool"]) == {"default", "alt"}
    assert ms["ptt_bot"] is svc_alt
    assert ms["current_account"] == "alt"


def test_switch_back_to_alive_reuses():
    # (c) 切回池中活著的帳號：不觸發新 login，ptt_bot 重指到既有 svc。
    api_ptt = _load_api_ptt()
    factory = _setup(api_ptt)
    tools, ms = _register_tools(api_ptt)

    svc_default = _FakeService(alive=True)
    svc_alt = _FakeService(alive=True)
    factory.prepare(svc_default, svc_alt)

    tools["switch_account"]("default")
    tools["switch_account"]("alt")
    logins_before = factory.login_total
    services_before = len(factory.handed_out)

    result = tools["switch_account"]("default")
    assert result["success"] is True
    assert factory.login_total == logins_before          # 沒有新 login
    assert len(factory.handed_out) == services_before     # 沒有新 Service
    assert ms["ptt_bot"] is svc_default
    assert ms["current_account"] == "default"


def test_switch_to_dead_relogs():
    # (d)(e) 切到池中死掉的帳號：舊 svc 被 close，且發生一次重登。
    api_ptt = _load_api_ptt()
    factory = _setup(api_ptt)
    tools, ms = _register_tools(api_ptt)

    svc_default = _FakeService(alive=True)
    svc_alt = _FakeService(alive=True)
    svc_default2 = _FakeService(alive=True)
    factory.prepare(svc_default, svc_alt, svc_default2)

    tools["switch_account"]("default")
    tools["switch_account"]("alt")
    svc_default.alive = False                     # 模擬 server 端閒置斷線

    result = tools["switch_account"]("default")
    assert result["success"] is True
    assert svc_default.close_calls == 1           # 死連線被汰換並 close
    assert svc_default2.login_calls == 1          # 一次重登
    assert ms["ptt_bot"] is svc_default2
    assert ms["pool"]["default"] is svc_default2


def test_logout_closes_active_only():
    # logout 只登出/close/移除 active 帳號，其他池內帳號不動。
    api_ptt = _load_api_ptt()
    factory = _setup(api_ptt)
    tools, ms = _register_tools(api_ptt)

    svc_default = _FakeService()
    svc_alt = _FakeService()
    factory.prepare(svc_default, svc_alt)

    tools["switch_account"]("default")
    tools["switch_account"]("alt")                # active = alt

    result = tools["logout"]()
    assert result["success"] is True
    assert svc_alt.close_calls == 1
    assert "alt" not in ms["pool"]
    assert ms["ptt_bot"] is None
    assert ms["pool"]["default"] is svc_default    # 其他池內帳號不動
    assert svc_default.close_calls == 0


def test_list_accounts_current_none_when_not_logged_in():
    # (f) 未登入時 current 為 None。
    api_ptt = _load_api_ptt()
    _setup(api_ptt)
    tools, ms = _register_tools(api_ptt)

    assert ms["ptt_bot"] is None
    assert tools["list_accounts"]()["current"] is None


if __name__ == "__main__":
    test_atomic_on_failed_switch()
    test_switch_to_new_account()
    test_switch_back_to_alive_reuses()
    test_switch_to_dead_relogs()
    test_logout_closes_active_only()
    test_list_accounts_current_none_when_not_logged_in()
    print("OK")
