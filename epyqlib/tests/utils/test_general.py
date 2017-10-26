import epyqlib.utils.general


def test_container():
    c = epyqlib.utils.general.Container(a=1, b=2)

    assert hasattr(c, 'a')
    assert hasattr(c, 'b')
    assert c.a == 1
    assert c.b == 2


def test_underscored_to_upper_camel():
    name = 'abc_de_fgh_IJK'
    expected = 'AbcDeFghIjk'

    result = epyqlib.utils.general.underscored_to_upper_camel(name)

    assert result == expected


def test_underscored_camel_to_upper_camel():
    name = 'abc_de_fgh_IJK'
    expected = 'AbcDeFghIJK'

    result = epyqlib.utils.general.underscored_camel_to_upper_camel(name)

    assert result == expected


def test_cameled_to_spaced():
    name = 'abcDeFghIjk'
    expected = 'abc De Fgh Ijk'

    result = epyqlib.utils.general.cameled_to_spaced(name)

    assert result == expected


def test_cameled_to_spaced_acronym():
    name = 'ABCDefGhi'
    expected = 'ABC Def Ghi'

    result = epyqlib.utils.general.cameled_to_spaced(name)

    assert result == expected


def test_underscored_camel_to_title_spaced():
    name = 'abcDeFghIjk_lmnOp'
    expected = 'Abc De Fgh Ijk Lmn Op'

    result = epyqlib.utils.general.underscored_camel_to_title_spaced(name)

    assert result == expected


def test_underscored_camel_to_title_spaced_acronym():
    name = 'ABCDefGhi_lmn'
    expected = 'ABC Def Ghi Lmn'

    result = epyqlib.utils.general.underscored_camel_to_title_spaced(name)

    assert result == expected
