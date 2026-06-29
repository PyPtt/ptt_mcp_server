from auto_version import _version_key


def test_version_key():
    assert _version_key("0.3.0") > _version_key("0.2.15")
    assert _version_key("1.0.0") > _version_key("0.20.0")
    assert _version_key("0.10.0") > _version_key("0.9.0")
    assert _version_key("0.3.0") == _version_key("0.3.0")


if __name__ == "__main__":
    test_version_key()
    print("OK")
