from typing import Set, Dict, Any, List, Tuple, Iterable
from itertools import combinations_with_replacement
from database.data_compression import starting_position_to_bytes
from sqlalchemy import Engine
from client.controller import Controller
from database.models import God, god_to_string, GameParams, GameResult
from database.postgres.postgres_interface import get_played_matches_pg
from game.constants import ENGINES


def play_game_worker(game_params: GameParams) -> Tuple[GameParams, GameResult]:
    engine_g = game_params.engine_g
    engine_b = game_params.engine_b
    pos = game_params.position_str
    time_g = game_params.time_g
    time_b = game_params.time_b

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



def generate_engine_god_configs(
        engine_pairs: List[Tuple[str, str]],
        god_list: List[God],
        games_per_matchup: int
) -> Iterable[Tuple[str, str, God, God, int]]:
    god_matchups = list(combinations_with_replacement(god_list, 2))

    for e1, e2 in engine_pairs:
        divisor = 2 if e1 == e2 else 4
        num_pos = games_per_matchup // divisor

        for g1, g2 in god_matchups:
            yield e1, e2, g1, g2, num_pos


def build_game_tasks(
        configs: Iterable[Tuple[str, str, God, God, int]],
        positions: List[str],
        starting_time: int
) -> List[dict]:
    tasks = []
    for e1, e2, g1, g2, num_pos in configs:
        for i in range(num_pos):
            pos = positions[i]
            tasks.append({'e_g': e1, 'e_b': e2, 'g_g': g1, 'g_b': g2, 'pos': pos, 'time': starting_time})

            if g1 != g2:
                tasks.append({'e_g': e1, 'e_b': e2, 'g_g': g2, 'g_b': g1, 'pos': pos, 'time': starting_time})

            if e1 != e2:
                tasks.append({'e_g': e2, 'e_b': e1, 'g_g': g1, 'g_b': g2, 'pos': pos, 'time': starting_time})
                if g1 != g2:
                    tasks.append({'e_g': e2, 'e_b': e1, 'g_g': g2, 'g_b': g1, 'pos': pos, 'time': starting_time})
    return tasks

def filter_unplayed_tasks(tasks: List[dict], pg_engine: Engine) -> list[GameParams]:
    played_set = get_played_matches_pg(pg_engine)
    unplayed = []

    print(f"Checking {len(tasks)} tasks against {len(played_set)} existing matches...")

    for task in tasks:
        pos = task['pos']

        key = GameParams(
            pos,
            task['e_g'],
            task['e_b'],
            task['g_g'],
            task['g_b'],
            task['time'],
            task['time']
        )

        if key not in played_set:
            unplayed.append(key)

    return unplayed
