import json
from pathlib import Path
import sys

import pygame

from .assets import ASSETS, Assets, Audio, BLACK, GOLD, PALETTES, PALETTE_NAMES, PIECE_COLORS, WHITE
from .engine import CHALLENGES, NAMES, Game, Menu, Mode, Piece, SHAPES, format_time
from .storage import Store


class App:
    def __init__(self, directory=None):
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.init()
        pygame.display.set_caption("Тетрис — Python / Pygame")
        self.store = Store(directory)
        self.settings = self.store.settings
        self.window_size = (160 * self.settings["scale"], 144 * self.settings["scale"])
        self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        try:
            pygame.display.set_icon(pygame.image.load(ASSETS / "icon.ico"))
        except pygame.error:
            pass
        self.canvas = pygame.Surface((640, 576))
        self.assets = Assets()
        self.audio = Audio(self.settings)
        self.menu = Menu()
        self.game = None
        self.scene = "main"
        self.return_scene = "main"
        self.setting_index = 0
        self.display_index = 0
        self.running = True
        self.fullscreen = False
        self.focused = True
        self.held_keys = set()
        self.repeat_direction = 0
        self.repeat_timer = 0.0
        self.clock = pygame.time.Clock()
        self.joysticks = {}
        self._refresh_joysticks()
        self.audio.sync(self.scene)

    @property
    def palette(self):
        return PALETTES[self.settings["palette"]]

    def box(self, x, y, width, height, color):
        pygame.draw.rect(self.canvas, color, (round(x * 4), round(y * 4), round(width * 4), round(height * 4)))

    def label(self, text, x, y, color=None, scale=0.20):
        self.assets.font.draw(self.canvas, text, x, y, color or self.palette[3], scale)

    def frame(self, x, y, width, height, fill=BLACK, popup=False):
        colors = ((7, 24, 33), (255, 201, 14), (255, 242, 0), fill) if popup else ((255, 201, 14), (255, 174, 1), fill)
        for inset, color in enumerate(colors):
            self.box(x + inset, y + inset, width - inset * 2, height - inset * 2, color)

    def title_label(self, text, y, scale, selected=False):
        width = len(text) * 6 * scale * 3.5
        x = (160 - width) / 2
        self.label(text, x, y, WHITE, scale)
        if selected:
            self.label(">", x - 9, y, WHITE, scale)
        self.box(x, y + 7 * scale * 3.5 + 1, width, 1, GOLD)

    def start(self):
        self.game = Game(self.menu.mode, self.menu.challenge,
                         lock_delay=self.settings["lock_delay"], hold=self.settings["hold"])
        self.scene = "playing"
        self.held_keys.clear()
        self.repeat_direction = 0
        self.audio.sync(self.scene)

    def main_menu(self):
        self.scene = "main"
        self.menu.page = "main"
        self.held_keys.clear()
        self.audio.sync(self.scene)

    def confirm_menu(self):
        command = self.menu.confirm()
        if command == "start":
            self.start()
        elif command == "settings":
            self.scene = "settings"
        else:
            self.scene = self.menu.page
        self.audio.play("menu")

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        else:
            self.window_size = self.screen.get_size()
            self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        self.fullscreen = not self.fullscreen

    def resize_scale(self, direction):
        self.settings["scale"] = max(2, min(8, self.settings["scale"] + direction))
        logical_width = 153 if self.scene in ("playing", "results") else 160
        self.window_size = (logical_width * self.settings["scale"], 144 * self.settings["scale"])
        if not self.fullscreen:
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)

    def change_setting(self, direction=1):
        keys = ("ghost", "modern", "hold", "sound", "music", "lock_delay", "colors")
        key = keys[self.setting_index]
        self.settings[key] = not self.settings[key]
        self.audio.sync(self.scene)
        self.store.save()

    def change_display(self, direction):
        keys = ("palette", "grid", "border", "overlay", "scale")
        key = keys[self.display_index]
        if key == "palette":
            self.settings[key] = (self.settings[key] + direction) % len(PALETTES)
        elif key == "scale":
            self.resize_scale(direction)
        else:
            self.settings[key] = not self.settings[key]
        self.store.save()

    def key(self, key):
        if key == pygame.K_F11:
            self.toggle_fullscreen()
            return
        if key == pygame.K_F2:
            self.settings["colors"] = not self.settings["colors"]
            self.store.save()
            return
        if key in (pygame.K_PAGEUP, pygame.K_PAGEDOWN):
            self.resize_scale(1 if key == pygame.K_PAGEUP else -1)
            self.store.save()
            return
        if key == pygame.K_HOME:
            if self.scene == "display":
                self.scene = self.return_scene
            else:
                self.return_scene = self.scene
                if self.game and self.scene == "playing" and self.game.state == "playing":
                    self.game.pause()
                self.scene = "display"
            return
        if self.scene in ("main", "modes"):
            if key in (pygame.K_UP, pygame.K_w, pygame.K_DOWN, pygame.K_s):
                self.menu.move(-1 if key in (pygame.K_UP, pygame.K_w) else 1)
                self.audio.play("menu")
            elif key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d, pygame.K_TAB):
                self.menu.next_challenge(-1 if key in (pygame.K_LEFT, pygame.K_a) else 1)
                self.audio.play("menu")
            elif key in (pygame.K_RETURN, pygame.K_SPACE):
                self.confirm_menu()
            elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                if self.menu.back() == "exit":
                    self.running = False
                self.scene = self.menu.page
            return
        if self.scene == "settings":
            if key in (pygame.K_UP, pygame.K_DOWN):
                self.setting_index = (self.setting_index + (-1 if key == pygame.K_UP else 1)) % 7
            elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_SPACE):
                self.change_setting()
            elif key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.store.save()
                self.main_menu()
            return
        if self.scene == "display":
            if key in (pygame.K_UP, pygame.K_DOWN):
                self.display_index = (self.display_index + (-1 if key == pygame.K_UP else 1)) % 5
            elif key in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_SPACE):
                self.change_display(-1 if key == pygame.K_LEFT else 1)
            elif key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_BACKSPACE):
                self.store.save()
                self.scene = self.return_scene
            return
        if self.scene == "results":
            if key == pygame.K_r:
                self.start()
            elif key in (pygame.K_RETURN, pygame.K_ESCAPE, pygame.K_SPACE):
                self.main_menu()
            return
        if self.scene != "playing":
            return
        if key == pygame.K_r:
            self.start()
        elif key in (pygame.K_RETURN, pygame.K_p):
            self.game.pause()
        elif key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
            if self.game.state == "paused":
                self.main_menu()
            else:
                self.game.pause()
        elif self.game.state == "playing":
            if key in (pygame.K_LEFT, pygame.K_a, pygame.K_RIGHT, pygame.K_d):
                direction = -1 if key in (pygame.K_LEFT, pygame.K_a) else 1
                self.game.move(direction)
                self.repeat_direction = direction
                self.repeat_timer = 0.15
            elif key == pygame.K_x:
                self.game.rotate(1)
            elif key == pygame.K_z:
                self.game.rotate(-1)
            elif key == pygame.K_c:
                self.game.hold()
            elif key in (pygame.K_UP, pygame.K_w):
                self.game.rotate(-1) if self.settings["modern"] else self.game.hard_drop()
            elif key == pygame.K_SPACE and self.settings["modern"]:
                self.game.hard_drop()

    def destination(self):
        width, height = self.screen.get_size()
        canvas_width, canvas_height = self.canvas.get_size()
        factor = min(width / canvas_width, height / canvas_height)
        size = (max(1, round(canvas_width * factor)), max(1, round(canvas_height * factor)))
        return pygame.Rect((width - size[0]) // 2, (height - size[1]) // 2, *size)

    def click(self, position):
        dest = self.destination()
        if not dest.collidepoint(position):
            return
        x = (position[0] - dest.x) * 160 / dest.width
        y = (position[1] - dest.y) * 144 / dest.height
        if self.scene == "main":
            for i in range(2):
                if pygame.Rect(40, 110 + i * 18, 85, 13).collidepoint(x, y):
                    self.menu.main_choice = i
                    self.confirm_menu()
                    return
        elif self.scene == "modes":
            for i in range(3):
                if pygame.Rect(15, 76 + i * 15, 130, 12).collidepoint(x, y):
                    self.menu.mode_index = i
                    self.confirm_menu()
                    return
            if 120 <= y < 132:
                self.menu.next_challenge()
            elif y >= 132:
                self.menu.back()
                self.scene = "main"
        elif self.scene == "settings":
            if 74 <= y < 130:
                self.setting_index = min(6, int((y - 74) // 8))
                self.change_setting()
            elif 132 <= y < 139:
                self.key(pygame.K_HOME)
            elif y >= 139:
                self.key(pygame.K_RETURN)
        elif self.scene == "display":
            if 76 <= y < 131:
                self.display_index = min(4, int((y - 76) // 11))
                self.change_display(1)
            elif y >= 134:
                self.key(pygame.K_ESCAPE)

    def _refresh_joysticks(self):
        self.joysticks.clear()
        for index in range(pygame.joystick.get_count()):
            joystick = pygame.joystick.Joystick(index)
            joystick.init()
            self.joysticks[joystick.get_instance_id()] = joystick

    def handle_event(self, event):
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN:
            self.held_keys.add(event.key)
            self.key(event.key)
        elif event.type == pygame.KEYUP:
            self.held_keys.discard(event.key)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.click(event.pos)
        elif event.type == pygame.WINDOWFOCUSLOST:
            self.focused = False
            self.held_keys.clear()
            if self.game and self.game.state == "playing":
                self.game.pause()
        elif event.type == pygame.WINDOWFOCUSGAINED:
            self.focused = True
        elif event.type == pygame.VIDEORESIZE and not self.fullscreen:
            self.window_size = (max(320, event.w), max(288, event.h))
            self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        elif event.type in (pygame.JOYDEVICEADDED, pygame.JOYDEVICEREMOVED):
            self._refresh_joysticks()
        elif event.type == pygame.JOYHATMOTION:
            if event.value[1] > 0:
                self.key(pygame.K_UP)
            elif event.value[1] < 0 and self.scene != "playing":
                self.key(pygame.K_DOWN)
            if event.value[0] and self.scene != "playing":
                self.key(pygame.K_RIGHT if event.value[0] > 0 else pygame.K_LEFT)
        elif event.type == pygame.JOYBUTTONDOWN:
            if self.scene == "playing":
                mapping = {0: pygame.K_x, 1: pygame.K_z, 2: pygame.K_c, 3: pygame.K_SPACE,
                           4: pygame.K_c, 5: pygame.K_c, 6: pygame.K_ESCAPE, 7: pygame.K_RETURN}
                if event.button == 3:
                    self.game.hard_drop()
                elif event.button in mapping:
                    self.key(mapping[event.button])
            elif event.button in (0, 7):
                self.key(pygame.K_RETURN)
            elif event.button in (1, 6):
                self.key(pygame.K_ESCAPE)
            elif event.button in (2, 3, 4, 5):
                self.key(pygame.K_TAB)

    def advance(self, seconds):
        if self.scene == "playing" and self.game.state == "playing" and self.focused:
            left = bool(self.held_keys & {pygame.K_LEFT, pygame.K_a})
            right = bool(self.held_keys & {pygame.K_RIGHT, pygame.K_d})
            soft = bool(self.held_keys & {pygame.K_DOWN, pygame.K_s})
            for joystick in self.joysticks.values():
                if joystick.get_numaxes() > 0:
                    axis = joystick.get_axis(0)
                    left |= axis < -0.45
                    right |= axis > 0.45
                if joystick.get_numaxes() > 1:
                    soft |= joystick.get_axis(1) > 0.45
                if joystick.get_numhats():
                    hat = joystick.get_hat(0)
                    left |= hat[0] < 0
                    right |= hat[0] > 0
                    soft |= hat[1] < 0
            direction = int(right) - int(left)
            if direction != self.repeat_direction:
                self.repeat_direction = direction
                self.repeat_timer = 0.0
            if direction:
                self.repeat_timer -= seconds
                for _ in range(5):
                    if self.repeat_timer > 0:
                        break
                    self.game.move(direction)
                    self.repeat_timer += 0.05
            self.game.tick(seconds, soft)
        if self.game:
            for sound in self.game.events:
                self.audio.play(sound)
            self.game.events.clear()
            if self.scene == "playing" and self.game.state in ("won", "lost"):
                self.store.finish(self.game.progress)
                self.scene = "results"
        self.audio.sync(self.scene, self.scene == "playing" and self.game.state == "paused")

    def submenu_header(self, title):
        self.canvas.fill(BLACK)
        self.canvas.blit(self.assets.title, (0, 0))
        self.box(0, 58, 160, 86, BLACK)
        self.title_label(title, 62, 0.19)

    def submenu_row(self, name, value, y, selected, value_x=117, scale=0.18, value_scale=0.17):
        if selected:
            self.box(7, y - 1.5, 146, 7, (35, 29, 8))
            self.box(7, y - 1.5, 1, 7, GOLD)
            self.label(">", 10, y, GOLD, scale)
        self.label(name, 18, y, GOLD if selected else WHITE, scale)
        self.label(value, value_x, y, GOLD if selected else WHITE, value_scale)

    def draw_menu(self):
        if self.scene == "main":
            self.canvas.fill(BLACK)
            self.canvas.blit(self.assets.title, (0, 0))
            self.title_label("ИГРАТЬ", 115, 0.28, self.menu.main_choice == 0)
            self.title_label("НАСТРОЙКИ", 132, 0.28, self.menu.main_choice == 1)
            return
        self.submenu_header("ВЫБЕРИ РЕЖИМ")
        for i, name in enumerate(NAMES):
            selected = i == self.menu.mode_index
            self.label(("> " if selected else "  ") + name, 23, 78 + i * 15,
                       GOLD if selected else WHITE, 0.22)
        if self.menu.mode == Mode.CHALLENGES:
            detail = ("[+] " if self.store.challenges[self.menu.challenge] else "[ ] ") + CHALLENGES[self.menu.challenge]
        elif self.menu.mode == Mode.SPRINT:
            detail = "РЕКОРД: " + (format_time(self.store.sprint_best) if self.store.sprint_best is not None else "НЕТ")
        else:
            detail = f"РЕКОРД: {self.store.high_score} / КОМБО X{self.store.best_combo}"
        self.label(detail, 8, 122, WHITE, 0.15)
        if self.menu.mode == Mode.CHALLENGES:
            self.label("TAB / ВЛЕВО / ВПРАВО: ЗАДАНИЕ", 8, 128, WHITE, 0.12)
        self.label("ENTER: СТАРТ / ESC: НАЗАД", 8, 136, GOLD, 0.14)

    def draw_settings(self):
        if self.scene == "settings":
            self.submenu_header("НАСТРОЙКИ")
            names = ("ТЕНЬ ФИГУРЫ", "НОВОЕ УПРАВЛЕНИЕ", "ЗАПАС ФИГУРЫ", "ЗВУКИ", "МУЗЫКА", "ЗАДЕРЖКА ФИКСАЦИИ", "ЦВЕТНЫЕ ФИГУРЫ")
            keys = ("ghost", "modern", "hold", "sound", "music", "lock_delay", "colors")
            for i, (name, key) in enumerate(zip(names, keys)):
                value = "[ВКЛ]" if self.settings[key] else "[ВЫКЛ]"
                self.submenu_row(name, value, 76 + i * 8, i == self.setting_index)
            self.label("HOME: ОФОРМЛЕНИЕ", 9, 133, WHITE, 0.13)
            self.label("ENTER / ESC: СОХРАНИТЬ И НАЗАД", 9, 140, GOLD, 0.12)
        else:
            self.submenu_header("ОФОРМЛЕНИЕ")
            names = ("ПАЛИТРА", "СЕТКА ПОЛЯ", "РАМКА", "ЭФФЕКТ LCD", "МАСШТАБ")
            values = (PALETTE_NAMES[self.settings["palette"]], "[ВКЛ]" if self.settings["grid"] else "[ВЫКЛ]",
                      "[ВКЛ]" if self.settings["border"] else "[ВЫКЛ]", "[ВКЛ]" if self.settings["overlay"] else "[ВЫКЛ]",
                      f"{self.settings['scale']}X")
            for i, (name, value) in enumerate(zip(names, values)):
                self.submenu_row(name, value, 78 + i * 11, i == self.display_index,
                                 value_x=104, value_scale=0.15)
            self.label("СТРЕЛКИ: ВЫБРАТЬ / ИЗМЕНИТЬ", 9, 134, WHITE, 0.12)
            self.label("ENTER / ESC: НАЗАД", 9, 140, GOLD, 0.12)

    def draw_block(self, kind, x, y, ghost=False):
        if ghost:
            color = PIECE_COLORS[kind] if self.settings["colors"] else self.palette[2]
            pygame.draw.rect(self.canvas, color, (round(x * 4), round(y * 4), 32, 32), 2)
        else:
            image = self.assets.block(kind, self.settings["colors"], self.settings["palette"])
            self.canvas.blit(image, (round(x * 4), round(y * 4)))

    def draw_preview(self, kind):
        cells = SHAPES[kind]
        middle_x = (min(x for x, _ in cells) + max(x for x, _ in cells)) / 2
        middle_y = (min(y for _, y in cells) + max(y for _, y in cells)) / 2
        for x, y in cells:
            self.draw_block(kind, 127 + (x - middle_x) * 8, 117 + (y - middle_y) * 8)

    def draw_game(self):
        game = self.game
        progress = game.progress
        self.canvas.blit(self.assets.game_background(), (0, 0))
        if self.settings["grid"]:
            color = (127, 127, 127)
            for x in range(11):
                pygame.draw.line(self.canvas, color, ((10 + x * 8) * 4, 0), ((10 + x * 8) * 4, 575))
            for y in range(19):
                pygame.draw.line(self.canvas, color, (40, y * 32), (359, y * 32))
        self.box(98, 0, 55, 144, BLACK)
        for rect in ((103, 3, 48, 23), (103, 31, 48, 21), (103, 57, 48, 22), (103, 84, 48, 12), (111, 101, 40, 40)):
            self.frame(*rect)
        board = game.clear_snapshot if game.clear_delay > 0 and game.clear_snapshot else game.board
        for y, row in enumerate(board):
            for x, kind in enumerate(row):
                if kind is not None:
                    self.draw_block(kind, 10 + x * 8, y * 8)
        if game.clear_delay > 0:
            if int(game.clear_delay * 25) % 2:
                for row in game.cleared_rows:
                    self.box(10, row * 8, 80, 8, WHITE)
        elif game.state in ("playing", "paused"):
            if self.settings["ghost"]:
                for x, y in game.ghost_cells():
                    if y >= 0:
                        self.draw_block(game.active.kind, 10 + x * 8, y * 8, True)
            for x, y in game.active.cells():
                if y >= 0:
                    self.draw_block(game.active.kind, 10 + x * 8, y * 8)
        self.label("ОЧКИ", 107, 6, WHITE, scale=0.18)
        self.label(progress.score, 107, 16, WHITE, scale=0.18)
        self.label("ВРЕМЯ", 107, 34, WHITE, scale=0.17)
        self.label(format_time(progress.seconds), 106, 43, WHITE, scale=0.16)
        self.label("ЛИНИИ", 107, 60, WHITE, scale=0.17)
        self.label(str(progress.lines) + ("/40" if progress.mode == Mode.SPRINT else ""), 107, 70, WHITE, scale=0.19)
        self.label(f"КОМБО X{max(0, progress.combo)}", 106, 87, WHITE, scale=0.16)
        self.label("ЗАПАС" if self.settings["hold"] else "ДАЛЕЕ", 114, 104, WHITE, scale=0.16)
        if not self.settings["hold"]:
            self.draw_preview(game.queue[0])
        elif game.held is not None:
            self.draw_preview(game.held)
        if game.state == "paused" or self.scene == "results":
            self.frame(12, 25, 75, 102, fill=WHITE, popup=True)
            ink = (7, 18, 33)
            title = "ПАУЗА" if game.state == "paused" else "ПОБЕДА!" if progress.won else "КОНЕЦ ИГРЫ"
            self.label(title, 18, 34, ink, scale=0.22)
            self.label("ENTER:" if game.state == "paused" else progress.objective, 18, 53, ink, scale=0.15)
            self.label("ПРОДОЛЖИТЬ" if game.state == "paused" else f"КОМБО X{progress.best_combo}", 18, 65, ink, scale=0.17)
            self.label("ESC: МЕНЮ" if game.state == "paused" else "ENTER: МЕНЮ", 18, 86, ink, scale=0.17)
            self.label("R: ЗАНОВО", 18, 103, ink, scale=0.17)
        elif progress.mode == Mode.CHALLENGES:
            self.box(12, 1, 74, 8, BLACK)
            self.label(progress.objective, 14, 2, WHITE, scale=0.16)
        if self.store.error:
            self.label("ОШИБКА СОХРАНЕНИЯ", 12, 137, GOLD, scale=0.13)

    def draw(self):
        size = (612, 576) if self.scene in ("playing", "results") else (640, 576)
        if self.canvas.get_size() != size:
            old_width, old_height = self.canvas.get_size()
            old_window = (round(old_width * self.settings["scale"] / 4), round(old_height * self.settings["scale"] / 4))
            self.canvas = pygame.Surface(size)
            if not self.fullscreen and self.screen.get_size() == old_window:
                self.window_size = (round(size[0] * self.settings["scale"] / 4), round(size[1] * self.settings["scale"] / 4))
                self.screen = pygame.display.set_mode(self.window_size, pygame.RESIZABLE)
        self.canvas.fill(BLACK)
        if self.scene in ("main", "modes"):
            self.draw_menu()
        elif self.scene in ("settings", "display"):
            self.draw_settings()
        else:
            self.draw_game()
        if self.settings["overlay"]:
            overlay = pygame.Surface(self.canvas.get_size(), pygame.SRCALPHA)
            for x in range(0, self.canvas.get_width(), 4):
                pygame.draw.line(overlay, (0, 0, 0, 32), (x, 0), (x, 575))
            for y in range(0, 576, 4):
                pygame.draw.line(overlay, (0, 0, 0, 32), (0, y), (self.canvas.get_width() - 1, y))
            self.canvas.blit(overlay, (0, 0))
        return self.canvas

    def present(self):
        self.screen.fill((15, 15, 15))
        dest = self.destination()
        if self.settings["border"]:
            pygame.draw.rect(self.screen, self.palette[2], dest.inflate(16, 16))
        self.screen.blit(pygame.transform.scale(self.canvas, dest.size), dest)
        pygame.display.flip()

    def capture(self, path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.draw()
        pygame.image.save(self.canvas, path)

    def run(self):
        try:
            while self.running:
                seconds = self.clock.tick(60) / 1000
                for event in pygame.event.get():
                    self.handle_event(event)
                self.advance(seconds)
                self.draw()
                self.present()
        finally:
            self.close()

    def close(self):
        self.store.save()
        pygame.quit()

    def self_test(self, directory=None):
        destination = Path(directory) if directory else self.store.directory / "screenshots"
        destination.mkdir(parents=True, exist_ok=True)
        checks = []

        def check(condition, label):
            if not condition:
                raise AssertionError(label)
            checks.append(label)

        def press(key):
            self.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
            self.handle_event(pygame.event.Event(pygame.KEYUP, key=key))

        try:
            self.capture(destination / "menu.png")
            check(self.audio.available and len(self.audio.sounds) == 7, "Original sound effects loaded")
            press(pygame.K_RETURN)
            check(self.scene == "modes" and self.game is None, "Play opens modes without starting")
            press(pygame.K_DOWN)
            self.capture(destination / "modes.png")
            press(pygame.K_RETURN)
            check(self.scene == "playing" and self.game.progress.mode == Mode.SPRINT, "Keyboard starts selected sprint")
            press(pygame.K_c)
            held = self.game.held
            active = self.game.active.kind
            press(pygame.K_c)
            check(held is not None and self.game.held == held and self.game.active.kind == active, "Hold limited to once per piece")
            self.advance(0.125)
            press(pygame.K_RETURN)
            before = self.game.progress.seconds
            self.advance(2)
            check(self.game.progress.seconds == before, "Paused timer does not advance")
            self.capture(destination / "paused.png")
            press(pygame.K_RETURN)
            self.handle_event(pygame.event.Event(pygame.WINDOWFOCUSLOST))
            self.advance(2)
            check(self.game.state == "paused" and self.game.progress.seconds == before, "Focus loss pauses the run")
            self.handle_event(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
            press(pygame.K_r)
            check(self.game.progress.seconds == 0 and self.game.held is None, "Restart resets timer and hold")
            self.game.board = [[None] * 10 for _ in range(18)]
            for y in range(14, 18):
                for x in range(9):
                    self.game.board[y][x] = 1 + (y - 14)
            self.game.active = Piece(0, 7, 14)
            self.game.progress.lines = 36
            self.game.progress.seconds = 83.456
            self.game.held = 6
            self.capture(destination / "playing.png")
            pixels = self.canvas
            cyan = any(pixels.get_at((x, y)).b > 140 and pixels.get_at((x, y)).g > 130 and pixels.get_at((x, y)).r < 100
                       for x in range(328, 360) for y in range(448, 480))
            check(cyan, "Colour blocks visible in rendered frame")
            press(pygame.K_UP)
            self.advance(0)
            check(self.scene == "results" and self.game.progress.won and self.game.progress.lines == 40, "Actual board clear completes sprint")
            check(self.store.sprint_best is not None and self.store.sprint_best <= 83.456, "Sprint record saved")
            self.capture(destination / "victory.png")
            press(pygame.K_RETURN)
            self.menu.main_choice = 1
            press(pygame.K_RETURN)
            self.capture(destination / "settings.png")
            check(self.scene == "settings", "Settings open independently")
            original = self.settings["ghost"]
            press(pygame.K_RIGHT)
            check(self.settings["ghost"] != original, "Settings toggle through input events")
            dest = self.destination()
            self.click((dest.x + round(80 / 160 * dest.width), dest.y + round(78 / 144 * dest.height)))
            check(self.setting_index == 0 and self.settings["ghost"] == original, "Mouse matches restyled settings rows")
            press(pygame.K_RETURN)
            self.menu.main_choice = 0
            press(pygame.K_RETURN)
            self.menu.mode_index = 2
            self.menu.challenge = 0
            press(pygame.K_TAB)
            self.capture(destination / "challenges.png")
            press(pygame.K_RETURN)
            check(self.game.progress.mode == Mode.CHALLENGES and self.game.progress.challenge == 1, "Selected challenge reaches engine")
            press(pygame.K_HOME)
            self.capture(destination / "display.png")
            check(self.scene == "display" and self.game.state == "paused", "Display menu pauses gameplay")
            old_palette = self.settings["palette"]
            dest = self.destination()
            self.click((dest.x + round(80 / 160 * dest.width), dest.y + round(80 / 144 * dest.height)))
            check(self.display_index == 0 and self.settings["palette"] != old_palette, "Mouse matches restyled display rows")
            press(pygame.K_ESCAPE)
            press(pygame.K_RETURN)
            check(self.game.state == "playing", "Gameplay resumes after display menu")
            self.main_menu()
            dest = self.destination()
            point = (dest.x + round(80 / 160 * dest.width), dest.y + round(115 / 144 * dest.height))
            self.click(point)
            check(self.scene == "modes", "Mouse activates Play button")
            reloaded = Store(self.store.directory)
            check(reloaded.sprint_best == self.store.sprint_best, "Saved data survives reload")
            report = {"passed": len(checks), "checks": checks, "pygame": pygame.version.ver, "screenshots": str(destination)}
            (destination / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            if sys.stdout is not None:
                print(f"PASS: {len(checks)} Pygame integration checks", flush=True)
        finally:
            self.close()
