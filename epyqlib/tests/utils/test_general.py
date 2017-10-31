import epyqlib.utils.general


def test_container():
    c = epyqlib.utils.general.Container(a=1, b=2)

    assert hasattr(c, 'a')
    assert hasattr(c, 'b')
    assert c.a == 1
    assert c.b == 2


def test_spaced_to_lower_camel():
    name = 'ABC Def ghi LM1'
    expected = 'abcDefGhiLM1'

    result = epyqlib.utils.general.spaced_to_lower_camel(name)

    assert result == expected


def test_spaced_to_upper_camel():
    name = 'ABC Def ghi LM1'
    expected = 'ABCDefGhiLM1'

    result = epyqlib.utils.general.spaced_to_upper_camel(name)

    assert result == expected


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
    name = 'abcDeFghIjk - lmnOp'
    expected = 'abc De Fgh Ijk - lmn Op'

    result = epyqlib.utils.general.cameled_to_spaced(name)

    assert result == expected


def test_cameled_to_spaced_dashed():
    name = 'ABC - DefGhi'
    expected = 'ABC - Def Ghi'

    result = epyqlib.utils.general.cameled_to_spaced(name)

    assert result == expected


def test_cameled_to_spaced_acronym():
    name = ' XY1ABCDefGhiJKLMnOP1 '
    expected = 'XY1 ABC Def Ghi JKL Mn OP1'

    result = epyqlib.utils.general.cameled_to_spaced(name)

    assert result == expected


def test_underscored_camel_to_title_spaced():
    name = 'abcDeFghIjk_lmnOp'
    expected = 'Abc De Fgh Ijk Lmn Op'

    result = epyqlib.utils.general.underscored_camel_to_title_spaced(name)

    assert result == expected


def test_underscored_camel_to_title_spaced_acronym():
    name = 'XY1ABCDefGhi_lmnOP1'
    expected = 'XY1 ABC Def Ghi Lmn OP1'

    result = epyqlib.utils.general.underscored_camel_to_title_spaced(name)

    assert result == expected


def test_underscored_camel_to_title_spaced_acronym_with_number_alone():
    name = 'AB1'
    expected = 'AB1'

    result = epyqlib.utils.general.underscored_camel_to_title_spaced(name)

    assert result == expected
