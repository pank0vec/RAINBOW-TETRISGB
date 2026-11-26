import json
from pathlib import Path
import tempfile
import unittest

from tetris.engine import BASE_SCORES, Game, Menu, Mode, Piece, Progress, format_time
from tetris.storage import Store


class EngineTests(unittest.TestCase):
    def test_seven_bag_has_every_shape(self):
        game = Game(seed=42)
        self.assertEqual({game.active.kind, *list(game.queue)[:6]}, set(range(7)))
        self.assertEqual(set(list(game.queue)[6:13]), set(range(7)))

    def test_horizontal_movement_respects_walls(self):
        game = Game(seed=1)
        for _ in range(20):
            game.move(-1)
        self.assertEqual(min(x for x, _ in game.active.cells()), 0)
        self.assertFalse(game.move(-1))
        for _ in range(20):
            game.move(1)
        self.assertEqual(max(x for x, _ in game.active.cells()), 9)

    def test_rotation_cycle_preserves_cells(self):
        for kind in range(7):
            game = Game(seed=1)
            game.active = Piece(kind, 3, 4)
            original = set(game.active.cells())
            for _ in range(4):
                self.assertTrue(game.rotate(1))
            self.assertEqual(set(game.active.cells()), original)

    def test_rotation_kicks_away_from_wall(self):
        game = Game()
        game.active = Piece(0, -2, 5)
        self.assertTrue(game.valid(game.active))
        self.assertTrue(game.rotate())
        self.assertGreaterEqual(min(x for x, _ in game.active.cells()), 0)

    def test_ghost_matches_hard_drop(self):
        game = Game(seed=3)
        ghost = game.ghost_cells()
        kind = game.active.kind
        distance = game.hard_drop()
        self.assertGreater(distance, 0)
        self.assertTrue(all(game.board[y][x] == kind for x, y in ghost))

    def test_collision_prevents_overlapping_blocks(self):
        game = Game()
        game.active = Piece(6, 3, 5)
        game.board[6][6] = 1
        self.assertFalse(game.move(1))
        self.assertEqual(game.active.x, 3)

    def test_line_clear_collapses_rows_and_keeps_kind(self):
        game = Game()
        for row in (16, 17):
            game.board[row][:9] = [1] * 9
        game.board[10][0] = 3
        game.active = Piece(0, 7, 14)
        game.hard_drop()
        self.assertEqual(game.progress.lines, 2)
        self.assertEqual(game.board[12][0], 3)
        self.assertEqual(game.board[16][9], 0)
        self.assertEqual(game.board[17][9], 0)
        self.assertEqual(game.progress.score, BASE_SCORES[2])

    def test_hold_limited_to_one_per_piece(self):
        game = Game(seed=5)
        first = game.active.kind
        self.assertTrue(game.hold())
        self.assertEqual(game.held, first)
        self.assertFalse(game.hold())
        game.hard_drop()
        self.assertTrue(game.hold())
        self.assertEqual(game.active.kind, first)
        self.assertEqual(game.active.rotation, 0)

    def test_disabled_hold(self):
        self.assertFalse(Game(hold=False).hold())

    def test_pause_freezes_timer_and_board(self):
        game = Game(seed=9)
        game.tick(0.1)
        before = (game.active.y, game.progress.seconds)
        game.pause()
        game.tick(10, True)
        self.assertEqual((game.active.y, game.progress.seconds), before)
        self.assertFalse(game.move(1))
        self.assertFalse(game.rotate())
        game.pause()
        game.tick(0.2)
        self.assertAlmostEqual(game.progress.seconds, 0.3)

    def test_lock_delay_and_no_delay(self):
        game = Game()
        game.active = Piece(6, 3, 15)
        game.tick(0.2)
        self.assertTrue(all(value is None for row in game.board for value in row))
        game.tick(0.31)
        self.assertEqual(sum(value is not None for row in game.board for value in row), 4)
        instant = Game(lock_delay=False)
        instant.active = Piece(6, 3, 15)
        instant.tick(0.01)
        self.assertEqual(sum(value is not None for row in instant.board for value in row), 4)

    def test_top_out_on_spawn(self):
        game = Game()
        game.board[0][4] = 2
        game._spawn(6)
        self.assertEqual(game.state, "lost")

    def test_restart_resets_whole_run(self):
        game = Game(Mode.SPRINT)
        game.hold()
        game.hard_drop()
        game.tick(1)
        game.reset()
        self.assertEqual(game.progress.mode, Mode.SPRINT)
        self.assertEqual(game.progress.lines, 0)
        self.assertEqual(game.progress.seconds, 0)
        self.assertEqual(game.progress.score, 0)
        self.assertIsNone(game.held)
        self.assertFalse(game.hold_used)
        self.assertEqual(game.clear_delay, 0)
        self.assertTrue(all(value is None for row in game.board for value in row))

    def test_combo_bonus_and_reset(self):
        p = Progress()
        self.assertEqual(p.clear(1, 0), 0)
        self.assertEqual(p.clear(2, 0), 50)
        self.assertEqual(p.clear(4, 2), 300)
        self.assertEqual(p.best_combo, 2)
        self.assertEqual(p.score, 40 + 100 + 50 + 1200 * 3 + 300)
        p.clear(0, 2)
        self.assertEqual(p.combo, -1)
        self.assertEqual(p.clear(1, 0), 0)
        self.assertEqual(p.best_combo, 2)

    def test_sprint_finishes_at_or_above_40(self):
        p = Progress(mode=Mode.SPRINT)
        for _ in range(9):
            p.clear(4, 0)
        p.clear(3, 0)
        self.assertFalse(p.won)
        p.clear(4, 0)
        self.assertTrue(p.won)
        self.assertEqual(p.lines, 43)
        score = p.score
        self.assertEqual(p.clear(1, 0), 0)
        self.assertEqual(p.score, score)

    def test_sprint_victory_from_actual_board(self):
        game = Game(Mode.SPRINT)
        game.progress.lines = 36
        for row in range(14, 18):
            game.board[row][:9] = [1] * 9
        game.active = Piece(0, 7, 14)
        game.hard_drop()
        self.assertEqual(game.state, "won")
        self.assertEqual(game.progress.lines, 40)
        game.tick(20)
        self.assertEqual(game.progress.seconds, 0)

    def test_all_challenges(self):
        p = Progress(Mode.CHALLENGES, 0)
        for _ in range(2):
            p.clear(4, 0)
        p.clear(2, 0)
        self.assertTrue(p.won)
        p = Progress(Mode.CHALLENGES, 1)
        p.clear(3, 0)
        self.assertFalse(p.won)
        p.clear(4, 0)
        self.assertTrue(p.won)
        p = Progress(Mode.CHALLENGES, 2)
        p.clear(1, 0)
        p.clear(1, 0)
        p.clear(0, 0)
        for _ in range(3):
            p.clear(1, 0)
        self.assertFalse(p.won)
        p.clear(1, 0)
        self.assertTrue(p.won)

    def test_level_and_time_format(self):
        game = Game()
        game.progress.lines = 10
        self.assertEqual(game.level, 1)
        game.progress.lines = 1000
        self.assertEqual(game.level, 20)
        self.assertEqual(format_time(65.125), "01:05.125")
        self.assertEqual(format_time(3661.025), "61:01.025")

    def test_play_opens_modes_before_game(self):
        menu = Menu()
        self.assertIsNone(menu.confirm())
        self.assertEqual(menu.page, "modes")
        menu.move(1)
        self.assertEqual(menu.mode, Mode.SPRINT)
        self.assertEqual(menu.confirm(), "start")
        self.assertIsNone(menu.back())
        menu.move(1)
        self.assertEqual(menu.confirm(), "settings")
        self.assertEqual(menu.back(), "exit")

    def test_challenge_navigation_wraps(self):
        menu = Menu()
        menu.confirm()
        menu.mode_index = 2
        menu.next_challenge(-1)
        self.assertEqual(menu.challenge, 2)
        menu.next_challenge()
        self.assertEqual(menu.challenge, 0)


class StorageTests(unittest.TestCase):
    def test_round_trip_and_best_records(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            store.settings["colors"] = False
            store.finish(Progress(Mode.SPRINT, seconds=60, score=500, best_combo=4, won=True))
            store.finish(Progress(Mode.SPRINT, seconds=80, score=200, best_combo=2, won=True))
            store.finish(Progress(Mode.CHALLENGES, challenge=2, won=True))
            loaded = Store(folder)
            self.assertEqual(loaded.sprint_best, 60)
            self.assertEqual(loaded.high_score, 500)
            self.assertEqual(loaded.best_combo, 4)
            self.assertEqual(loaded.challenges, [False, False, True])
            self.assertFalse(loaded.settings["colors"])

    def test_unfinished_sprint_never_becomes_record(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(folder)
            store.finish(Progress(Mode.SPRINT, seconds=10, score=100, won=False))
            self.assertIsNone(store.sprint_best)

    def test_corrupt_file_and_invalid_fields(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "save.json"
            file.write_text("not JSON", encoding="utf-8")
            self.assertTrue(Store(folder).settings["colors"])
            file.write_text(json.dumps({"sprint_best": float("nan"), "high_score": -2,
                                        "challenges": [1, 0, 1], "settings": {"palette": 80, "scale": -1, "music": "false"}}))
            store = Store(folder)
            self.assertIsNone(store.sprint_best)
            self.assertEqual(store.high_score, 0)
            self.assertEqual(store.challenges, [False, False, False])
            self.assertEqual(store.settings["palette"], 4)
            self.assertEqual(store.settings["scale"], 2)
            self.assertTrue(store.settings["music"])


if __name__ == "__main__":
    unittest.main()
