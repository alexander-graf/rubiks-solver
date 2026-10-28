"""HTTP-Schnittstelle. Der Browser hält den aktuellen Zustand, der Server rechnet."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import cv2
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import camera as cam
from . import colors, cube, solver

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
CAPTURE_DIR = ROOT / "captures"
CAPTURE_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Rubik's Solver")
camera = cam.Camera()


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
    """Farbverteilung und Lösbarkeit; `cells` sind die Felder betroffener Steine."""
    problems = cube.check(req.state)
    if problems:
        return {"problems": problems, "cells": [], "solvable": False}
    issues = cube.piece_issues(req.state)
    return {
        "problems": [text for text, _ in issues],
        "cells": sorted({i for _, cells in issues for i in cells}),
        "solvable": not issues,
    }


# ---------- Kamera ----------

SESSION_RE = re.compile(r"^[0-9A-Za-z_-]{1,40}$")


def _frame(after: int = 0):
    try:
        return camera.frame(after)
    except cam.CameraError as e:
        raise HTTPException(503, str(e)) from e


@app.get("/api/camera/info")
def camera_info():
    _, frame = _frame()
    h, w = frame.shape[:2]
    return {"width": w, "height": h, "box": cam.box(w, h)}


@app.get("/api/camera/stream")
def camera_stream():
    """MJPEG-Strom für die Vorschau im <img>-Element."""
    seq, _ = _frame()

    def frames():
        nonlocal seq
        while True:
            try:
                seq, frame = camera.frame(after=seq)
            except cam.CameraError:
                return
            ok, jpg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/camera/peek")
def camera_peek(face: str = "F"):
    """Schnelle Messung am aktuellen Bild für die Live-Anzeige."""
    _, frame = _frame()
    cells = cam.sample_cells(frame, white_center=face == "U")
    return {"cells": cells.round().tolist(), "center": colors.guess(cells[4])}


class CaptureRequest(BaseModel):
    face: str
    session: str


@app.post("/api/camera/capture")
def camera_capture(req: CaptureRequest):
    if req.face not in cube.FACES or not SESSION_RE.match(req.session):
        raise HTTPException(400, "Ungültige Seite oder Sitzung")
    try:
        cells, frame = camera.capture(white_center=req.face == "U")
    except cam.CameraError as e:
        raise HTTPException(503, str(e)) from e
    folder = CAPTURE_DIR / req.session
    folder.mkdir(exist_ok=True)
    cv2.imwrite(str(folder / f"{req.face}_full.jpg"), frame)
    h, w = frame.shape[:2]
    x, y, s = cam.box(w, h)
    cv2.imwrite(str(folder / f"{req.face}.jpg"), frame[y : y + s, x : x + s])
    return {
        "cells": cells.round(1).tolist(),
        "center": colors.guess(cells[4]),
        "image": f"/captures/{req.session}/{req.face}.jpg?t={time.time():.0f}",
    }


class RecognizeRequest(BaseModel):
    faces: dict[str, list[list[float]]]
    session: str | None = None


@app.post("/api/recognize")
def recognize(req: RecognizeRequest):
    if sorted(req.faces) != sorted(cube.FACES) or any(len(v) != 9 for v in req.faces.values()):
        raise HTTPException(400, "Es braucht 9 Messwerte für jede der 6 Seiten")
    raw, unsure = colors.classify(req.faces)
    # Wie herum die Fotos gehalten wurden, ist egal: die Drehung je Foto ist die,
    # bei der ein lösbarer Würfel herauskommt.
    found = cube.orientations(raw)
    if found:
        turns, state = found[0]
        problems = []
    else:
        turns, state = dict.fromkeys(cube.FACES, 0), raw
        problems = cube.piece_problems(raw)
    unsure = [
        i // 9 * 9 + cube.rotate_index(i % 9, turns[cube.FACES[i // 9]]) for i in unsure
    ]
    # Messwerte aufheben, um die Erkennung später mit echten Fotos nachzujustieren
    if req.session and SESSION_RE.match(req.session) and (CAPTURE_DIR / req.session).is_dir():
        (CAPTURE_DIR / req.session / "samples.json").write_text(
            json.dumps(
                {"faces": req.faces, "raw": raw, "turns": turns, "state": state,
                 "unsure": unsure, "alternatives": len(found) - 1 if found else 0},
                indent=1,
            )
        )
    return {
        "state": state,
        "unsure": unsure,
        "turns": turns,
        # Mehrere gültige Drehungen sind selten; dann ist die mit den wenigsten gewählt
        "alternatives": len(found) - 1 if found else 0,
        "problems": problems,
    }


app.mount("/captures", StaticFiles(directory=CAPTURE_DIR), name="captures")
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
