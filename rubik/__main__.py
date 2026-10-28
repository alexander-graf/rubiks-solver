"""Start: .venv/bin/python -m rubik [--port 8765] [--no-browser]"""

import argparse
import threading
import webbrowser

import uvicorn


def main():
    p = argparse.ArgumentParser(prog="rubik")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    args = p.parse_args()

    url = f"http://127.0.0.1:{args.port}/"
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, [url]).start()
    print(f"Rubik's Solver läuft auf {url}")
    uvicorn.run("rubik.server:app", host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
