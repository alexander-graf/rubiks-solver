"""Webcam und Messung der 9 Felder einer Seite.

Ein Hintergrund-Thread liest laufend Bilder; Vorschau, Live-Messung und Aufnahme
nehmen sich jeweils das neueste. Ohne Zugriff gibt der Thread die Kamera nach
`idle_seconds` wieder frei.

YUYV statt MJPEG: Die C270 liefert im MJPEG-Modus bei jedem Bild „Corrupt JPEG
data“, und 640×480 reicht für 9 Felder.
"""

from __future__ import annotations

import threading
import time

import cv2
import numpy as np

# Kantenlänge der quadratischen Schablone relativ zur kürzeren Bildseite
BOX_FRACTION = 0.7
# Gemessen wird nur das Innere jedes Felds, damit die schwarzen Ränder nicht stören
INNER = 0.5
# Beim weißen Mittelfeld klebt ein Logo. Dort zählt nur das hellste Drittel der Pixel
# (das Logo ist dunkler als Weiß). Ein Ring am Rand des Felds traf bei nicht ganz
# ausgefülltem Quadrat den schwarzen Rand – die orange Mitte wurde so dunkelrot.
WHITE_CENTER = 0.7


class CameraError(RuntimeError):
    pass


def box(width: int, height: int) -> tuple[int, int, int]:
    """(x, y, Kantenlänge) der Schablone im Bild."""
    size = int(min(width, height) * BOX_FRACTION)
    return (width - size) // 2, (height - size) // 2, size


def _robust_color(pixels: np.ndarray) -> np.ndarray:
    """Median der mittelhellen Pixel: verwirft Spiegelungen (hellste) und
    Schatten/Ränder (dunkelste)."""
    v = pixels.max(axis=1)
    lo, hi = np.percentile(v, [15, 85])
    keep = pixels[(v >= lo) & (v <= hi)]
    if len(keep) == 0:
        keep = pixels
    return np.median(keep, axis=0)


def sample_cells(frame: np.ndarray, white_center: bool = False) -> np.ndarray:
    """9 RGB-Werte (zeilenweise) aus dem BGR-Bild."""
    h, w = frame.shape[:2]
    x0, y0, size = box(w, h)
    cell = size / 3
    out = np.zeros((9, 3))
    for i in range(9):
        r, c = divmod(i, 3)
        cx = x0 + (c + 0.5) * cell
        cy = y0 + (r + 0.5) * cell
        half = int(cell * (WHITE_CENTER if white_center and i == 4 else INNER) / 2)
        pixels = frame[int(cy) - half : int(cy) + half, int(cx) - half : int(cx) + half].reshape(-1, 3)
        pixels = pixels.astype(float)
        if white_center and i == 4:
            v = pixels.max(axis=1)
            out[i] = np.median(pixels[v >= np.percentile(v, 67)], axis=0)[::-1]
        else:
            out[i] = _robust_color(pixels)[::-1]  # BGR -> RGB
    return out


class Camera:
    def __init__(self, index: int = 0, width: int = 640, height: int = 480, idle_seconds: float = 20):
        self.index, self.width, self.height = index, width, height
        self.idle_seconds = idle_seconds
        self._cond = threading.Condition()
        self._frame: np.ndarray | None = None
        self._seq = 0
        self._thread: threading.Thread | None = None
        self._last_use = 0.0
        self._error: str | None = None

    def _run(self) -> None:
        cap = cv2.VideoCapture(self.index, cv2.CAP_V4L2)
        try:
            if not cap.isOpened():
                self._error = f"Kamera /dev/video{self.index} lässt sich nicht öffnen (belegt?)"
                return
            cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"YUYV"))
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            failures = 0
            while time.monotonic() - self._last_use < self.idle_seconds:
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures > 20:
                        self._error = "Kamera liefert keine Bilder"
                        return
                    time.sleep(0.05)
                    continue
                failures = 0
                with self._cond:
                    self._frame = frame
                    self._seq += 1
                    self._error = None
                    self._cond.notify_all()
        finally:
            cap.release()
            with self._cond:
                self._frame = None
                if self._thread is threading.current_thread():
                    self._thread = None
                self._cond.notify_all()

    def frame(self, after: int = 0, timeout: float = 4.0) -> tuple[int, np.ndarray]:
        """Neuestes Bild mit laufender Nummer > `after`."""
        with self._cond:
            self._last_use = time.monotonic()
            if self._thread is None:
                self._error = None
                self._thread = threading.Thread(target=self._run, name="camera", daemon=True)
                self._thread.start()
            ok = self._cond.wait_for(
                lambda: (self._frame is not None and self._seq > after) or self._error is not None,
                timeout,
            )
            if self._error:
                raise CameraError(self._error)
            if not ok:
                raise CameraError("Keine Bilder von der Kamera")
            return self._seq, self._frame

    def capture(self, frames: int = 10, white_center: bool = False) -> tuple[np.ndarray, np.ndarray]:
        """Misst über mehrere Bilder (Median je Feld gegen Rauschen und Wackeln) und
        gibt die Messung samt letztem Bild zurück."""
        seq, frame = self.frame()
        samples = [sample_cells(frame, white_center)]
        for _ in range(frames - 1):
            seq, frame = self.frame(after=seq)
            samples.append(sample_cells(frame, white_center))
        return np.median(samples, axis=0), frame
