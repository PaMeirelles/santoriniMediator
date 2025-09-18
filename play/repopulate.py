import random
import time
from itertools import combinations
from typing import List, Dict

from game.board import God
from analysis.database import get_conn, store_match
from game.constants import ENGINES
from client.controller import Controller
# --- Configuration ---
ENGINE_PAIRS = [("Paladini_7.1_Spirit", "Paladini_6.5.2_Prince")]
POSITIONS_FILE_PATH = "../data/official_starting_pos.txt"
GAMES_PER_MATCHUP = 4


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

def reverse_pos(pos:str) -> str:
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

def repopulate_database(starting_time: int = 60):
    """
    Builds a randomized list of games to play between engines using
    a predefined list of starting positions, and then executes them.
    """
    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    official_positions = official_positions + [reverse_pos(x) for x in official_positions]

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


# --- NEW FUNCTION ---
def play_matches_with_specific_gods(
    god_list: List[God],
    engine1: str,
    engine2: str,
    starting_time: int = 60
):
    """
    Plays matches between two engines where at least one of the specified gods is present.

    Args:
        god_list: A list of God objects to focus on.
        engine1: The name of the first engine.
        engine2: The name of the second engine.
        starting_time: The time control for the games.
    """
    # 1. Initial Setup
    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    official_positions += [reverse_pos(x) for x in official_positions]
    conn = get_conn()
    cursor = conn.cursor()

    # 2. Generate Filtered God Matchups
    all_god_matchups = list(combinations(God, 2))
    filtered_god_matchups = [
        matchup for matchup in all_god_matchups
        if matchup[0] in god_list or matchup[1] in god_list
    ]

    if not filtered_god_matchups:
        print(f"No valid god matchups found for the provided list: {[god.name for god in god_list]}")
        conn.close()
        return

    print(f"\nFound {len(filtered_god_matchups)} god matchups involving specified gods.")
    games_to_schedule: List[Dict] = []

    # 3. Build the schedule of games to play
    print(f"\n--- Scheduling games for {engine1} vs {engine2} ---")
    for god1, god2 in filtered_god_matchups:
        num_games_per_pairing = GAMES_PER_MATCHUP // 4 if engine1 != engine2 else GAMES_PER_MATCHUP // 2
        for i in range(num_games_per_pairing):
            template_pos = official_positions[i]

            pos_g1_b2 = prepare_position_string(template_pos, god1, god2)
            pos_g2_b1 = prepare_position_string(template_pos, god2, god1)

            # Schedule engine1 vs engine2
            games_to_schedule.append(
                {'engine_g': engine1, 'engine_b': engine2, 'god_g': god1, 'god_b': god2, 'pos': pos_g1_b2}
            )
            games_to_schedule.append(
                {'engine_g': engine1, 'engine_b': engine2, 'god_g': god2, 'god_b': god1, 'pos': pos_g2_b1}
            )

            # If engines are different, schedule the reverse pairing
            if engine1 != engine2:
                games_to_schedule.append(
                    {'engine_g': engine2, 'engine_b': engine1, 'god_g': god1, 'god_b': god2, 'pos': pos_g1_b2}
                )
                games_to_schedule.append(
                    {'engine_g': engine2, 'engine_b': engine1, 'god_g': god2, 'god_b': god1, 'pos': pos_g2_b1}
                )

    # 4. Execute the games
    print(f"\n--- Total games to schedule: {len(games_to_schedule)} ---")
    if not games_to_schedule:
        print("No new games to play. Database may be up to date for this set.")
        conn.close()
        return

    total_games = len(games_to_schedule)
    for i, game_params in enumerate(games_to_schedule):
        print(f"\n--- Playing Game {i + 1} of {total_games} ---")
        run_single_match(cursor, **game_params, starting_time=starting_time)
        conn.commit()

    print(f"\nMatch series complete for engines {engine1} and {engine2} with specified gods.")
    conn.close()


if __name__ == "__main__":
    # --- Option 1: Run the original full repopulation ---
    repopulate_database(60)

    # # --- Option 2: Run matches with a specific list of gods ---
    # # Define the engines to test
    # engine_a = "Paladini_5.5.40_Velocity"
    # engine_b = "Paladini_6.5.2_Prince"
    #
    # # Define the list of gods you want to see in the matches.
    # # For example, to test all matches involving Hades or Demeter.
    # gods_to_test = [God.ATLAS, God.HERMES, God.HEPHAESTUS]
    #
    # print(f"--- Starting new match series with at least one of: {[g.name for g in gods_to_test]} ---")
    # play_matches_with_specific_gods(
    #     god_list=gods_to_test,
    #     engine1=engine_a,
    #     engine2=engine_b,
    #     starting_time=60
    # )