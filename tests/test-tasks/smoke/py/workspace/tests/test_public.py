from src.add import add_numbers


def test_add_integers():
    assert add_numbers(2, 3) == 5


def test_add_zero():
    assert add_numbers(7, 0) == 7
