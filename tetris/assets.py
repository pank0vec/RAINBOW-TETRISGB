from functools import lru_cache
import json
from pathlib import Path
import sys

import pygame


ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
ASSETS = ROOT / "assets"
PALETTES = (
    ((224, 248, 207), (134, 192, 108), (48, 104, 80), (7, 24, 33)),
    ((200, 201, 67), (125, 133, 39), (0, 106, 0), (4, 62, 0)),
    ((127, 134, 15), (87, 124, 68), (54, 93, 72), (42, 69, 59)),
    ((198, 203, 165), (140, 146, 107), (74, 81, 57), (24, 24, 24)),
    ((129, 161, 126), (98, 124, 96), (60, 75, 59), (22, 28, 22)),
)
PALETTE_NAMES = ("GB STUDIO", "IVAN SKODJE", "DMG", "POCKET", "GAMEBUINO")
PIECE_COLORS = ((67, 215, 245), (255, 170, 65), (94, 134, 255), (255, 97, 132),
                (183, 123, 255), (92, 220, 142), (255, 220, 89))
GOLD = (255, 205, 0)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)


class PixelFont:
    def __init__(self):
        self.glyphs = json.loads((ASSETS / "font.json").read_text(encoding="utf-8"))

    @lru_cache(maxsize=512)
    def render(self, text, scale, color):
        text = text.upper()
        unit = scale * 14
        width = max(1, round(len(text) * 6 * unit))
        surface = pygame.Surface((width, max(1, round(7 * unit))), pygame.SRCALPHA)
        for index, ch in enumerate(text):
            if ch == " ":
                continue
            glyph = self.glyphs.get(ch, self.glyphs["?"])
            for row in range(7):
                for col in range(5):
                    if glyph[row][col] == "1":
                        left = round((index * 6 + col) * unit)
                        top = round(row * unit)
                        right = round((index * 6 + col + 1) * unit)
                        bottom = round((row + 1) * unit)
                        pygame.draw.rect(surface, color, (left, top, max(1, right - left), max(1, bottom - top)))
        return surface

    def draw(self, target, text, x, y, color, scale=0.20):
        image = self.render(str(text), scale, tuple(color))
        target.blit(image, (round(x * 4), round(y * 4)))


class Assets:
    def __init__(self):
        self.images = {
            name: pygame.image.load(ASSETS / f"{name}.png").convert_alpha()
            for name in ("title", "playing", "settings", "blocks")
        }
        self.title = pygame.transform.scale(self._title(), (640, 440))
        self.font = PixelFont()

    def _title(self):
        data = json.loads((ASSETS / "title_colors.json").read_text(encoding="utf-8"))
        size = (data["width"], data["height"])
        return pygame.image.fromstring(bytes.fromhex(data["rgb"]), size, "RGB").convert_alpha()

    @lru_cache(maxsize=1)
    def game_background(self):
        source = self.images["playing"]
        surface = pygame.Surface((153, 144), pygame.SRCALPHA)
        surface.fill(BLACK)
        for y in range(source.get_height()):
            for x in (*range(8, 16), *range(96, 104)):
                color = source.get_at((x, y))
                rgb = (136, 0, 21) if color.r > 200 else (179, 0, 28) if color.r > 100 else tuple(color)[:3]
                surface.set_at((x - 6, y), (*rgb, 255))
        return pygame.transform.scale(surface, (612, 576))

    @lru_cache(maxsize=24)
    def background(self, name, palette):
        surface = self.images[name].copy()
        if palette:
            for y in range(surface.get_height()):
                for x in range(surface.get_width()):
                    color = surface.get_at((x, y))
                    nearest = min(range(4), key=lambda i: sum((color[j] - PALETTES[0][i][j]) ** 2 for j in range(3)))
                    surface.set_at((x, y), (*PALETTES[palette][nearest], color.a))
        return pygame.transform.scale(surface, (surface.get_width() * 4, surface.get_height() * 4))

    @lru_cache(maxsize=48)
    def block(self, kind, colors, palette):
        index = kind if kind <= 5 else 0
        source = self.images["blocks"].subsurface(((index + 2) * 8, 0, 8, 8)).copy()
        for y in range(8):
            for x in range(8):
                c = source.get_at((x, y))
                if colors:
                    border = x in (0, 7) or y in (0, 7)
                    shade = 255 if c.r > 180 else 220 if c.r > 100 else 170 if c.r > 20 else 45 if border else 150
                    rgb = tuple(component * shade // 255 for component in PIECE_COLORS[kind])
                else:
                    nearest = min(range(4), key=lambda i: sum((c[j] - PALETTES[0][i][j]) ** 2 for j in range(3)))
                    rgb = PALETTES[palette][nearest]
                source.set_at((x, y), (*rgb, c.a))
        return pygame.transform.scale(source, (32, 32))


class Audio:
    def __init__(self, settings):
        self.settings = settings
        self.available = pygame.mixer.get_init() is not None
        self.current = None
        self.sounds = {}
        if self.available:
            for path in (ASSETS / "audio" / "sfx").glob("*.wav"):
                try:
                    self.sounds[path.stem] = pygame.mixer.Sound(path)
                except pygame.error:
                    pass
            pygame.mixer.music.set_volume(0.45)

    def play(self, name):
        if self.available and self.settings["sound"] and name in self.sounds:
            self.sounds[name].play()

    def sync(self, scene, paused=False):
        if not self.available:
            return
        if not self.settings["music"]:
            pygame.mixer.music.stop()
            self.current = None
            return
        track = "game" if scene == "playing" else "results" if scene == "results" else "title"
        if track != self.current:
            try:
                pygame.mixer.music.load(ASSETS / "audio" / "music" / f"{track}.wav")
                pygame.mixer.music.play(-1)
                self.current = track
            except pygame.error:
                self.current = None
        if paused:
            pygame.mixer.music.pause()
        else:
            pygame.mixer.music.unpause()
