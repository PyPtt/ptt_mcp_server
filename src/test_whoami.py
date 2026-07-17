import types

from test_switch_account import _load_api_ptt, _register_tools


def test_whoami_not_logged_in():
    tools, memory_storage = _register_tools(_load_api_ptt())

    result = tools["whoami"]()
    assert result["success"] is True
    assert result["account"] == "default"
    assert result["ptt_id"] is None
    assert result["logged_in"] is False


def test_whoami_logged_in():
    tools, memory_storage = _register_tools(_load_api_ptt())
    memory_storage["ptt_bot"] = types.SimpleNamespace(
        _api=types.SimpleNamespace(_is_login=True, ptt_id="CodingMan")
    )
    memory_storage["current_account"] = "alt"

    result = tools["whoami"]()
    assert result["account"] == "alt"
    assert result["ptt_id"] == "CodingMan"
    assert result["logged_in"] is True


def test_whoami_stale_ptt_id_after_logout():
    # PyPtt 登出後不會清 ptt_id，whoami 不得回報殘留值
    tools, memory_storage = _register_tools(_load_api_ptt())
    memory_storage["ptt_bot"] = types.SimpleNamespace(
        _api=types.SimpleNamespace(_is_login=False, ptt_id="stale")
    )

    result = tools["whoami"]()
    assert result["logged_in"] is False
    assert result["ptt_id"] is None


if __name__ == "__main__":
    test_whoami_not_logged_in()
    test_whoami_logged_in()
    test_whoami_stale_ptt_id_after_logout()
    print("OK")
