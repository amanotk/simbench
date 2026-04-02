from src.add import add_numbers


def test_add_floats():
    assert add_numbers(1.25, 2.5) == 3.75


def test_add_negative_value():
    assert add_numbers(-4, 9) == 5
