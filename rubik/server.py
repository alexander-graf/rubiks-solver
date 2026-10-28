"""HTTP-Schnittstelle. Der Browser hält den aktuellen Zustand, der Server rechnet."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import cube, solver

WEB_DIR = Path(__file__).resolve().parent.parent / "web"

app = FastAPI(title="Rubik's Solver")


class ApplyRequest(BaseModel):
    state: str
    moves: str


class StateRequest(BaseModel):
    state: str


@app.get("/api/meta")
def meta():
    """Geometrie und Farben, damit die 3D-Ansicht dieselben Felder baut wie Python."""
    return {
        "solved": cube.SOLVED,
        "faces": cube.FACES,
        "faceColors": cube.FACE_COLORS,
        "colorNames": cube.COLOR_NAMES,
        "facelets": cube.FACELETS,
        "axes": {
            f: {"normal": n, "right": r, "down": d} for f, (n, r, d) in cube.FACE_AXES.items()
        },
    }


@app.post("/api/apply")
def apply(req: ApplyRequest):
    if len(req.state) != 54:
        raise HTTPException(400, "Zustand muss 54 Felder haben")
    try:
        moves = cube.parse_moves(req.moves)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"moves": moves, "states": cube.apply_moves(req.state, moves)}


@app.get("/api/scramble")
def scramble(length: int = 20):
    return {"moves": cube.random_scramble(max(1, min(length, 100)))}


class SolveRequest(BaseModel):
    state: str
    seconds: float = 0


@app.post("/api/solve")
def solve(req: SolveRequest):
    """Lösung samt Zwischenzuständen, damit der Browser vor und zurück springen kann."""
    try:
        if req.seconds > 0:
            moves = solver.solve_shorter(req.state, min(req.seconds, 60))
        else:
            moves = solver.solve(req.state)
    except solver.SolveError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "steps": [{"move": m, "text": solver.describe(m)} for m in moves],
        "states": cube.apply_moves(req.state, moves),
    }


@app.post("/api/check")
def check(req: StateRequest):
    return {"problems": cube.check(req.state)}


app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
