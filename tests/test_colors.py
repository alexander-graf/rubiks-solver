import random

import numpy as np

from rubik.colors import classify
from rubik.cube import FACES, SOLVED, apply_moves, random_scramble

# Ungefähre Kamerawerte bei neutralem Licht
BASE = {
    "W": (200, 200, 200),
    "Y": (200, 190, 40),
    "R": (160, 25, 35),
    "O": (225, 95, 25),
    "B": (25, 60, 165),
    "G": (25, 150, 75),
}


def fake_samples(state, rng, tint=(1.0, 0.85, 0.6), brightness=0.5, noise=5.0):
    """Zimmerlicht nachts: warm, dunkel, verrauscht, jedes Foto etwas anders hell."""
    samples = {}
    for f, face in enumerate(FACES):
        photo = brightness * rng.uniform(0.8, 1.2)
        cells = []
        for c in state[f * 9 : f * 9 + 9]:
            rgb = np.array(BASE[c]) * np.array(tint) * photo + rng.normal(0, noise, 3)
            cells.append(np.clip(rgb, 0, 255).tolist())
        samples[face] = cells
    return samples


def scrambled(seed):
    return apply_moves(SOLVED, random_scramble(25, random.Random(seed)))[-1]


def test_recognizes_scrambles_under_warm_dim_light():
    # Rauschen 2: jeder Messwert ist ein Median über ~1000 Pixel und 10 Bilder.
    # Helligkeit 0.3 entspricht dem ersten Probebild nachts (Mittelwert ~45 von 255).
    rng = np.random.default_rng(1)
    for brightness in (0.3, 0.5):
        for seed in range(40):
            state = scrambled(seed)
            found, _ = classify(fake_samples(state, rng, brightness=brightness, noise=2))
            assert found == state


def test_per_photo_exposure_is_compensated():
    """Rot auf einem hellen Foto vs. Orange auf einem dunklen: ohne Schätzung der
    Helligkeit je Foto wurden hier 17 von 200 Würfeln falsch erkannt."""
    rng = np.random.default_rng(5)
    failures = sum(
        classify(fake_samples(scrambled(seed), rng))[0] != scrambled(seed) for seed in range(200)
    )
    assert failures <= 4


def test_recognizes_under_neutral_and_bluish_light():
    rng = np.random.default_rng(2)
    for tint in [(1, 1, 1), (0.8, 0.9, 1.1)]:
        for seed in range(10):
            state = scrambled(100 + seed)
            assert classify(fake_samples(state, rng, tint=tint, brightness=0.8))[0] == state


def test_each_color_exactly_nine_even_with_heavy_noise():
    rng = np.random.default_rng(3)
    found, unsure = classify(fake_samples(scrambled(7), rng, noise=40))
    assert sorted(found.count(c) for c in "WYROBG") == [9] * 6
    assert unsure  # bei so viel Rauschen muss etwas als unsicher gelten


def test_centers_keep_their_color():
    rng = np.random.default_rng(4)
    found, _ = classify(fake_samples(scrambled(9), rng, noise=40))
    assert [found[i * 9 + 4] for i in range(6)] == list("WRGYOB")
