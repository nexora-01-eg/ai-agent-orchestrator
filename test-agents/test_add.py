from test_opencode import add


def test_add():
    assert add(5, 3) == 8


def test_add_negative():
    assert add(-1, -1) == -2