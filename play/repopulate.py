import random
import time
from itertools import combinations
from typing import List, Dict

from game.board import God
from analysis.database import get_conn, store_match
from game.constants import ENGINES
from client.controller import Controller
# --- Configuration ---
ENGINE_PAIRS = [("Paladini_4.1.1_Mystic", "Paladini_4.1.1_Mystic")]
POSITIONS_FILE_PATH = "../data/official_starting_pos.txt"
GAMES_PER_MATCHUP = 6


# --- Helper Functions (Existing and New) ---
def load_official_positions(file_path: str) -> List[str]:
    """Loads a list of starting position templates from a file."""
    try:
        with open(file_path, 'r') as f:
            positions = [line.strip() for line in f if line.strip()]
        print(f"Successfully loaded {len(positions)} official starting positions.")
        return positions
    except FileNotFoundError:
        print(f"Error: Starting positions file not found at '{file_path}'.")
        return []


def prepare_position_string(template_pos: str, god_g: God, god_b: God) -> str:
    """Injects the correct God IDs into a template position string."""
    god_g_char = str(god_g.value)
    god_b_char = str(god_b.value)
    return template_pos[:51] + god_g_char + god_b_char + template_pos[53:]


def check_if_played(cursor, pos: str, engine_g: str, engine_b: str, time_control:int) -> bool:
    """
    Checks if a specific position has already been played for this engine matchup.
    """

    cursor.execute("""
        SELECT COUNT(*) FROM TB_MATCHES
        WHERE Starting_pos = ?
          AND Engine_G = ? AND Engine_B = ? 
          AND Time_G = Time_B 
          AND Time_B = ?
    """, (pos, engine_g, engine_b, time_control))
    return cursor.fetchone()[0] > 0


# --- Main Repopulation Logic (Modified) ---
def run_single_match(cursor, engine_g: str, engine_b: str, god_g: God, god_b: God, starting_time: int, pos: str):
    """
    Runs one match for a specific engine/god pairing and stores it,
    after checking if it has been played.
    """
    # 1. Check if this exact position has been played for this engine matchup
    if check_if_played(cursor, pos, engine_g, engine_b, starting_time):
        print(f"  - SKIPPING (already played): {engine_g} vs {engine_b}, pos: ...{pos}")
        return

    print(f"  - Playing {engine_g} ({god_g.name}) vs {engine_b} ({god_b.name}) using pos: ...{pos}")

    ctrl = Controller(
        pos, starting_time, starting_time,
        ENGINES[engine_g],
        ENGINES[engine_b],
        headless=True
    )
    result, moves = ctrl.run_game()
    store_match(
        cursor.connection,  # Pass the connection object for committing
        god_g, god_b, engine_g, engine_b,
        result, starting_time, moves, pos
    )


def repopulate_database(starting_time: int = 60):
    """
    Builds a randomized list of games to play between engines using
    a predefined list of starting positions, and then executes them.
    """
    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    conn = get_conn()
    cursor = conn.cursor()

    god_matchups = list(combinations(God, 2))
    games_to_schedule: List[Dict] = []

    # --- Phase 1: Build a list of all games to be played ---
    print("\n--- Scheduling games based on database history ---")
    for prev_engine, current_engine in ENGINE_PAIRS:
        print(f"\nScheduling for: {current_engine} vs {prev_engine}")
        for god1, god2 in god_matchups:
            # Each iteration schedules a symmetric block of 2 or 4 games
            for i in range(GAMES_PER_MATCHUP // 4 if prev_engine != current_engine else GAMES_PER_MATCHUP // 2):
                template_pos = official_positions[i]

                # Prepare the two symmetric positions
                pos_g1_b2 = prepare_position_string(template_pos, god1, god2)
                pos_g2_b1 = prepare_position_string(template_pos, god2, god1)

                # Add games to the schedule list as dictionaries
                games_to_schedule.append(
                    {'engine_g': current_engine, 'engine_b': prev_engine, 'god_g': god1, 'god_b': god2,
                     'pos': pos_g1_b2})
                games_to_schedule.append(
                    {'engine_g': current_engine, 'engine_b': prev_engine, 'god_g': god2, 'god_b': god1,
                     'pos': pos_g2_b1})
                if prev_engine != current_engine:
                    games_to_schedule.append(
                        {'engine_g': prev_engine, 'engine_b': current_engine, 'god_g': god1, 'god_b': god2,
                         'pos': pos_g1_b2})
                    games_to_schedule.append(
                        {'engine_g': prev_engine, 'engine_b': current_engine, 'god_g': god2, 'god_b': god1,
                         'pos': pos_g2_b1})

    # --- Phase 2: Shuffle the list to randomize play order ---
    print(f"\n--- Total games to schedule: {len(games_to_schedule)} ---")
    if not games_to_schedule:
        print("No new games to play. Database is up to date.")
        conn.close()
        return

    # print("Shuffling game order...")
    # random.shuffle(games_to_schedule)

    # --- Phase 3: Execute the shuffled games ---
    total_games = len(games_to_schedule)
    for i, game_params in enumerate(games_to_schedule):
        print(f"\n--- Playing Game {i + 1} of {total_games} (Randomized Order) ---")
        # The 'starting_time' is passed here
        run_single_match(cursor, **game_params, starting_time=starting_time)
        # Commit after each game to save progress incrementally
        conn.commit()

    print("\nDatabase repopulation complete.")
    conn.close()


if __name__ == "__main__":
    repopulate_database()