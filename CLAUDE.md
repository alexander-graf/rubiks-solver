# Rubik's Solver

Webcam (Logitech C270, `/dev/video0`) fotografiert die 6 Seiten eines 3×3-Würfels,
das Programm erkennt die Farben, zeigt den Würfel in 3D und berechnet die Lösung
(Kociemba, Klassische Notation, Schritt- und Abspielmodus).

## Starten

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # einmalig
    .venv/bin/python -m rubik            # öffnet http://127.0.0.1:8765/
    .venv/bin/python -m pytest -q

`?moves=R U F2` an der URL führt Züge direkt nach dem Laden aus (zum Testen).

## Aufbau

- `rubik/cube.py` – das Modell. **Einzige Quelle der Zuglogik.** Zustand = 54
  Farbbuchstaben `W Y R O B G` in Kociemba-Reihenfolge U R F D L B, je Seite
  zeilenweise von außen gesehen. Weiß oben, Grün vorn, Rot rechts. Züge werden
  geometrisch gerechnet (Position + Normale je Feld, 90°-Drehung der Schicht).
- `rubik/server.py` – FastAPI; liefert unter `/api/meta` auch die Geometrie,
  damit die 3D-Ansicht dieselben Felder baut.
- `web/` – Browser-Oberfläche, three.js r170 liegt lokal in `web/vendor/`.
  Der Browser animiert nur; nach jedem Zug werden die Steine zurückgesetzt und
  aus dem Zustand vom Server neu gefärbt.

## Entscheidungen (Grilling 2026-10-28)

- 6 Fotos, geführte feste Reihenfolge, Kamera in der Hand, Live-Vorschau mit
  3×3-Schablone, Auslösen per Leertaste, Mittel über ~10 Bilder.
- Licht ist schlecht (Zimmerlicht, nachts), Sticker leicht glänzend; das weiße
  Mittelfeld trägt einen bläulichen Logo-Sticker. Farben daher nicht über feste
  Grenzen, sondern alle 54 Felder so verteilen, dass jede Farbe genau 9× vorkommt;
  Bezugswerte aus den Mittelfeldern (Weiß nur am Rand messen). Aufnahmen speichern
  (`captures/`), um die Erkennung mit echten Fotos nachzujustieren.
- Prüfnetz mit U1–B9 und Farbbuchstaben, Original-Foto daneben, Klick zum Umfärben.

## Meilensteine

1. ✅ Modell, 3D, manuelle Eingabe, Zufallsverdrehung
2. Löser (RubikTwoPhase) mit Schritt-/Abspielmodus, Klartext + Pfeil je Zug
3. Kamera: geführte 6-Foto-Aufnahme, Farberkennung
4. Prüfnetz mit Foto-Vergleich, Lösbarkeitsprüfung (Parität, Ecken-/Kantendrehung)
5. Erkennung mit echten Nachtfotos nachjustieren
