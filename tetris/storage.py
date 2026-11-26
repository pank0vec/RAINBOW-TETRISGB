import json
import math
import os
from pathlib import Path

from .engine import Mode


DEFAULT_SETTINGS = {
    "ghost": True,
    "modern": False,
    "hold": True,
    "sound": True,
    "music": True,
    "lock_delay": True,
    "colors": True,
    "palette": 0,
    "grid": True,
    "border": False,
    "overlay": False,
    "scale": 4,
}


def default_directory():
    override = os.environ.get("TETRIS_PYGAME_DATA")
    if override:
        return Path(override)
    base = Path(os.environ.get("APPDATA", Path.home() / ".local" / "share"))
    return base / "GameboyTetrisPygame"


class Store:
    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else default_directory()
        self.path = self.directory / "save.json"
        self.settings = DEFAULT_SETTINGS.copy()
        self.sprint_best = None
        self.high_score = 0
        self.best_combo = 0
        self.challenges = [False, False, False]
        self.error = ""
        self.load()

    def load(self):
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                return
            values = data.get("settings", {})
            if isinstance(values, dict):
                for key, default in DEFAULT_SETTINGS.items():
                    value = values.get(key, default)
                    if type(default) is bool and type(value) is bool:
                        self.settings[key] = value
                    elif key == "palette" and type(value) is int:
                        self.settings[key] = max(0, min(4, value))
                    elif key == "scale" and type(value) is int:
                        self.settings[key] = max(2, min(8, value))
            for key in ("high_score", "best_combo"):
                value = data.get(key, 0)
                if type(value) is int and value >= 0:
                    setattr(self, key, value)
            best = data.get("sprint_best")
            if type(best) in (int, float) and math.isfinite(best) and best >= 0:
                self.sprint_best = best
            challenges = data.get("challenges")
            if isinstance(challenges, list) and len(challenges) == 3 and all(type(x) is bool for x in challenges):
                self.challenges = challenges
        except (OSError, ValueError, TypeError):
            pass

    def save(self):
        data = {
            "version": 1,
            "settings": self.settings,
            "sprint_best": self.sprint_best,
            "high_score": self.high_score,
            "best_combo": self.best_combo,
            "challenges": self.challenges,
        }
        try:
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(temporary, self.path)
            self.error = ""
            return True
        except OSError as exc:
            self.error = str(exc)
            return False

    def finish(self, progress):
        self.high_score = max(self.high_score, progress.score)
        self.best_combo = max(self.best_combo, progress.best_combo)
        if progress.won and progress.mode == Mode.SPRINT:
            if self.sprint_best is None or progress.seconds < self.sprint_best:
                self.sprint_best = progress.seconds
        if progress.won and progress.mode == Mode.CHALLENGES:
            self.challenges[progress.challenge] = True
        return self.save()
