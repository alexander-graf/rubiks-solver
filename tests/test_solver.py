import random

import pytest

from rubik import solver
from rubik.cube import SOLVED, apply_moves, parse_moves, random_scramble

FACE_SLICE = {f: slice(i * 9, i * 9 + 9) for i, f in enumerate("URFDLB")}
WHERE = {"U": "oben", "D": "unten", "L": "links", "R": "rechts"}


def run(state: str, moves: list[str]) -> str:
    return apply_moves(state, moves)[-1] if moves else state


def test_solves_random_scrambles():
    rng = random.Random(7)
    for _ in range(30):
        state = run(SOLVED, random_scramble(25, rng))
        moves = solver.solve(state)
        assert run(state, moves) == SOLVED
        assert len(moves) <= 24


def test_solved_cube_needs_no_moves():
    assert solver.solve(SOLVED) == []


def test_twisted_corner_is_rejected():
    # U9/R1/F3-Ecke im Uhrzeigersinn verdreht: Farbverteilung stimmt, lösbar ist es nicht
    s = list(SOLVED)
    u9, r1, f3 = 8, 9, 20
    s[u9], s[r1], s[f3] = s[f3], s[u9], s[r1]
    with pytest.raises(solver.SolveError, match="nicht lösbar"):
        solver.solve("".join(s))


def test_wrong_color_counts_are_rejected():
    with pytest.raises(solver.SolveError, match="9×"):
        solver.solve("Y" + SOLVED[1:])


@pytest.mark.parametrize("move", ["R", "R'", "L", "L'", "U", "U'", "D", "D'"])
def test_text_direction_matches_geometry(move):
    """Wohin wandern die grünen Felder der Vorderseite? Das muss im Klartext stehen."""
    after = run(SOLVED, [move])
    gone_to = [f for f in "URDL" if "G" in after[FACE_SLICE[f]]]
    assert len(gone_to) == 1
    assert solver.describe(move).endswith("nach " + WHERE[gone_to[0]])


@pytest.mark.parametrize("move, direction", [("B", "links"), ("B'", "rechts")])
def test_back_text_follows_top_edge(move, direction):
    """Bei B wandern die weißen Felder der oberen Kante zur Seite."""
    after = run(SOLVED, [move])
    side = "L" if "W" in after[FACE_SLICE["L"]] else "R"
    assert WHERE[side] == direction
    assert solver.describe(move).endswith(direction)


def test_half_turn_text():
    assert solver.describe("F2") == "Vorderseite halb herum (180°, Richtung egal)"


def test_solve_shorter_is_not_longer_and_still_solves():
    state = run(SOLVED, parse_moves("R U2 F' L D B2 R' U F2 D' L2 B U' R2 F D2 L' B'"))
    quick = solver.solve(state)
    better = solver.solve_shorter(state, seconds=3)
    assert len(better) <= len(quick)
    assert run(state, better) == SOLVED
