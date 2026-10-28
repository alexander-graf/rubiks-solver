"""Start: .venv/bin/python -m rubik [--port 8765] [--no-browser]"""

import argparse
import shutil
import subprocess
import threading
import webbrowser

import uvicorn


def open_browser(url: str) -> None:
    # Chrome schreibt beim Übergeben an ein offenes Fenster harmlose Fehlerzeilen
    # (zygote … broken pipe) ins Terminal; die werden hier verschluckt.
    if xdg := shutil.which("xdg-open"):
        subprocess.Popen([xdg, url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        webbrowser.open(url)


def main():
    p = argparse.ArgumentParser(prog="rubik")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, open_browser, [url]).start()
    print(f"Rubik's Solver läuft auf {url}")
    uvicorn.run("rubik.server:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
