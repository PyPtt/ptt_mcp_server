"""閒置自動重登與登入頻率限制測試。

沿用 test_switch_account_pool 的假 Service 工廠；以替換 api_ptt._clock 快轉時間。
"""

import pytest

from test_switch_account import _load_api_ptt, _register_tools, _FakeService
from test_switch_account_pool import _setup


class _Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def env(monkeypatch):
    api_ptt = _load_api_ptt()
    factory = _setup(api_ptt)
    # 死連線的 get_time 會走到 _handle_ptt_exception 的 ParameterError 分支。
    if not hasattr(api_ptt.PyPtt, "ParameterError"):
        monkeypatch.setattr(
            api_ptt.PyPtt,
            "ParameterError",
            type("ParameterError", (Exception,), {}),
            raising=False,
        )
    clock = _Clock()
    monkeypatch.setattr(api_ptt, "_clock", clock)
    tools, ms = _register_tools(api_ptt)
    return api_ptt, factory, clock, tools, ms


def test_login_throttled_within_interval(env):
    api_ptt, factory, clock, tools, ms = env
    svc1 = _FakeService(alive=True)
    svc2 = _FakeService(alive=True)
    factory.prepare(svc1, svc2)

    assert tools["login"]()["success"] is True
    svc1.alive = False

    clock.now += 10
    result = tools["login"]()
    assert result["success"] is False
    assert result["code"] == "LOGIN_THROTTLED"
    assert 0 < result["retry_after"] <= api_ptt.LOGIN_MIN_INTERVAL
    assert len(factory.handed_out) == 1  # 沒有真的去連 PTT

    clock.now += api_ptt.LOGIN_MIN_INTERVAL
    assert tools["login"]()["success"] is True
    assert ms["ptt_bot"] is svc2


def test_failed_login_also_throttled(env):
    api_ptt, factory, clock, tools, ms = env
    wrong = api_ptt.PyPtt.WrongIDorPassword("bad pw")
    factory.prepare(_FakeService(login_error=wrong))

    assert tools["login"]()["success"] is False
    assert tools["login"]()["code"] == "LOGIN_THROTTLED"
    assert len(factory.handed_out) == 1


def test_login_when_alive_is_not_throttled(env):
    # 連線活著時 login() 不會重登，自然也不受頻率限制。
    api_ptt, factory, clock, tools, ms = env
    svc = _FakeService(alive=True)
    factory.prepare(svc)

    tools["login"]()
    assert tools["login"]()["success"] is True
    assert svc.login_calls == 1


def test_idle_disconnect_relogs_before_call(env):
    api_ptt, factory, clock, tools, ms = env
    svc1 = _FakeService(alive=True)
    svc2 = _FakeService(alive=True)
    factory.prepare(svc1, svc2)

    tools["login"]()
    svc1.alive = False  # 閒置被 PTT 斷線
    clock.now += api_ptt.LOGIN_MIN_INTERVAL + api_ptt.IDLE_PROBE_SECONDS

    assert tools["get_time"]()["success"] is True
    assert svc1.close_calls == 1  # 死連線被汰換
    assert svc2.login_calls == 1  # 自動重登一次
    assert ms["ptt_bot"] is svc2


def test_recent_call_skips_probe(env):
    # 剛用過就不探測：連線即使死了也不會在呼叫前重登。
    api_ptt, factory, clock, tools, ms = env
    svc = _FakeService(alive=True)
    factory.prepare(svc)

    tools["login"]()
    svc.alive = False
    clock.now += api_ptt.IDLE_PROBE_SECONDS - 1

    tools["get_time"]()
    assert len(factory.handed_out) == 1


def test_idle_relogin_throttled_returns_error_without_calling(env):
    api_ptt, factory, clock, tools, ms = env
    svc1 = _FakeService(alive=True)
    factory.prepare(svc1)

    tools["login"]()
    svc1.alive = False
    # 超過閒置探測門檻，但還在登入間隔內 → 回 LOGIN_THROTTLED，不送出原本的操作。
    clock.now += api_ptt.IDLE_PROBE_SECONDS
    ms["last_login_at"]["default"] = clock.now - 1

    result = tools["get_time"]()
    assert result["code"] == "LOGIN_THROTTLED"
    assert len(factory.handed_out) == 1


def test_no_auto_login_when_logged_out(env):
    api_ptt, factory, clock, tools, ms = env
    factory.prepare(_FakeService(alive=True))

    tools["login"]()
    assert tools["logout"]()["success"] is True
    clock.now += api_ptt.LOGIN_MIN_INTERVAL + api_ptt.IDLE_PROBE_SECONDS

    assert tools["get_time"]()["code"] == "NOT_LOGGED_IN"
    assert len(factory.handed_out) == 1
