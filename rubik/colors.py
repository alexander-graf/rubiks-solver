"""Farberkennung: 54 gemessene Felder auf 6 Farben verteilen, je Farbe genau 9.

Keine festen Farbgrenzen – Zimmerlicht in der Nacht verschiebt alle Farben. Bezug
sind die Mittelfelder (ihre Farbe steht fest). Die Zuordnung „genau 9 je Farbe“
ist ein Zuordnungsproblem (ungarische Methode); danach werden die Bezugsfarben
auf den Mittelwert ihrer 9 Felder gesetzt und neu zugeordnet, bis sich nichts
mehr ändert.
"""

from __future__ import annotations

import colorsys

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment

from .cube import FACE_COLORS, FACES

# Helligkeit zählt weniger als Farbton: Licht und Schatten ändern vor allem L
WEIGHTS = np.array([0.5, 1.0, 1.0])
# Liegt eine andere Farbe näher als das, gilt das Feld als unsicher (Lab-Einheiten)
UNSURE_MARGIN = 8.0


def guess(rgb) -> str:
    """Grobe Farbe eines einzelnen Felds über den Farbton – nur für Warnungen
    („falsche Seite?“), nicht für die eigentliche Erkennung. Grenzen aus echten
    Fotos bei Zimmerlicht: Rot 0–6°, Orange 19–28°, Gelb 51–73°, Grün 154–169°,
    Blau 205–213°, Weiß Sättigung < 0,15."""
    h, s, _ = colorsys.rgb_to_hsv(*(np.asarray(rgb, float) / 255))
    h *= 360
    if s < 0.2:
        return "W"
    if h >= 330 or h < 12:
        return "R"
    if h < 40:
        return "O"
    if h < 110:
        return "Y"
    if h < 185:
        return "G"
    if h < 270:
        return "B"
    return "?"


def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    px = (np.asarray(rgb, np.float32) / 255).reshape(-1, 1, 3)
    return cv2.cvtColor(px, cv2.COLOR_RGB2Lab).reshape(-1, 3)


def classify(samples: dict[str, list]) -> tuple[str, list[int]]:
    """samples: Seite -> 9 RGB-Werte. Liefert Zustand und Indizes unsicherer Felder."""
    rgb = np.concatenate([np.asarray(samples[f], float) for f in FACES])
    face_of = np.repeat(np.arange(6), 9)
    colors = [FACE_COLORS[f] for f in FACES]
    centers = [i * 9 + 4 for i in range(6)]
    # Jedes Foto hat seine eigene Belichtung (Automatik der Kamera). Die Helligkeit je
    # Foto wird mitgeschätzt: nach jeder Zuordnung so nachregeln, dass die Felder eines
    # Fotos im Mittel so hell sind wie ihre Farbe auf allen Fotos.
    gain = np.ones(6)
    lab = rgb_to_lab(rgb)
    refs = lab[centers].copy()

    assign = None
    for _ in range(15):
        dist = np.linalg.norm((lab[:, None, :] - refs[None, :, :]) * WEIGHTS, axis=2)  # (54, 6)
        cost = np.repeat(dist, 9, axis=1)  # Spalte j steht für Farbe j // 9
        for k, i in enumerate(centers):
            cost[i, :] = 1e6
            cost[i, k * 9 : (k + 1) * 9] = 0
        _, cols = linear_sum_assignment(cost)
        new = cols // 9
        if assign is not None and np.array_equal(new, assign):
            break
        assign = new
        scaled = rgb / gain[face_of, None]
        ref_rgb = np.array([scaled[assign == k].mean(axis=0) for k in range(6)])
        ratio = scaled.sum(axis=1) / ref_rgb[assign].sum(axis=1)
        gain *= np.array([np.median(ratio[face_of == f]) for f in range(6)])
        gain /= np.exp(np.log(gain).mean())
        lab = rgb_to_lab(np.clip(rgb / gain[face_of, None], 0, 255))
        refs = np.array([lab[assign == k].mean(axis=0) for k in range(6)])

    unsure = []
    for i in range(54):
        if i in centers:
            continue
        own = dist[i, assign[i]]
        other = np.delete(dist[i], assign[i]).min()
        if other - own < UNSURE_MARGIN:
            unsure.append(i)
    return "".join(colors[k] for k in assign), unsure
