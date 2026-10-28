import random

import kociemba
import pytest

from rubik import cube
from rubik.cube import SOLVED, apply_moves, piece_problems, random_scramble


def scrambled(seed):
    return apply_moves(SOLVED, random_scramble(25, random.Random(seed)))[-1]


def swap(state, *pairs):
    s = list(state)
    for a, b in pairs:
        s[a], s[b] = s[b], s[a]
    return "".join(s)


def idx(name):
    return next(i for i, f in enumerate(cube.FACELETS) if f["name"] == name)


def test_counts_pieces():
    assert len(cube.CORNERS) == 8 and len(cube.EDGES) == 12


@pytest.mark.parametrize("seed", range(30))
def test_scrambles_are_valid(seed):
    assert piece_problems(scrambled(seed)) == []


def test_twisted_corner():
    s = list(SOLVED)
    a, b, c = (idx(n) for n in ("U9", "R1", "F3"))
    s[a], s[b], s[c] = s[c], s[a], s[b]
    assert piece_problems("".join(s)) == ["Eine Ecke ist verdreht"]


def test_flipped_edge():
    assert piece_problems(swap(SOLVED, (idx("U8"), idx("F2")))) == ["Eine Kante ist gekippt"]


def test_two_edges_swapped():
    s = swap(SOLVED, (idx("U8"), idx("U6")), (idx("F2"), idx("R2")))
    assert piece_problems(s) == ["Zwei Steine sind vertauscht"]


def test_impossible_corner_colors():
    # Zwei Aufkleber derselben Ecke getauscht -> spiegelverkehrt
    problems = piece_problems(swap(SOLVED, (idx("R1"), idx("F3"))))
    assert any("spiegelverkehrt" in p for p in problems)


def test_agrees_with_kociemba_on_random_damage():
    """Zufällige Vertauschungen: lösbar heißt, der Löser findet eine Lösung, die
    wirklich löst. (Die C-Bibliothek gibt bei manchen unmöglichen Ecken eine
    „Lösung“ aus, die nicht löst – deshalb wird hier nachgerechnet.)"""
    rng = random.Random(11)
    for seed in range(150):
        s = scrambled(seed)
        a, b = rng.sample([i for i in range(54) if i % 9 != 4], 2)
        damaged = swap(s, (a, b))
        try:
            moves = kociemba.solve(cube.to_kociemba(damaged)).split()
            solvable = apply_moves(damaged, moves)[-1] == SOLVED
        except ValueError:
            solvable = False
        assert (piece_problems(damaged) == []) == solvable


def test_rotate_face_four_times_is_identity():
    assert cube.rotate_face("abcdefghi", 1) == "gdahebifc"
    assert cube.rotate_face("abcdefghi", 4) == "abcdefghi"


def test_rotate_index_matches_rotate_face():
    cells = "abcdefghi"
    for k in range(4):
        rotated = cube.rotate_face(cells, k)
        assert all(rotated[cube.rotate_index(i, k)] == cells[i] for i in range(9))


def test_orientation_search_undoes_random_photo_rotations():
    rng = random.Random(3)
    for seed in range(15):
        state = scrambled(seed)
        turns = [rng.randrange(4) for _ in range(6)]
        photos = "".join(cube.rotate_face(state[f * 9 : f * 9 + 9], turns[f]) for f in range(6))
        found = cube.orientations(photos)
        assert found and found[0][1] == state


def test_issues_name_the_affected_cells():
    # F2 Grün -> Rot macht U8/F2 zu einer zweiten W/R-Kante; R8 Rot -> Grün macht
    # R8/D6 zu einer zweiten G/Y-Kante. Die Farbverteilung bleibt stimmig.
    s = list(SOLVED)
    s[idx("F2")] = "R"
    s[idx("R8")] = "G"
    issues = cube.piece_issues("".join(s))
    assert sum("doppelt" in t for t, _ in issues) == 2
    cells = {i for _, c in issues for i in c}
    assert {idx("F2"), idx("U8"), idx("R8"), idx("D6")} <= cells


def test_global_issue_has_no_cells():
    issues = cube.piece_issues(swap(SOLVED, (idx("U8"), idx("F2"))))
    assert issues == [("Eine Kante ist gekippt", [])]
