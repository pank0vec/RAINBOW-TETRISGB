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
        source = self.images["title"]
        result = source.copy()
        rainbow = ((255, 35, 35), (238, 18, 25), (255, 234, 0), (33, 175, 72), (0, 164, 202), (157, 67, 164))
        for y in range(source.get_height()):
            for x in range(source.get_width()):
                red = source.get_at((x, y)).r
                shade = 0 if red > 200 else 1 if red > 100 else 2 if red > 20 else 3
                if y < 57:
                    target = (GOLD, (205, 157, 0), (104, 83, 0), BLACK)[shade]
                    inside = shade >= 2 and x > 0 and y > 0 and all(
                        source.get_at((nx, ny)).r < 200
                        for nx, ny in ((x - 1, y), (min(x + 1, 159), y), (x, y - 1), (x, y + 1))
                    )
                    if (shade == 1 or inside) and 17 <= y <= 47 and 11 <= x <= 138:
                        stripe = 0 if y < 22 else 1 if y < 29 else 2 if y < 31 else 3 if y < 39 else 4 if y < 44 else 5
                        target = rainbow[stripe]
                    if shade == 3 and (x < 3 or x > 156 or y < 8):
                        target = (25, 26, 22)
                else:
                    target = (WHITE, BLACK, (149, 215, 228) if x >= 104 else (77, 78, 74), (25, 26, 22))[shade]
                    if 118 <= x <= 122 and 64 <= y < 77:
                        target = ((255, 242, 0), BLACK, (77, 78, 74), (24, 24, 24))[shade]
                    if x >= 142 and y >= 80 and shade == 2:
                        target = (38, 175, 72)
                    if x >= 142 and 80 <= y <= 89 and shade in (0, 2):
                        target = GOLD
                    if 58 <= y <= 61 and 8 <= x <= 151:
                        target = ((219, 161, 21), (140, 103, 13), (140, 103, 13), (255, 201, 14))[y - 58]
                    if 58 <= y <= 65:
                        left, right = ((119, 120), (118, 121), (118, 121), (117, 122),
                                       (117, 122), (117, 122), (118, 121), (119, 120))[y - 58]
                        if left <= x <= right:
                            target = (24, 24, 24) if shade == 3 else (145, 137, 0) if y == 64 or (y == 63 and shade == 2) else (255, 242, 0)
                result.set_at((x, y), target)
        return result

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
