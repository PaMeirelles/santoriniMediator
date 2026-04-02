from dataclasses import dataclass
from typing import Tuple, Set, List, Dict, Any

from typing_extensions import LiteralString

from client.controller import Controller
from game.board import God
from game.constants import ENGINES


@dataclass
class GameParams:
    engine_g: str
    engine_b: str
    time_g: int
    time_b: int
    god_g: God
    god_b: God
    position_str: str

@dataclass
class GameResult:
    result: int
    moves: LiteralString


def play_game_worker(game_params: GameParams, ) -> Tuple[GameParams, GameResult]:
    """
    Worker function to run a single game.
    This function is executed by each thread in the pool.
    It does NOT interact with the database.
    """
    engine_g = game_params.engine_g
    engine_b = game_params.engine_b
    pos = game_params.position_str
    time_g = game_params.time_g
    time_b = game_params.time_b

    # The controller runs the game headless
    ctrl = Controller(
        pos, time_g, time_b,
        ENGINES[engine_g],
        ENGINES[engine_b],
        headless=True
    )
    result, moves = ctrl.run_game()

    return game_params, GameResult(result, moves)

def load_official_positions(file_path: str, include_reverse:bool=True) -> List[str]:
    """Loads a list of starting position templates from a file."""
    try:
        with open(file_path, 'r') as f:
            positions = [line.strip() for line in f if line.strip()]
        print(f"Successfully loaded {len(positions)} official starting positions.")
        if include_reverse:
            return positions + [reverse_pos(x) for x in positions]
        else:
            return positions
    except FileNotFoundError:
        print(f"Error: Starting positions file not found at '{file_path}'.")
        return []


def prepare_position_string(template_pos: str, god_g: God, god_b: God) -> str:
    """Injects the correct God IDs into a template position string."""
    god_g_char = str(god_g.value)
    god_b_char = str(god_b.value)
    return template_pos[:51] + god_g_char + god_b_char + template_pos[53:]


def get_played_matches(cursor) -> Set[Tuple[str, str, str, int]]:
    """
    Fetches a set of all previously played match configurations for fast lookups.
    Returns a set of (Starting_pos, Engine_G, Engine_B, Time_B) tuples.
    """
    print("Fetching history of played matches from the database...")
    cursor.execute("SELECT Starting_pos, Engine_G, Engine_B, Time_B FROM TB_MATCHES WHERE Time_G = Time_B ")
    return set(cursor.fetchall())


def load_historical_results(cursor, old_engine: str, new_engine: str, time_control: int) -> List[Dict[str, Any]]:
    """
    Loads detailed results for games already played between the two specified engines.
    """
    query = """
        SELECT Engine_G, Engine_B, God_G, God_B, Result
        FROM TB_MATCHES
        WHERE ((Engine_G = ? AND Engine_B = ?) OR (Engine_G = ? AND Engine_B = ?))
        AND Time_G = ? AND Time_B = ?
    """
    params = (new_engine, old_engine, old_engine, new_engine, time_control, time_control)
    cursor.execute(query, params)

    # Return results as a list of dictionaries for easier access
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def reverse_pos(pos: str) -> str:
    """Swaps the 'G' and 'B' characters in a position string."""
    new_pos = ""
    for c in pos:
        if c == 'B':
            new_pos += 'G'
        elif c == 'G':
            new_pos += 'B'
        else:
            new_pos += c
    return new_pos