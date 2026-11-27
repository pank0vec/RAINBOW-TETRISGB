# Запуск программы. Читает параметры запуска и выбирает: играть, сохранить кадр или провести
# проверки.

import argparse
import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

from tetris.app import App


# Запуск приложения или встроенных проверок.
def main():
    parser = argparse.ArgumentParser(description="Game Boy Tetris на Python / Pygame")
    parser.add_argument("--data-dir")
    parser.add_argument("--capture")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if args.headless:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    app = App(args.data_dir)
    if args.self_test:
        app.self_test(args.capture)
    elif args.capture:
        app.capture(args.capture)
        app.close()
    else:
        app.run()


if __name__ == "__main__":
    main()
