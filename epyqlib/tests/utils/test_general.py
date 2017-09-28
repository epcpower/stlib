import epyqlib.utils.general


def test_collection():
    c = epyqlib.utils.general.Container(a=1, b=2)

    assert hasattr(c, 'a')
    assert hasattr(c, 'b')
    assert c.a == 1
    assert c.b == 2
