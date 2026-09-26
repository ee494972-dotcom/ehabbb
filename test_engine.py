import random
import unittest

import engine
from engine import RED, YELLOW


def board_from(moves):
    board, disc = engine.new_board(), RED
    for col in moves:
        board, _ = engine.drop(board, col, disc)
        disc = engine.other(disc)
    return board


class RulesTest(unittest.TestCase):
    def test_discs_stack_from_the_bottom(self):
        board, row = engine.drop(engine.new_board(), 3, RED)
        self.assertEqual(row, engine.ROWS - 1)
        _, row = engine.drop(board, 3, YELLOW)
        self.assertEqual(row, engine.ROWS - 2)

    def test_full_column_rejects_a_drop(self):
        board = board_from([0] * engine.ROWS)
        self.assertIsNone(engine.drop(board, 0, RED))
        self.assertNotIn(0, engine.valid_columns(board))

    def test_every_direction_wins(self):
        cases = {
            "horizontal": [0, 0, 1, 1, 2, 2, 3],
            "vertical": [0, 1, 0, 1, 0, 1, 0],
            "diagonal up": [0, 1, 1, 2, 2, 3, 2, 3, 3, 6, 3],
            "diagonal down": [6, 5, 5, 4, 4, 3, 4, 3, 3, 0, 3],
        }
        for name, moves in cases.items():
            with self.subTest(name):
                board = board_from(moves)
                last_col = moves[-1]
                row = next(r for r in range(engine.ROWS) if board[engine.idx(r, last_col)] != engine.EMPTY)
                self.assertIsNotNone(engine.winning_line(board, engine.idx(row, last_col)))

    def test_three_in_a_row_is_not_a_win(self):
        board = board_from([0, 0, 1, 1, 2])
        self.assertIsNone(engine.winning_line(board, engine.idx(engine.ROWS - 1, 2)))

    def test_there_are_69_winning_lines(self):
        self.assertEqual(len(engine.LINES), 69)


class ComputerTest(unittest.TestCase):
    def test_takes_an_immediate_win(self):
        board = board_from([0, 6, 1, 6, 2])  # yellow to move; red threatens column 3
        board, _ = engine.drop(board, 5, YELLOW)
        for level in engine.LEVELS:
            with self.subTest(level):
                self.assertEqual(engine.best_move(board, RED, level, rng=random.Random(1)), 3)

    def test_blocks_an_immediate_threat(self):
        board = board_from([0, 6, 1, 6, 2])
        for level in ("normal", "hard"):
            with self.subTest(level):
                self.assertEqual(engine.best_move(board, YELLOW, level, rng=random.Random(1)), 3)

    def test_hard_respects_the_time_limit(self):
        import time
        start = time.monotonic()
        col = engine.best_move(engine.new_board(), RED, "hard", time_limit=0.5)
        self.assertLess(time.monotonic() - start, 1.5)
        self.assertIn(col, range(engine.COLS))

    def test_full_board_has_no_move(self):
        self.assertIsNone(engine.best_move("R" * 42, YELLOW))


if __name__ == "__main__":
    unittest.main()
