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


# ---------- Steine: Ecken und Kanten ----------
#
# Eine Ecke wird ab ihrem U/D-Feld im mathematisch positiven Drehsinn gelesen, eine
# Kante ab ihrem U/D-Feld bzw. (in der mittleren Schicht) ab ihrem F/B-Feld. So ist
# „verdreht“ (Ecke) bzw. „gekippt“ (Kante) für alle Positionen gleich definiert.

_FACE_RANK = {"U": 0, "D": 0, "F": 1, "B": 1, "R": 2, "L": 2}


def _det(a: Vec, b: Vec, c: Vec) -> int:
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def _pieces() -> tuple[list[tuple[int, ...]], list[tuple[int, ...]]]:
    by_pos: dict[Vec, list[int]] = {}
    for i, f in enumerate(FACELETS):
        by_pos.setdefault(f["pos"], []).append(i)
    corners, edges = [], []
    for idx in by_pos.values():
        idx.sort(key=lambda i: _FACE_RANK[FACELETS[i]["face"]])
        if len(idx) == 3:
            a, b, c = idx
            if _det(FACELETS[a]["normal"], FACELETS[b]["normal"], FACELETS[c]["normal"]) < 0:
                b, c = c, b
            corners.append((a, b, c))
        elif len(idx) == 2:
            edges.append(tuple(idx))
    return corners, edges


CORNERS, EDGES = _pieces()
_SOLVED_CORNERS = {frozenset(SOLVED[i] for i in p): tuple(SOLVED[i] for i in p) for p in CORNERS}
_SOLVED_EDGES = {frozenset(SOLVED[i] for i in p): tuple(SOLVED[i] for i in p) for p in EDGES}
_CORNER_ID = {k: n for n, k in enumerate(_SOLVED_CORNERS)}
_EDGE_ID = {k: n for n, k in enumerate(_SOLVED_EDGES)}


def _odd(perm: list[int]) -> bool:
    seen, odd = set(), False
    for start in range(len(perm)):
        length = 0
        i = start
        while i not in seen:
            seen.add(i)
            i = perm[i]
            length += 1
        if length and length % 2 == 0:
            odd = not odd
    return odd


def piece_problems(state: str) -> list[str]:
    """Ist die Stellung mit einem echten Würfel erreichbar? Leer = lösbar.
    Setzt eine stimmige Farbverteilung voraus (siehe `check`)."""
    names = lambda p: "/".join(FACELETS[i]["name"] for i in p)  # noqa: E731
    problems = []

    cperm, twist = [], 0
    for p in CORNERS:
        cols = tuple(state[i] for i in p)
        key = frozenset(cols)
        if key not in _SOLVED_CORNERS:
            problems.append(f"Ecke {names(p)} hat Farben {'/'.join(cols)}, die es so nicht gibt")
            continue
        t = next(k for k in range(3) if cols[k] in "WY")
        if cols[t:] + cols[:t] != _SOLVED_CORNERS[key]:
            problems.append(f"Ecke {names(p)} ist spiegelverkehrt ({'/'.join(cols)})")
            continue
        cperm.append(_CORNER_ID[key])
        twist += t

    eperm, flip = [], 0
    for p in EDGES:
        cols = tuple(state[i] for i in p)
        key = frozenset(cols)
        if key not in _SOLVED_EDGES:
            problems.append(f"Kante {names(p)} hat Farben {'/'.join(cols)}, die es so nicht gibt")
            continue
        eperm.append(_EDGE_ID[key])
        flip += cols != _SOLVED_EDGES[key]

    if problems:
        return problems
    if len(set(cperm)) != 8:
        problems.append("Eine Ecke kommt doppelt vor")
    if len(set(eperm)) != 12:
        problems.append("Eine Kante kommt doppelt vor")
    if problems:
        return problems
    if twist % 3:
        problems.append("Eine Ecke ist verdreht")
    if flip % 2:
        problems.append("Eine Kante ist gekippt")
    if _odd(cperm) != _odd(eperm):
        problems.append("Zwei Steine sind vertauscht")
    return problems


# ---------- Ausrichtung der Fotos ----------


def rotate_face(cells: str, turns: int) -> str:
    """9 Felder zeilenweise, `turns` Vierteldrehungen im Uhrzeigersinn."""
    for _ in range(turns % 4):
        cells = "".join(cells[(2 - i % 3) * 3 + i // 3] for i in range(9))
    return cells


def rotate_index(i: int, turns: int) -> int:
    """Wohin wandert Feld i (0–8) bei `turns` Vierteldrehungen im Uhrzeigersinn?"""
    for _ in range(turns % 4):
        r, c = divmod(i, 3)
        i = c * 3 + (2 - r)
    return i


def orientations(state: str) -> list[tuple[dict[str, int], str]]:
    """Alle Drehungen der 6 Fotos (je 0–3 Vierteldrehungen), die einen lösbaren Würfel
    ergeben – verschiedene Zustände, die mit den wenigsten Drehungen zuerst."""
    faces = [state[i * 9 : i * 9 + 9] for i in range(6)]
    rotated = [[rotate_face(f, k) for k in range(4)] for f in faces]
    found: dict[str, dict[str, int]] = {}
    for combo in range(4**6):
        turns = [(combo >> (2 * f)) & 3 for f in range(6)]
        candidate = "".join(rotated[f][turns[f]] for f in range(6))
        if candidate in found or piece_problems(candidate):
            continue
        found[candidate] = dict(zip(FACES, turns))
    cost = lambda t: sum(min(k, 4 - k) for k in t.values())  # noqa: E731
    return sorted(((t, s) for s, t in found.items()), key=lambda ts: cost(ts[0]))
