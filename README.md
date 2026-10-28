# Rubik's Solver

Webcam fotografiert die 6 Seiten eines verdrehten 3×3-Würfels, das Programm erkennt
die Farben, zeigt den Würfel in 3D und führt Zug für Zug durch die Lösung – mit
Pfeilen auf dem Würfel, Animation und deutschem Klartext („Rechte Seite nach oben“).

- **Kamera:** Live-Vorschau mit 3×3-Schablone, Aufnahme per Klick oder Leertaste.
  Wie herum eine Seite fotografiert wird, ist egal – das Programm findet die
  Drehung jedes Fotos selbst (die einzige, die einen lösbaren Würfel ergibt).
- **Farberkennung:** robust bei Zimmerlicht; je Farbe genau 9 Felder, Bezug sind die
  Mittelfelder, Belichtung je Foto wird mitgeschätzt. Unsichere Felder werden markiert.
- **Prüfen:** Netz mit Feldnamen und Fotos zum Vergleich, Korrektur per Klick,
  Lösbarkeit live (unmögliche Ecken/Kanten werden rot markiert).
- **Lösung:** Kociemba-Zwei-Phasen-Algorithmus, meist 18–21 Züge in Millisekunden;
  Schritt- und Abspielmodus, vor und zurück.

## Starten

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m rubik          # öffnet http://127.0.0.1:8765/
.venv/bin/python -m pytest -q      # Tests
```

Getestet mit einer Logitech C270 unter Linux (Python 3.14). Die Kamera wird über
OpenCV/V4L2 als `/dev/video0` angesprochen.

## Aufbau

| Datei | Inhalt |
|---|---|
| `rubik/cube.py` | Würfelmodell, Züge (geometrisch), Lösbarkeitsprüfung, Drehungssuche der Fotos |
| `rubik/solver.py` | Lösung über das Paket `kociemba`, Klartext je Zug |
| `rubik/camera.py` | Webcam im Hintergrund-Thread, Messung der 9 Felder |
| `rubik/colors.py` | Farberkennung (Zuordnung mit genau 9 je Farbe) |
| `rubik/server.py` | FastAPI-Schnittstelle |
| `web/` | Oberfläche im Browser, three.js für die 3D-Ansicht |
