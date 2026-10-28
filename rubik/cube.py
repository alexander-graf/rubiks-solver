"""Würfelmodell: 54 Felder, Züge, Verdrehfolgen.

Ein Zustand ist ein String aus 54 Farbbuchstaben (W Y R O B G) in der
Kociemba-Reihenfolge U1..U9 R1..R9 F1..F9 D1..D9 L1..L9 B1..B9, jede Seite
zeilenweise so gelesen, wie man von außen auf sie schaut.

Koordinaten: x nach rechts (R), y nach oben (U), z nach vorn (F). Ein Feld
ist durch die Position seines Steins (je Achse -1, 0, 1) und seine Normale
festgelegt. Ein Zug dreht alle Felder der Schicht um 90° um die Achse der
Seite; das hält Python und die 3D-Ansicht auf derselben Geometrie.
"""

from __future__ import annotations

import random
import re

Vec = tuple[int, int, int]

FACES = "URFDLB"

# Seite -> (Normale, Richtung "nach rechts", Richtung "nach unten") in der Ansicht von außen
FACE_AXES: dict[str, tuple[Vec, Vec, Vec]] = {
    "U": ((0, 1, 0), (1, 0, 0), (0, 0, 1)),
    "R": ((1, 0, 0), (0, 0, -1), (0, -1, 0)),
    "F": ((0, 0, 1), (1, 0, 0), (0, -1, 0)),
    "D": ((0, -1, 0), (1, 0, 0), (0, 0, -1)),
    "L": ((-1, 0, 0), (0, 0, 1), (0, -1, 0)),
    "B": ((0, 0, -1), (-1, 0, 0), (0, -1, 0)),
}

# Weiß oben, Grün vorn
FACE_COLORS = {"U": "W", "R": "R", "F": "G", "D": "Y", "L": "O", "B": "B"}
COLORS = "WYROBG"
COLOR_NAMES = {"W": "Weiß", "Y": "Gelb", "R": "Rot", "O": "Orange", "B": "Blau", "G": "Grün"}

SOLVED = "".join(FACE_COLORS[f] * 9 for f in FACES)


def _add(*vs: Vec) -> Vec:
    return tuple(sum(c) for c in zip(*vs))  # type: ignore[return-value]


def _scale(v: Vec, k: int) -> Vec:
    return (v[0] * k, v[1] * k, v[2] * k)


def _facelets() -> list[dict]:
    out = []
    for face in FACES:
        n, right, down = FACE_AXES[face]
        for i in range(9):
            row, col = divmod(i, 3)
            pos = _add(n, _scale(right, col - 1), _scale(down, row - 1))
            out.append({"name": f"{face}{i + 1}", "face": face, "pos": pos, "normal": n})
    return out


FACELETS = _facelets()
_INDEX = {(f["pos"], f["normal"]): i for i, f in enumerate(FACELETS)}


def _rotate_cw(v: Vec, axis: Vec) -> Vec:
    """Vierteldrehung im Uhrzeigersinn, von der Spitze der Achse aus gesehen."""
    ax, ay, az = axis
    x, y, z = v
    cross = (ay * z - az * y, az * x - ax * z, ax * y - ay * x)
    dot = ax * x + ay * y + az * z
    # Rodrigues mit cos = 0, sin = -1
    return (-cross[0] + ax * dot, -cross[1] + ay * dot, -cross[2] + az * dot)


def _move_permutation(face: str) -> list[int]:
    """perm[i] = Index, auf den das Feld i bei einer Vierteldrehung wandert."""
    axis = FACE_AXES[face][0]
    perm = list(range(54))
    for i, f in enumerate(FACELETS):
        if sum(p * a for p, a in zip(f["pos"], axis)) == 1:
            perm[i] = _INDEX[(_rotate_cw(f["pos"], axis), _rotate_cw(f["normal"], axis))]
    return perm


_PERMS = {face: _move_permutation(face) for face in FACES}

_MOVE_RE = re.compile(r"([URFDLB])(2'|2|'|’|)")


def parse_moves(text: str) -> list[str]:
    """'R U R' F2' -> ['R', 'U', "R'", 'F2']. Wirft ValueError bei Unbekanntem."""
    moves = []
    for token in text.replace(",", " ").split():
        pos = 0
        while pos < len(token):
            m = _MOVE_RE.match(token, pos)
            if not m:
                raise ValueError(f"Unbekannter Zug: {token[pos:]!r}")
            suffix = m.group(2).replace("’", "'")
            moves.append(m.group(1) + ("2" if suffix.startswith("2") else suffix))
            pos = m.end()
    return moves


def apply_move(state: str, move: str) -> str:
    face, suffix = move[0], move[1:]
    turns = {"": 1, "2": 2, "'": 3}[suffix]
    perm = _PERMS[face]
    s = list(state)
    for _ in range(turns):
        new = s[:]
        for i, target in enumerate(perm):
            new[target] = s[i]
        s = new
    return "".join(s)


def apply_moves(state: str, moves: list[str]) -> list[str]:
    """Liefert alle Zwischenzustände, einschließlich des Endzustands (ohne den Start)."""
    states = []
    for move in moves:
        state = apply_move(state, move)
        states.append(state)
    return states


def random_scramble(length: int = 20, rng: random.Random | None = None) -> list[str]:
    """Zufällige Folge ohne direkt aufeinanderfolgende Züge derselben Seite
    und ohne Muster wie R L R (gegenüberliegende Seiten dazwischen)."""
    rng = rng or random.Random()
    opposite = {"U": "D", "D": "U", "R": "L", "L": "R", "F": "B", "B": "F"}
    moves: list[str] = []
    while len(moves) < length:
        face = rng.choice(FACES)
        if moves and moves[-1][0] == face:
            continue
        if len(moves) >= 2 and moves[-2][0] == face and moves[-1][0] == opposite[face]:
            continue
        moves.append(face + rng.choice(["", "'", "2"]))
    return moves


def check(state: str) -> list[str]:
    """Grobe Prüfung: Länge, Farbbuchstaben, Mittelfelder, je 9 pro Farbe.
    Die Prüfung auf physikalische Lösbarkeit folgt mit der Kamera-Erkennung."""
    if len(state) != 54:
        return [f"Zustand hat {len(state)} statt 54 Felder"]
    problems = []
    bad = sorted(set(state) - set(COLORS))
    if bad:
        problems.append(f"Unbekannte Farbbuchstaben: {', '.join(bad)}")
    for i, face in enumerate(FACES):
        center = state[i * 9 + 4]
        if center != FACE_COLORS[face]:
            problems.append(f"Mittelfeld {face}5 ist {center}, erwartet {FACE_COLORS[face]}")
    for c in COLORS:
        n = state.count(c)
        if n != 9:
            problems.append(f"{COLOR_NAMES[c]} ({c}) kommt {n}× vor statt 9×")
    return problems


def to_kociemba(state: str) -> str:
    """Farbbuchstaben -> Seitenbuchstaben über die Mittelfelder (Eingabe für den Löser)."""
    center_to_face = {state[i * 9 + 4]: face for i, face in enumerate(FACES)}
    return "".join(center_to_face[c] for c in state)
