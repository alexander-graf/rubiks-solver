import random

import pytest

from rubik.cube import (
    SOLVED,
    apply_move,
    apply_moves,
    check,
    parse_moves,
    random_scramble,
    to_kociemba,
)


def run(moves: str, state: str = SOLVED) -> str:
    return apply_moves(state, parse_moves(moves))[-1]


def faces(kociemba: str) -> list[str]:
    return [kociemba[i : i + 9] for i in range(0, 54, 9)]


# Von Hand hergeleitet, Reihenfolge U R F D L B
@pytest.mark.parametrize(
    "move, expected",
    [
        ("R", ["UUFUUFUUF", "RRRRRRRRR", "FFDFFDFFD", "DDBDDBDDB", "LLLLLLLLL", "UBBUBBUBB"]),
        ("U", ["UUUUUUUUU", "BBBRRRRRR", "RRRFFFFFF", "DDDDDDDDD", "FFFLLLLLL", "LLLBBBBBB"]),
        ("F", ["UUUUUULLL", "URRURRURR", "FFFFFFFFF", "RRRDDDDDD", "LLDLLDLLD", "BBBBBBBBB"]),
    ],
)
def test_single_moves_match_kociemba_convention(move, expected):
    assert faces(to_kociemba(run(move))) == expected


@pytest.mark.parametrize("face", "URFDLB")
def test_four_quarter_turns_are_identity(face):
    assert run(f"{face} {face} {face} {face}") == SOLVED


@pytest.mark.parametrize("face", "URFDLB")
def test_prime_undoes_move(face):
    assert run(f"{face} {face}'") == SOLVED
    assert run(f"{face}2 {face}2") == SOLVED


def test_sexy_move_six_times_is_identity():
    assert run("R U R' U' " * 6) == SOLVED
    assert run("R U R' U' " * 3) != SOLVED


def test_scramble_and_inverse_return_to_solved():
    rng = random.Random(1)
    for _ in range(50):
        moves = random_scramble(25, rng)
        inverse = [m[0] + {"": "'", "'": "", "2": "2"}[m[1:]] for m in reversed(moves)]
        assert apply_moves(apply_moves(SOLVED, moves)[-1], inverse)[-1] == SOLVED


def test_scrambles_keep_counts_and_centers():
    state = apply_moves(SOLVED, random_scramble(30, random.Random(2)))[-1]
    assert state != SOLVED
    assert check(state) == []


def test_parse_accepts_compact_and_curly_apostrophe():
    assert parse_moves("RU'F2 B’,D") == ["R", "U'", "F2", "B'", "D"]
    assert parse_moves("R2'") == ["R2"]


def test_parse_rejects_unknown():
    with pytest.raises(ValueError):
        parse_moves("R X")


def test_check_reports_problems():
    assert check(SOLVED) == []
    broken = "Y" + SOLVED[1:]
    problems = check(broken)
    assert any("Weiß" in p for p in problems)
    assert any("Gelb" in p for p in problems)
    assert any("U5" in p for p in check(SOLVED[:4] + "Y" + SOLVED[5:]))
