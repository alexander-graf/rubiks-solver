# Rubik's Solver

Webcam (Logitech C270, `/dev/video0`) fotografiert die 6 Seiten eines 3×3-Würfels,
das Programm erkennt die Farben, zeigt den Würfel in 3D und berechnet die Lösung
(Kociemba, Klassische Notation, Schritt- und Abspielmodus).

## Starten

    python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # einmalig
    .venv/bin/python -m rubik            # öffnet http://127.0.0.1:8765/
    .venv/bin/python -m pytest -q

Im Browser gespeicherter Stand (Aufnahmen, Zustand) wird beim Laden wiederhergestellt;
Testlinks mit `?moves=` wirken auf diesen Stand. Headless-Chrome startet ohne Speicher.

Testlinks: `?view=cam` öffnet die Kamera-Ansicht, `?moves=R U F2` führt Züge nach dem Laden aus, `&solve` rechnet danach
die Lösung, `&step=3` springt zu Zug 3, `&speed=100` setzt das Tempo (ms je Vierteldrehung).

Der Server lädt Code **nicht** neu – nach Änderungen an `rubik/` neu starten.

## Aufbau

- `rubik/cube.py` – das Modell. **Einzige Quelle der Zuglogik.** Zustand = 54
  Farbbuchstaben `W Y R O B G` in Kociemba-Reihenfolge U R F D L B, je Seite
  zeilenweise von außen gesehen. Weiß oben, Grün vorn, Rot rechts. Züge werden
  geometrisch gerechnet (Position + Normale je Feld, 90°-Drehung der Schicht).
- `rubik/solver.py` – Paket `kociemba` (C-Erweiterung, < 10 ms, ~19–21 Züge) und der
  deutsche Klartext je Zug. „Kürzere suchen“ startet Versuche mit sinkender Höchstlänge
  in eigenen Prozessen (der C-Aufruf ist nicht abbrechbar). **Nur `forkserver`, nie
  `fork`:** Der Server hat Threads; ein geforktes Kind blieb hängen, erbte den
  Port-Socket und lief nach `kill` des Servers mit 100 % CPU weiter.
- `rubik/camera.py` – Webcam im Hintergrund-Thread (gibt sie nach 20 s ohne Zugriff
  frei), Schablone = zentriertes Quadrat (70 % der kurzen Bildseite), Messung je Feld
  im inneren halben Feld, Median der mittelhellen Pixel; beim weißen Mittelfeld nur
  ein Ring am Rand (Logo). Aufnahme = Median über 10 Bilder. **YUYV 640×480**, nicht
  MJPEG: die C270 meldet bei MJPEG jedes Bild als „Corrupt JPEG data“.
- `cube.piece_problems` – Lösbarkeit auf Ebene der Steine (Ecken/Kanten vorhanden,
  nicht spiegelverkehrt, Verdrehung, Kippung, Parität). **Läuft vor dem Löser**: die
  C-Bibliothek `kociemba` gibt bei manchen unmöglichen Ecken eine „Lösung“ aus, die
  gar nicht löst; `solver.solve` rechnet deshalb jede Lösung nach.
- `cube.orientations` – probiert alle 4⁶ = 4096 Drehungen der 6 Fotos (≈ 0,1 s) und
  behält die lösbaren. Darum ist egal, wie herum fotografiert wird. Mit Alex' erstem
  echten Durchgang (5 von 6 Fotos verdreht) gab es genau einen Treffer.
- `rubik/colors.py` – 54 Messwerte → Farben, je Farbe genau 9 (ungarische Methode),
  Bezug = Mittelfelder, iterativ nachgeführt, **Helligkeit je Foto mitgeschätzt**
  (Belichtungsautomatik!). Ohne das wurden Rot/Orange bei warmem Licht verwechselt.
  „Unsicher“ = andere Farbe liegt < 8 Lab-Einheiten weiter weg. `guess` = grobe
  Farbe über den Farbton, nur für die Live-Warnung „falsche Mitte“.
- `captures/<Sitzung>/` – je Seite `X.jpg` (Ausschnitt) und `X_full.jpg`, dazu
  `samples.json` mit Messwerten und Ergebnis; zum Nachjustieren der Erkennung.
  Nicht im Git.
- `rubik/server.py` – FastAPI; liefert unter `/api/meta` auch die Geometrie,
  damit die 3D-Ansicht dieselben Felder baut.
- `web/` – Browser-Oberfläche, three.js r170 liegt lokal in `web/vendor/`.
  Der Browser animiert nur; nach jedem Zug werden die Steine zurückgesetzt und
  aus dem Zustand vom Server neu gefärbt.

## Testen im Browser ohne Bildschirm

Headless-Chrome mit `--virtual-time-budget` taugt hier nicht: unter virtueller Zeit
laufen `requestAnimationFrame`-Animationen nicht verlässlich (leere oder halb
gedrehte Bilder). Stattdessen echte Zeit über das DevTools-Protokoll (Node-Skript mit
`--remote-debugging-port`, `Page.captureScreenshot`, `Runtime.evaluate` mit
`awaitPromise`) – und Testserver auf einem anderen Port als 8765, dort läuft oft
Alex' eigene Instanz. Die Kamera kann nur **ein** Prozess gleichzeitig nutzen.

## Entscheidungen (Grilling 2026-10-28)

- 6 Fotos per Klick/Leertaste, Live-Vorschau mit 3×3-Schablone, Mittel über 10
  Bilder. Kamera steht inzwischen auf einem Stativ, Alex hält nur den Würfel.
- Die feste Haltung („Weiß oben“) hat in der Praxis nicht funktioniert – ersetzt
  durch die automatische Drehungssuche. Geführt wird nur noch, welche Mitte kommt.
- Licht ist schlecht (Zimmerlicht, nachts), Sticker leicht glänzend; das weiße
  Mittelfeld trägt einen bläulichen Logo-Sticker. Farben daher nicht über feste
  Grenzen, sondern alle 54 Felder so verteilen, dass jede Farbe genau 9× vorkommt;
  Bezugswerte aus den Mittelfeldern (Weiß nur am Rand messen). Aufnahmen speichern
  (`captures/`), um die Erkennung mit echten Fotos nachzujustieren.
- Prüfnetz mit U1–B9 und Farbbuchstaben, Original-Foto daneben, Klick zum Umfärben.

## Meilensteine

1. ✅ Modell, 3D, manuelle Eingabe, Zufallsverdrehung
2. ✅ Löser (kociemba) mit Schritt-/Abspielmodus, Klartext + Pfeil je Zug
3. ✅ Kamera: Live-Vorschau, 6 Fotos per Klick/Leertaste, Farberkennung
4. ✅ Prüfnetz: Fotos im Netz-Layout zum Vergleich, Lösbarkeit live mit betroffenen
   Feldern (rot), Stand überlebt Neuladen (localStorage `rubik-solver-v1`)
5. Erkennung mit echten Nachtfotos nachjustieren
6. Idee (Alex, 2026-10-28): Trainingsmodus mit menschlicher Methode (Anfänger/CFOP,
   v. a. F2L erklären) statt Kociemba – vorher eigene Fragerunde
