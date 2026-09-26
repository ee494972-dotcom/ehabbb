"""Connect Four rules and the computer opponent."""
import math
import random
import time

ROWS, COLS = 6, 7
EMPTY, RED, YELLOW = ".", "R", "Y"
LEVELS = ("easy", "normal", "hard")
WIN_SCORE = 1_000_000
CENTER_FIRST = (3, 2, 4, 1, 5, 0, 6)


def idx(row, col):
    return row * COLS + col


def new_board():
    return EMPTY * (ROWS * COLS)


def other(disc):
    return YELLOW if disc == RED else RED


def valid_columns(board):
    return [col for col in CENTER_FIRST if board[col] == EMPTY]


def drop(board, col, disc):
    """Return (new board, landing row), or None when the column is full."""
    if not 0 <= col < COLS:
        return None
    for row in range(ROWS - 1, -1, -1):
        i = idx(row, col)
        if board[i] == EMPTY:
            return board[:i] + disc + board[i + 1:], row
    return None


def is_full(board):
    return EMPTY not in board[:COLS]


def _build_lines():
    lines = []
    for row in range(ROWS):
        for col in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (-1, 1)):
                if 0 <= row + 3 * dr < ROWS and 0 <= col + 3 * dc < COLS:
                    lines.append(tuple(idx(row + k * dr, col + k * dc) for k in range(4)))
    return tuple(lines)


LINES = _build_lines()
LINES_THROUGH = tuple(tuple(line for line in LINES if i in line) for i in range(ROWS * COLS))
CENTER_CELLS = tuple(idx(row, COLS // 2) for row in range(ROWS))


def winning_line(board, i):
    """Return the four cells through cell i that all hold its disc, if any."""
    disc = board[i]
    if disc == EMPTY:
        return None
    for line in LINES_THROUGH[i]:
        if all(board[j] == disc for j in line):
            return line
    return None


def evaluate(board, disc):
    """Heuristic score from disc's point of view (antisymmetric between sides)."""
    rival = other(disc)
    score = 3 * (sum(board[i] == disc for i in CENTER_CELLS)
                 - sum(board[i] == rival for i in CENTER_CELLS))
    for line in LINES:
        mine = theirs = 0
        for i in line:
            if board[i] == disc:
                mine += 1
            elif board[i] == rival:
                theirs += 1
        if theirs == 0:
            score += 5 if mine == 3 else 2 if mine == 2 else 0
        elif mine == 0:
            score -= 5 if theirs == 3 else 2 if theirs == 2 else 0
    return score


class _OutOfTime(Exception):
    pass


EXACT, LOWER, UPPER = 0, 1, 2


def _negamax(board, disc, depth, alpha, beta, deadline, table):
    if time.monotonic() > deadline:
        raise _OutOfTime
    moves = valid_columns(board)
    if not moves:
        return 0
    if depth == 0:
        return evaluate(board, disc)
    original_alpha = alpha
    entry = table.get(board)
    if entry:
        stored_depth, flag, value, best_col = entry
        if stored_depth >= depth:
            if flag == EXACT:
                return value
            if flag == LOWER:
                alpha = max(alpha, value)
            else:
                beta = min(beta, value)
            if alpha >= beta:
                return value
        moves.remove(best_col)
        moves.insert(0, best_col)
    best, best_col = -math.inf, moves[0]
    for col in moves:
        child, row = drop(board, col, disc)
        if winning_line(child, idx(row, col)):
            # Deeper remaining depth means a quicker win, so it scores higher.
            best, best_col = WIN_SCORE + depth, col
            break
        score = -_negamax(child, other(disc), depth - 1, -beta, -alpha, deadline, table)
        if score > best:
            best, best_col = score, col
        alpha = max(alpha, best)
        if alpha >= beta:
            break
    flag = UPPER if best <= original_alpha else LOWER if best >= beta else EXACT
    table[board] = (depth, flag, best, best_col)
    return best


def best_move(board, disc, level="normal", time_limit=1.5, rng=random):
    """Pick a column for disc. Returns None when the board is full."""
    moves = valid_columns(board)
    if not moves:
        return None
    for col in moves:
        child, row = drop(board, col, disc)
        if winning_line(child, idx(row, col)):
            return col
    if level == "easy":
        rival = other(disc)
        for col in moves:
            child, row = drop(board, col, rival)
            if winning_line(child, idx(row, col)) and rng.random() < 0.5:
                return col
        return rng.choice(moves)

    # Iterative deepening: each finished depth replaces the choice, and a depth
    # cut off by the time limit is discarded, so a legal move is always ready.
    max_depth = 4 if level == "normal" else 16
    deadline = time.monotonic() + time_limit
    table = {}
    order = list(moves)
    choice = order[0]
    for depth in range(1, max_depth + 1):
        try:
            scores, floor = {}, -math.inf
            for col in order:
                child, _ = drop(board, col, disc)
                # Searching just below the best score so far keeps every move
                # that ties the best exact, while worse moves are cut off early.
                scores[col] = -_negamax(child, other(disc), depth - 1, -math.inf, -floor,
                                        deadline, table)
                floor = max(floor, scores[col] - 1)
        except _OutOfTime:
            break
        top = max(scores.values())
        choice = rng.choice([col for col in order if scores[col] == top])
        order.sort(key=lambda col: scores[col], reverse=True)
        if abs(top) >= WIN_SCORE:
            break
    return choice
