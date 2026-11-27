# Правила игры. Фигуры, поле, движение, поворот, падение, линии, очки, режимы и модель меню.

from collections import deque
from dataclasses import dataclass
from enum import Enum
import random


# Режимы игры.
class Mode(str, Enum):
    MARATHON = "marathon"
    SPRINT = "sprint40"
    CHALLENGES = "challenges"


# Названия режимов и заданий для экрана.
NAMES = ("МАРАФОН", "СПРИНТ: 40 ЛИНИЙ", "ИСПЫТАНИЯ")
CHALLENGES = ("ОЧИСТИТЬ 10 ЛИНИЙ", "СДЕЛАТЬ ТЕТРИС (4 ЛИНИИ)", "СОБРАТЬ КОМБО X3")
# Форма семи фигур: по четыре клетки у каждой.
SHAPES = (
    ((2, 0), (2, 1), (2, 2), (2, 3)),
    ((1, 0), (1, 1), (1, 2), (2, 2)),
    ((2, 0), (2, 1), (2, 2), (1, 2)),
    ((1, 0), (1, 1), (2, 1), (2, 2)),
    ((2, 0), (2, 1), (1, 1), (2, 2)),
    ((2, 0), (1, 1), (2, 1), (1, 2)),
    ((1, 1), (2, 1), (1, 2), (2, 2)),
)
# Центры поворота фигур.
PIVOTS = ((1.5, 1.5), (1, 1), (2, 1), (2, 1), (2, 1), (2, 1), (1.5, 1.5))
# Скорость падения на разных уровнях.
SPEEDS = (53, 49, 45, 41, 37, 33, 28, 22, 17, 11, 10, 9, 8, 7, 6, 6, 5, 5, 4, 4, 3)
# Базовые очки за очистку от нуля до четырёх линий.
BASE_SCORES = (0, 40, 100, 300, 1200)


# Перевод секунд в надпись с минутами и миллисекундами.
def format_time(seconds):
    milliseconds = max(0, round(seconds * 1000))
    minutes, remainder = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02}:{seconds:02}.{milliseconds:03}"


# Очки, линии, комбо и цель текущей партии.
@dataclass
class Progress:
    mode: Mode = Mode.MARATHON
    challenge: int = 0
    lines: int = 0
    combo: int = -1
    best_combo: int = 0
    tetrises: int = 0
    seconds: float = 0.0
    score: int = 0
    won: bool = False

    # Подсчёт очков, комбо и выполнения цели после очистки.
    def clear(self, count, level):
        if not 0 <= count <= 4:
            raise ValueError("Line count must be between 0 and 4")
        if self.won:
            return 0
        self.combo = self.combo + 1 if count else -1
        self.best_combo = max(self.best_combo, self.combo)
        self.lines += count
        self.tetrises += count == 4
        objectives = (self.lines >= 10, self.tetrises >= 1, self.best_combo >= 3)
        self.won = (self.mode == Mode.SPRINT and self.lines >= 40) or (
            self.mode == Mode.CHALLENGES and objectives[self.challenge]
        )
        bonus = 50 * max(0, self.combo) * (level + 1) if count else 0
        self.score += BASE_SCORES[count] * (level + 1) + bonus
        return bonus

    # Текст текущей цели для экрана.
    @property
    def objective(self):
        if self.mode == Mode.SPRINT:
            return f"{min(self.lines, 40)} / 40 ЛИНИЙ"
        if self.mode == Mode.MARATHON:
            return f"УРОВЕНЬ {self.lines // 10}"
        return (
            f"{min(self.lines, 10)} / 10 ЛИНИЙ",
            f"{self.tetrises} / 1 ТЕТРИС",
            f"{min(self.best_combo, 3)} / 3 КОМБО",
        )[self.challenge]


# Тип, положение и поворот падающей фигуры.
@dataclass
class Piece:
    kind: int
    x: int = 3
    y: int = -1
    rotation: int = 0

    # Координаты четырёх блоков фигуры с учётом поворота.
    def cells(self, dx=0, dy=0, rotation=None):
        turns = self.rotation if rotation is None else rotation
        for x, y in SHAPES[self.kind]:
            if self.kind != 6:
                px, py = PIVOTS[self.kind]
                for _ in range(turns % 4):
                    x, y = px - (y - py), py + (x - px)
            yield round(x) + self.x + dx, round(y) + self.y + dy


# Игровые правила и состояние поля.
class Game:
    width = 10
    height = 18

    # Начальная настройка новой партии.
    def __init__(self, mode=Mode.MARATHON, challenge=0, *, seed=None, lock_delay=True, hold=True):
        self.rng = random.Random(seed)
        self.lock_delay_enabled = lock_delay
        self.hold_enabled = hold
        self.reset(mode, challenge)

    # Очистка поля и результатов для новой игры.
    def reset(self, mode=None, challenge=None):
        previous = getattr(self, "progress", Progress())
        self.progress = Progress(
            Mode(mode) if mode is not None else previous.mode,
            max(0, min(2, challenge if challenge is not None else previous.challenge)),
        )
        self.board = [[None] * self.width for _ in range(self.height)]
        self.queue = deque()
        self.held = None
        self.hold_used = False
        self.state = "playing"
        self.gravity = self.lock_elapsed = self.clear_delay = 0.0
        self.lock_resets = 0
        self.cleared_rows = []
        self.clear_snapshot = None
        self.events = []
        self._fill_queue()
        self._spawn()

    # Подготовка случайной очереди из семёрок фигур.
    def _fill_queue(self):
        while len(self.queue) < 8:
            bag = list(range(7))
            self.rng.shuffle(bag)
            self.queue.extend(bag)

    # Появление новой фигуры и проверка свободного места.
    def _spawn(self, kind=None):
        if kind is None:
            kind = self.queue.popleft()
            self._fill_queue()
        self.active = Piece(kind)
        self.gravity = self.lock_elapsed = 0.0
        self.lock_resets = 0
        if not self.valid(self.active):
            self.state = "lost"
            self.events.append("gameover")

    # Проверка границ поля и столкновений с блоками.
    def valid(self, piece, dx=0, dy=0, rotation=None):
        for x, y in piece.cells(dx, dy, rotation):
            if x < 0 or x >= self.width or y >= self.height or y < -4:
                return False
            if y >= 0 and self.board[y][x] is not None:
                return False
        return True

    # Разрешено ли сейчас управлять фигурой.
    @property
    def controlling(self):
        return self.state == "playing" and self.clear_delay <= 0

    # Текущий уровень скорости по числу очищенных линий.
    @property
    def level(self):
        return min(self.progress.lines // 10, len(SPEEDS) - 1)

    # Сброс задержки закрепления фигуры после движения.
    def _reset_lock(self):
        if self.lock_elapsed > 0 and self.lock_resets < 15:
            self.lock_elapsed = 0.0
            self.lock_resets += 1

    # Движение фигуры влево и вправо.
    def move(self, direction):
        if not self.controlling or not self.valid(self.active, dx=direction):
            return False
        self.active.x += direction
        self._reset_lock()
        self.events.append("move")
        return True

    # Поворот фигуры с проверкой свободного места.
    def rotate(self, direction=1):
        if not self.controlling:
            return False
        rotation = (self.active.rotation + direction) % 4
        for dx, dy in ((0, 0), (-1, 0), (1, 0), (-2, 0), (2, 0), (0, -1), (0, -2)):
            if self.valid(self.active, dx, dy, rotation):
                self.active.x += dx
                self.active.y += dy
                self.active.rotation = rotation
                self._reset_lock()
                self.events.append("rotate")
                return True
        return False

    # Поиск места приземления для тени.
    def ghost_cells(self):
        distance = 0
        while self.valid(self.active, dy=distance + 1):
            distance += 1
        return list(self.active.cells(dy=distance))

    # Мгновенное падение до упора.
    def hard_drop(self):
        if not self.controlling:
            return 0
        distance = 0
        while self.valid(self.active, dy=1):
            self.active.y += 1
            distance += 1
        self.progress.score += distance
        self.lock_piece()
        return distance

    # Обмен фигуры с запасом.
    def hold(self):
        if not self.controlling or not self.hold_enabled or self.hold_used:
            return False
        old = self.active.kind
        self._spawn(self.held)
        self.held = old
        self.hold_used = True
        self.events.append("rotate")
        return True

    # Закрепление фигуры, очистка строк и появление следующей.
    def lock_piece(self):
        if self.state != "playing":
            return
        cells = list(self.active.cells())
        if any(y < 0 for _, y in cells) or not self.valid(self.active):
            self.state = "lost"
            self.events.append("gameover")
            return
        # Перенос блоков фигуры в поле.
        for x, y in cells:
            self.board[y][x] = self.active.kind
        # Поиск и удаление полностью заполненных строк.
        rows = [y for y, row in enumerate(self.board) if all(value is not None for value in row)]
        level = self.level
        self.clear_snapshot = [row[:] for row in self.board] if rows else None
        self.cleared_rows = rows
        if rows:
            remaining = [row[:] for y, row in enumerate(self.board) if y not in rows]
            self.board = [[None] * self.width for _ in rows] + remaining
            self.clear_delay = 0.3
        # Очки, комбо и проверка победы.
        self.progress.clear(len(rows), level)
        self.events.append("tetris" if len(rows) == 4 else "clear" if rows else "land")
        self.hold_used = False
        if self.progress.won:
            self.state = "won"
        else:
            self._spawn()

    # Включение и выключение паузы.
    def pause(self):
        if self.state == "playing":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "playing"

    # Падение, таймер и задержки во время партии.
    def tick(self, seconds, soft_drop=False):
        if self.state != "playing":
            return
        seconds = max(0.0, seconds)
        self.progress.seconds += seconds
        if self.clear_delay > 0:
            self.clear_delay = max(0.0, self.clear_delay - seconds)
            return
        # Расчёт скорости и шаги падения.
        interval = min(SPEEDS[self.level] / 60, 0.05) if soft_drop else SPEEDS[self.level] / 60
        self.gravity += min(seconds, 0.25)
        while self.gravity >= interval:
            self.gravity -= interval
            if self.valid(self.active, dy=1):
                self.active.y += 1
                self.lock_elapsed = 0.0
                if soft_drop:
                    self.progress.score += 1
            else:
                self.gravity = 0.0
                break
        # Задержка закрепления после касания поверхности.
        if not self.valid(self.active, dy=1):
            self.lock_elapsed += seconds
            if self.lock_elapsed >= (0.5 if self.lock_delay_enabled else 0.0):
                self.lock_piece()
        else:
            self.lock_elapsed = 0.0


# Выбор кнопки, режима и задания.
class Menu:
    # Начальные пункты меню.
    def __init__(self):
        self.page = "main"
        self.main_choice = 0
        self.mode_index = 0
        self.challenge = 0

    # Режим, выбранный в меню.
    @property
    def mode(self):
        return tuple(Mode)[self.mode_index]

    # Переключение пунктов меню.
    def move(self, direction):
        if self.page == "main":
            self.main_choice = (self.main_choice + direction) % 2
        else:
            self.mode_index = (self.mode_index + direction) % 3

    # Подтверждение выбранного пункта.
    def confirm(self):
        if self.page == "modes":
            return "start"
        if self.main_choice == 1:
            return "settings"
        self.page = "modes"
        return None

    # Возврат назад или команда выхода.
    def back(self):
        if self.page == "modes":
            self.page = "main"
            return None
        return "exit"

    # Переключение заданий.
    def next_challenge(self, direction=1):
        if self.page == "modes" and self.mode == Mode.CHALLENGES:
            self.challenge = (self.challenge + direction) % 3
