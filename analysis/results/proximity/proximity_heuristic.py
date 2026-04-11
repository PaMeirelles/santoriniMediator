import sqlite3
import time
import csv
import heapq
from enum import Enum
from typing import Tuple, Set, List
from collections import deque
from tqdm import tqdm

# Assuming the uploaded files are in a 'game' subfolder
from game.board import Board
from database.models import God
from game.constants import NEIGHBOURS
from game.move import (
    Move, ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove,
    HermesMove, MinotaurMove, PanMove, PrometheusMove
)

# --- Configuration ---
DB_PATH = "../../../data/matches.db"
OUTPUT_CSV_PATH = "distance_analysis_fixed.csv"

# --- God to Move Parser Mapping ---
GOD_TO_MOVE_PARSER = {
    God.APOLLO: ApolloMove.from_text, God.ARTEMIS: ArtemisMove.from_text,
    God.ATHENA: AthenaMove.from_text, God.ATLAS: AtlasMove.from_text,
    God.DEMETER: DemeterMove.from_text, God.HEPHAESTUS: HephaestusMove.from_text,
    God.HERMES: HermesMove.from_text, God.MINOTAUR: MinotaurMove.from_text,
    God.PAN: PanMove.from_text, God.PROMETHEUS: PrometheusMove.from_text,
}


# --- Database Interaction ---
def get_conn(db_path=DB_PATH):
    """Establishes a connection to the SQLite database."""
    return sqlite3.connect(db_path)


def load_matches(conn):
    """Loads all match data from the database."""
    print(f"Loading matches from '{DB_PATH}'...")
    cursor = conn.cursor()
    cursor.execute('SELECT Id, Moves, Starting_pos FROM "TB_MATCHES"')
    matches = cursor.fetchall()
    print(f"Loaded {len(matches)} matches for analysis.")
    return matches


# --- Distance Calculation Methods ---

def chebyshev_distance(sq1: int, sq2: int) -> int:
    """Calculates the Chebyshev distance (number of moves on a grid) between two squares."""
    x1, y1 = sq1 % 5, sq1 // 5
    x2, y2 = sq2 % 5, sq2 // 5
    return max(abs(x1 - x2), abs(y1 - y2))


def calculate_naive_metric(board: Board) -> Tuple[int, int]:
    """Calculates a naive distance metric based on Chebyshev distance."""
    g_workers, b_workers = board.workers[:2], board.workers[2:]
    # The -1 adjustment seems arbitrary in the original; it's preserved here
    # but may warrant review depending on the metric's definition.
    min_dist_g = min(max(chebyshev_distance(g, b) for b in b_workers) for g in g_workers) - 1
    min_dist_b = min(max(chebyshev_distance(b, g) for g in g_workers) for b in b_workers) - 1
    return min_dist_g, min_dist_b


# --- Start of new, accurate move generation logic from user's file ---
# This section is assumed correct and is included for completeness.
# board/generation.py
from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Optional
from dataclasses import dataclass, field
class God(Enum):
    APOLLO = 0
    ARTEMIS = 1
    ATHENA = 2
    ATLAS = 3
    DEMETER = 4
    HEPHAESTUS = 5
    HERMES = 6
    MINOTAUR = 7
    PAN = 8
    PROMETHEUS = 9

def text_to_square(square_text):
    row = ord(square_text[0]) - ord('a')
    col = int(square_text[1]) - 1
    square = col * 5 + row
    if square < 0 or square > 24:
        raise Exception(f"Invalid square: {square_text}")
    return square

def square_to_text(square):
    row = chr(square % 5 + ord('a'))
    col = str(square // 5 + 1)
    return row + col

T = TypeVar('T', bound='Move')

@dataclass
class Move(ABC):
    from_sq: int
    had_athena_flag: bool = field(default=False, init=False)
    score: int = field(init=False, default=0)
    god: Optional[God] = field(init=False, default=None)

    @property
    @abstractmethod
    def final_sq(self) -> int:
        pass

    @abstractmethod
    def to_text(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def from_text(cls: Type[T], move_text: str) -> T:
        pass

# --- ApolloMove ---
@dataclass
class ApolloMove(Move):
    to_sq: int
    build_sq: int

    def __post_init__(self):
        self.god = God.APOLLO

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def to_text(self) -> str:
        return square_to_text(self.from_sq) + square_to_text(self.to_sq) + square_to_text(self.build_sq)

    @classmethod
    def from_text(cls, move_text: str) -> "ApolloMove":
        return cls(
            from_sq=text_to_square(move_text[0:2]),
            to_sq=text_to_square(move_text[2:4]),
            build_sq=text_to_square(move_text[4:6]),
        )

# --- ArtemisMove ---
@dataclass
class ArtemisMove(Move):
    to_sq: int
    build_sq: int
    mid_sq: Optional[int] = None

    def __post_init__(self):
        self.god = God.ARTEMIS

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def to_text(self) -> str:
        parts = [square_to_text(self.from_sq)]
        if self.mid_sq is not None:
            parts.append(square_to_text(self.mid_sq))
        parts.append(square_to_text(self.to_sq))
        parts.append(square_to_text(self.build_sq))
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "ArtemisMove":
        if len(move_text) == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
            )
        elif len(move_text) == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                mid_sq=text_to_square(move_text[2:4]),
                to_sq=text_to_square(move_text[4:6]),
                build_sq=text_to_square(move_text[6:8]),
            )
        else:
            raise ValueError("Move text must be 6 or 8 characters long")

# --- HermesMove ---
@dataclass
class HermesMove(Move):
    squares: List[int]
    build_sq: int

    def __post_init__(self):
        self.god = God.HERMES

    @property
    def final_sq(self) -> int:
        return self.squares[-1] if self.squares else self.from_sq

    def to_text(self) -> str:
        return (
            square_to_text(self.from_sq) +
            ''.join(square_to_text(sq) for sq in self.squares) +
            square_to_text(self.build_sq)
        )

    @classmethod
    def from_text(cls, move_text: str) -> "HermesMove":
        if len(move_text) < 4 or len(move_text) % 2 != 0:
            raise ValueError("Hermes move text must be even and at least 4 chars")
        from_sq = text_to_square(move_text[0:2])
        build_sq = text_to_square(move_text[-2:])
        middle = move_text[2:-2]
        squares = [text_to_square(middle[i:i+2]) for i in range(0, len(middle), 2)]
        return cls(from_sq=from_sq, squares=squares, build_sq=build_sq)

# --- DemeterMove ---
@dataclass
class DemeterMove(Move):
    to_sq: int
    build_sq_1: int
    build_sq_2: Optional[int] = None

    def __post_init__(self):
        self.god = God.DEMETER

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq_1),
        ]
        if self.build_sq_2 is not None:
            parts.append(square_to_text(self.build_sq_2))
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "DemeterMove":
        if len(move_text) == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq_1=text_to_square(move_text[4:6]),
            )
        elif len(move_text) == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq_1=text_to_square(move_text[4:6]),
                build_sq_2=text_to_square(move_text[6:8]),
            )
        else:
            raise ValueError("Demeter move text must be 6 or 8 characters")

# --- HephaestusMove ---
@dataclass
class HephaestusMove(DemeterMove):
    def __post_init__(self):
        self.god = God.HEPHAESTUS

# --- PanMove ---
@dataclass
class PanMove(ApolloMove):
    def __post_init__(self):
        self.god = God.PAN

# --- PrometheusMove ---
@dataclass
class PrometheusMove(Move):
    to_sq: int
    build_sq: int
    optional_build: Optional[int] = None

    def __post_init__(self):
        self.god = God.PROMETHEUS

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq),
        ]
        if self.optional_build is not None:
            parts.append(square_to_text(self.optional_build))
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "PrometheusMove":
        if len(move_text) == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
            )
        elif len(move_text) == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
                optional_build=text_to_square(move_text[6:8]),
            )
        else:
            raise ValueError("Prometheus move text must be 6 or 8 characters")

# --- AthenaMove ---
@dataclass
class AthenaMove(ApolloMove):
    def __post_init__(self):
        self.god = God.ATHENA

# --- MinotaurMove ---
@dataclass
class MinotaurMove(ApolloMove):
    pushed: bool = False

    def __post_init__(self):
        self.god = God.MINOTAUR

# --- AtlasMove ---
@dataclass
class AtlasMove(Move):
    to_sq: int
    build_sq: int
    dome: bool
    orig_h: Optional[int] = None

    def __post_init__(self):
        self.god = God.ATLAS

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq),
        ]
        if self.dome:
            parts.append("D")
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "AtlasMove":
        if len(move_text) not in (6, 7):
            raise ValueError("Atlas move must be 6 or 7 characters")
        from_sq = text_to_square(move_text[0:2])
        to_sq = text_to_square(move_text[2:4])
        build_sq = text_to_square(move_text[4:6])
        dome = len(move_text) == 7 and move_text[6] == "D"
        if len(move_text) == 7 and not dome:
            raise ValueError("Atlas 7th char must be 'D' if present.")
        return cls(from_sq=from_sq, to_sq=to_sq, build_sq=build_sq, dome=dome, orig_h=None)


def generate_moves(board: Board) -> List:
    god = board.gods[0] if board.turn == 1 else board.gods[1]
    raw = _DISPATCH[god](board)
    for move in raw:
        move.had_athena_flag = board.prevent_up_next_turn
    return raw


def _apollo(board: Board) -> List[ApolloMove]:
    moves = []
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > board.blocks[from_sq]:
                continue
            occupant = board.which_worker_is_here(to_sq)
            if board.blocks[to_sq] == 4 or (occupant is not None and board.is_ally_worker(occupant)) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            for build_sq in NEIGHBOURS[to_sq]:
                if build_sq == to_sq:
                    continue
                if build_sq == from_sq:
                    if occupant is not None or board.blocks[build_sq] == 4:
                        continue
                elif not board.is_free(build_sq):
                    continue
                moves.append(ApolloMove(from_sq, to_sq, build_sq))
    return moves


def _artemis(board: Board) -> List[ArtemisMove]:
    moves, reached = [], set()
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > board.blocks[from_sq]:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            reached.add((from_sq, to_sq))
            for build_sq in board.get_build_sq(from_sq, to_sq):
                moves.append(ArtemisMove(from_sq, to_sq, build_sq))
            for second_sq in NEIGHBOURS[to_sq]:
                if (board.prevent_up_next_turn and board.blocks[second_sq] > board.blocks[from_sq] or
                        not board.is_free(second_sq) or
                        board.blocks[second_sq] - board.blocks[to_sq] > 1 or
                        second_sq == from_sq or
                        (from_sq, second_sq) in reached):
                    continue
                reached.add((from_sq, second_sq))
                for build_sq in board.get_build_sq(from_sq, second_sq):
                    moves.append(ArtemisMove(from_sq, second_sq, build_sq, mid_sq=to_sq))
    return moves


def _athena(board: Board) -> List[AthenaMove]:
    moves = []
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if not board.is_free(to_sq) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                moves.append(AthenaMove(from_sq, to_sq, build_sq))
    return moves


def _atlas(board: Board) -> List[AtlasMove]:
    moves = []
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > board.blocks[from_sq]:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                h = board.blocks[build_sq]
                moves.append(AtlasMove(from_sq, to_sq, build_sq, False, h))
                if h != 4:
                    moves.append(AtlasMove(from_sq, to_sq, build_sq, True, h))
    return moves


def _demeter(board: Board) -> List[DemeterMove]:
    moves = []
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > board.blocks[from_sq]:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            build_sqs = board.get_build_sq(from_sq, to_sq)
            for i, b1 in enumerate(build_sqs):
                for b2 in build_sqs[i:]:
                    if b1 == b2:
                        moves.append(DemeterMove(from_sq, to_sq, b1))
                    else:
                        moves.append(DemeterMove(from_sq, to_sq, b1, b2))
    return moves


def _hephaestus(board: Board) -> List[HephaestusMove]:
    moves = []
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > board.blocks[from_sq]:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                moves.append(HephaestusMove(from_sq, to_sq, build_sq))
                if board.blocks[build_sq] < 2:
                    moves.append(HephaestusMove(from_sq, to_sq, build_sq, build_sq))
    return moves


def _hermes(board: Board) -> List[HermesMove]:
    moves = []
    for from_sq in board.get_worker_index():
        h = board.blocks[from_sq]
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > h:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - h > 1:
                continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                moves.append(HermesMove(from_sq, [to_sq], build_sq))
        for build_sq in board.get_build_sq(from_sq, from_sq):
            moves.append(HermesMove(from_sq, [], build_sq))
        visited, q = {from_sq}, deque([(from_sq, [])])
        while q:
            cur, path = q.popleft()
            for nei in NEIGHBOURS[cur]:
                if nei in visited or not board.is_free(nei) or board.blocks[nei] != h:
                    continue
                new_path = path + [nei]
                for build_sq in board.get_build_sq(from_sq, nei):
                    moves.append(HermesMove(from_sq, new_path, build_sq))
                q.append((nei, new_path))
                visited.add(nei)
    return moves


def _minotaur(board: Board) -> List[MinotaurMove]:
    moves = []
    for from_sq in board.get_worker_index():
        h = board.blocks[from_sq]
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > h:
                continue
            occupant = board.which_worker_is_here(to_sq)
            if occupant is not None and board.is_ally_worker(occupant):
                continue
            if board.blocks[to_sq] == 4 or board.blocks[to_sq] - h > 1:
                continue
            push_sq = None
            if occupant is not None and board.is_opponent_worker(occupant):
                push_sq = _calculate_push_square(from_sq, to_sq)
                if push_sq is None or not board.is_free(push_sq) or board.blocks[push_sq] == 4:
                    continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                if push_sq is not None and push_sq == build_sq:
                    continue
                moves.append(MinotaurMove(from_sq, to_sq, build_sq, push_sq is not None))
    return moves


def _pan(board: Board) -> List[PanMove]:
    moves = []
    for from_sq in board.get_worker_index():
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > board.blocks[from_sq]:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - board.blocks[from_sq] > 1:
                continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                moves.append(PanMove(from_sq, to_sq, build_sq))
    return moves


def _prometheus(board: Board) -> List[PrometheusMove]:
    moves = []
    for from_sq in board.get_worker_index():
        h = board.blocks[from_sq]
        for to_sq in NEIGHBOURS[from_sq]:
            if board.prevent_up_next_turn and board.blocks[to_sq] > h:
                continue
            if not board.is_free(to_sq) or board.blocks[to_sq] - h > 1:
                continue
            for build_sq in board.get_build_sq(from_sq, to_sq):
                moves.append(PrometheusMove(from_sq, to_sq, build_sq))
        seen = set()
        for opt in board.get_build_sq(from_sq, from_sq):
            if board.blocks[opt] == 4:
                continue
            for to_sq in NEIGHBOURS[from_sq]:
                if not board.is_free(to_sq):
                    continue
                if board.prevent_up_next_turn and board.blocks[to_sq] > h:
                    continue
                if board.blocks[to_sq] + (opt == to_sq) > h:
                    continue
                for build_sq in board.get_build_sq(from_sq, to_sq):
                    key = (from_sq, to_sq, build_sq, opt)
                    if key in seen or (board.blocks[build_sq] == 3 and build_sq == opt):
                        continue
                    seen.add(key)
                    moves.append(PrometheusMove(from_sq, to_sq, build_sq, optional_build=opt))
    return moves


_DISPATCH = {
    God.APOLLO: _apollo,
    God.ARTEMIS: _artemis,
    God.ATHENA: _athena,
    God.ATLAS: _atlas,
    God.DEMETER: _demeter,
    God.HEPHAESTUS: _hephaestus,
    God.HERMES: _hermes,
    God.MINOTAUR: _minotaur,
    God.PAN: _pan,
    God.PROMETHEUS: _prometheus,
}

def generate_moves(board: Board) -> List[Move]:
    """Generates all valid moves for the current player on the board."""
    god = board.gods[0] if board.turn == 1 else board.gods[1]
    if god not in _DISPATCH:  # Fallback for gods without special moves
        god = God.PAN
    return _DISPATCH[god](board)


# --- End of move generation logic ---

def a_star_no_build(board: Board, start_sq: int, goal_sq: int) -> int:
    """A* pathfinding using simple Pan movement rules (move + build is not considered)."""
    # Obstacles are domes and other workers (excluding the goal square)
    obstacles = {sq for sq, b in enumerate(board.blocks) if b == 4}
    for w_sq in board.workers:
        if w_sq != goal_sq:
            obstacles.add(w_sq)

    open_set = [(0, 0, start_sq)]  # (f_cost, g_cost, square)
    g_costs = {start_sq: 0}

    while open_set:
        _, g_cost, current_sq = heapq.heappop(open_set)

        if current_sq == goal_sq:
            return g_cost

        for neighbor in NEIGHBOURS[current_sq]:
            if neighbor in obstacles:
                continue
            # Check if move is valid (not too high)
            if board.blocks[neighbor] - board.blocks[current_sq] > 1:
                continue

            new_g_cost = g_cost + 1
            if neighbor not in g_costs or new_g_cost < g_costs[neighbor]:
                g_costs[neighbor] = new_g_cost
                f_cost = new_g_cost + chebyshev_distance(neighbor, goal_sq)
                heapq.heappush(open_set, (f_cost, new_g_cost, neighbor))

    return float('inf')


def a_star_true_god_rules(initial_board: Board, start_sq: int, goal_sq: int) -> int:
    """
    A* pathfinding that calculates the true distance in turns by searching the
    state space of (worker_position, board_blocks_tuple).
    """
    worker_idx = initial_board.workers.index(start_sq)
    start_blocks = tuple(initial_board.blocks)

    # State: (f_cost, g_cost, current_worker_sq, current_blocks_tuple)
    open_set = [(chebyshev_distance(start_sq, goal_sq), 0, start_sq, start_blocks)]
    # Visited set: (worker_sq, blocks_tuple) -> g_cost
    g_costs = {(start_sq, start_blocks): 0}

    while open_set:
        _, g_cost, current_sq, current_blocks = heapq.heappop(open_set)

        if current_sq == goal_sq:
            return g_cost

        # Create a temporary board representing the current state in the search
        temp_board = Board(initial_board.position_to_text())  # Restore all info
        temp_board.blocks = list(current_blocks)
        temp_board.workers[worker_idx] = current_sq

        # Generate all possible full turns for the current player from this state
        all_possible_moves = generate_moves(temp_board)

        # We are only interested in paths for the worker that started at start_sq
        moves_for_this_worker = [m for m in all_possible_moves if m.from_sq == current_sq]

        for move in moves_for_this_worker:
            # Create a new board state by applying the move
            next_state_board = temp_board.copy()
            next_state_board.make_move(move)  # This updates worker pos and blocks

            new_worker_sq = next_state_board.workers[worker_idx]
            new_blocks_tuple = tuple(next_state_board.blocks)

            state_key = (new_worker_sq, new_blocks_tuple)
            new_g_cost = g_cost + 1

            if state_key not in g_costs or new_g_cost < g_costs[state_key]:
                g_costs[state_key] = new_g_cost
                f_cost = new_g_cost + chebyshev_distance(new_worker_sq, goal_sq)
                heapq.heappush(open_set, (f_cost, new_g_cost, new_worker_sq, new_blocks_tuple))

    return float('inf')


def calculate_path_metric(board: Board, pathfinding_func) -> Tuple[float, float]:
    """Calculates min-distance to farthest opponent using a given A* function."""
    g_workers, b_workers = board.workers[:2], board.workers[2:]

    min_dist_g = float('inf')
    for g in g_workers:
        dist = max(pathfinding_func(board, g, b) for b in b_workers)
        if dist < min_dist_g:
            min_dist_g = dist

    min_dist_b = float('inf')
    for b in b_workers:
        dist = max(pathfinding_func(board, b, g) for g in g_workers)
        if dist < min_dist_b:
            min_dist_b = dist

    return min_dist_g, min_dist_b


def analyze_and_write_state(writer, board: Board, match_id: int, ply_number: int):
    """Analyzes a single board state with all three methods and writes to CSV."""
    # 1. Naive Metric
    start_t = time.perf_counter()
    naive_g, naive_b = calculate_naive_metric(board)
    naive_time = time.perf_counter() - start_t

    # 2. A* with No build
    start_t = time.perf_counter()
    no_build_g, no_build_b = calculate_path_metric(board, a_star_no_build)
    no_build_time = time.perf_counter() - start_t

    # 3. A* with True God Rules
    start_t = time.perf_counter()
    true_g, true_b = calculate_path_metric(board, a_star_true_god_rules)
    true_time = time.perf_counter() - start_t

    writer.writerow([
        match_id, ply_number, 'G',
        naive_g, f"{naive_time:.6f}",
        no_build_g, f"{no_build_time:.6f}",
        true_g, f"{true_time:.6f}",
    ])

    writer.writerow([
        match_id, ply_number, 'B',
        naive_b, f"{naive_time:.6f}",
        no_build_b, f"{no_build_time:.6f}",
        true_b, f"{true_time:.6f}",
    ])


# --- Main Execution ---
if __name__ == "__main__":
    conn = get_conn()
    matches = load_matches(conn)
    conn.close()

    with open(OUTPUT_CSV_PATH, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "match_id", "ply_number", "color"
            "naive_dist", "naive_time_s",
            "a_star_dist", "a_star_time_s",
            "true_god_dist", "true_god_time_s",
        ])

        # Correctly initialize tqdm with the total number of matches
        for match_id, moves_str, start_pos in tqdm(matches, total=len(matches), desc="Analyzing Matches"):
            if not moves_str or not start_pos:
                continue

            board = Board(start_pos)
            # Always analyze the starting position (ply 0)
            analyze_and_write_state(writer, board, match_id, 0)

            move_list = [mv.strip() for mv in moves_str.splitlines() if mv.strip()]

            for i, move_text in enumerate(move_list):
                ply_number = i + 1
                try:
                    current_god = board.gods[0] if board.turn == 1 else board.gods[1]
                    move_parser = GOD_TO_MOVE_PARSER.get(current_god)
                    if not move_parser:
                        # print(f"Warning: No move parser for God {current_god} in match {match_id}. Skipping rest of match.")
                        break

                    move = move_parser(move_text)
                    if board.move_is_valid(move):
                        board.make_move(move)
                        analyze_and_write_state(writer, board, match_id, ply_number)
                    else:
                        # print(f"Warning: Invalid move '{move_text}' in match {match_id} at ply {ply_number}. Skipping rest of match.")
                        break
                except Exception as e:
                    # print(f"Error processing move '{move_text}' in match {match_id} at ply {ply_number}: {e}. Skipping rest of match.")
                    break

    print(f"\nAnalysis complete. Results saved to '{OUTPUT_CSV_PATH}'.")