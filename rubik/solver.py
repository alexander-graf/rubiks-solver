"""Lösung über Kociembas Zwei-Phasen-Algorithmus (Paket `kociemba`, C-Erweiterung)."""

from __future__ import annotations

import multiprocessing as mp
import time

import kociemba

from . import cube


class SolveError(ValueError):
    pass


# Klartext aus Sicht des Haltenden: Weiß oben, Grün vorn.
# Richtung = wohin die zu dir zeigenden Felder der Schicht wandern.
_TEXT = {
    "R": ("Rechte Seite nach oben", "Rechte Seite nach unten"),
    "L": ("Linke Seite nach unten", "Linke Seite nach oben"),
    "U": ("Obere Schicht nach links", "Obere Schicht nach rechts"),
    "D": ("Untere Schicht nach rechts", "Untere Schicht nach links"),
    "F": ("Vorderseite im Uhrzeigersinn", "Vorderseite gegen den Uhrzeigersinn"),
    "B": ("Rückseite: obere Kante nach links", "Rückseite: obere Kante nach rechts"),
}


_LAYER = {
    "R": "Rechte Seite",
    "L": "Linke Seite",
    "U": "Obere Schicht",
    "D": "Untere Schicht",
    "F": "Vorderseite",
    "B": "Rückseite",
}


def describe(move: str) -> str:
    face, suffix = move[0], move[1:]
    if suffix == "2":
        return f"{_LAYER[face]} halb herum (180°, Richtung egal)"
    clockwise, counter = _TEXT[face]
    return counter if suffix == "'" else clockwise


def _kociemba(state: str, max_depth: int = 24) -> list[str]:
    if state == cube.SOLVED:
        return []
    try:
        return kociemba.solve(cube.to_kociemba(state), max_depth=max_depth).split()
    except ValueError as e:
        raise SolveError(
            "Diese Stellung ist nicht lösbar – vermutlich ist eine Farbe falsch "
            "(gedrehte Ecke, gekippte Kante oder zwei vertauschte Steine)."
        ) from e


def solve(state: str) -> list[str]:
    problems = cube.check(state)
    if problems:
        raise SolveError("; ".join(problems))
    return _kociemba(state)


def _worker(state: str, max_depth: int, conn) -> None:
    try:
        conn.send(_kociemba(state, max_depth))
    except SolveError:
        conn.send(None)
    conn.close()


def solve_shorter(state: str, seconds: float) -> list[str]:
    """Erst schnell lösen, dann mit sinkender Höchstlänge weitersuchen, bis die Zeit um
    ist oder keine kürzere Lösung mehr gefunden wird. Jeder Versuch läuft in einem
    eigenen Prozess, weil sich der C-Aufruf nicht abbrechen lässt.

    "forkserver" statt "fork": Der Server läuft mit Threads, und ein geforkter
    Kindprozess kann dort an einer fremden, gesperrten Sperre hängen bleiben."""
    best = solve(state)
    deadline = time.monotonic() + seconds
    ctx = mp.get_context("forkserver")
    while best and time.monotonic() < deadline:
        receiver, sender = ctx.Pipe(duplex=False)
        p = ctx.Process(target=_worker, args=(state, len(best) - 1, sender), daemon=True)
        p.start()
        sender.close()
        found = None
        if receiver.poll(max(0.0, deadline - time.monotonic())):
            try:
                found = receiver.recv()
            except EOFError:
                pass
        receiver.close()
        if p.is_alive():
            p.terminate()
        p.join()
        if not found or len(found) >= len(best):
            break
        best = found
    return best
