import random
import time
from itertools import combinations
from typing import List, Dict, Set, Tuple, Any
import concurrent.futures
from tqdm import tqdm

from game.board import God
from analysis.database import get_conn, store_match
from game.constants import ENGINES
from client.controller import Controller
from play.helpers import load_official_positions, reverse_pos, get_played_matches, prepare_position_string, \
    play_game_worker, GameParams

# --- Configuration ---
ENGINE_PAIRS = [("Fitos_4.6_Atium", "Davi_1.0_Phoenix"),]
POSITIONS_FILE_PATH = "../data/official_starting_pos.txt"
GAMES_PER_MATCHUP = 120
# Set the number of games to play in parallel. Adjust based on your CPU cores.
MAX_WORKERS = 10


def repopulate_database_multithreaded(starting_time: int = 60, max_workers: int = MAX_WORKERS):
    """
    Schedules and plays games in parallel, saving all results to the DB at the end.
    """
    # --- Phase 1: Load static data and database history ---
    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    official_positions = official_positions + [reverse_pos(x) for x in official_positions]

    conn = get_conn()
    cursor = conn.cursor()
    played_matches = get_played_matches(cursor)
    conn.close()  # Close connection; we won't need it until the very end.
    print(f"Found {len(played_matches)} previously played matches.")

    # --- Phase 2: Build a list of all potential games ---
    games_to_schedule: List[GameParams] = []
    god_matchups = list(combinations(God, 2))

    print("\n--- Scheduling potential games ---")
    for prev_engine, current_engine in ENGINE_PAIRS:
        for god1, god2 in god_matchups:
            for i in range(GAMES_PER_MATCHUP // 4 if prev_engine != current_engine else GAMES_PER_MATCHUP // 2):
                template_pos = official_positions[i]

                pos_g1_b2 = prepare_position_string(template_pos, god1, god2)
                pos_g2_b1 = prepare_position_string(template_pos, god2, god1)

                # Add potential games to the schedule
                games_to_schedule.append(
                    GameParams(
                        engine_g=current_engine,
                        engine_b=prev_engine,
                        time_g=starting_time,
                        time_b=starting_time,
                        god_g=god1,
                        god_b=god2,
                        position_str=pos_g1_b2
                    )
                )
                games_to_schedule.append(
                    GameParams(
                        engine_g=current_engine,
                        engine_b=prev_engine,
                        time_g=starting_time,
                        time_b=starting_time,
                        god_g=god2,
                        god_b=god1,
                        position_str=pos_g2_b1
                    )
                )
                if prev_engine != current_engine:
                    games_to_schedule.append(
                        GameParams(
                            engine_g=prev_engine,
                            engine_b=current_engine,
                            time_g=starting_time,
                            time_b=starting_time,
                            god_g=god1,
                            god_b=god2,
                            position_str=pos_g1_b2
                        )
                    )
                    games_to_schedule.append(
                        GameParams(
                            engine_g=prev_engine,
                            engine_b=current_engine,
                            time_g=starting_time,
                            time_b=starting_time,
                            god_g=god2,
                            god_b=god1,
                            position_str=pos_g2_b1
                        )
                    )
    # --- Phase 3: Filter out games that have already been played ---
    unplayed_games = [
        game for game in games_to_schedule
        if (game.position_str, game.engine_g, game.engine_b, starting_time) not in played_matches
    ]

    print(f"\nTotal potential games: {len(games_to_schedule)}")
    print(f"Games to play after filtering: {len(unplayed_games)}")

    if not unplayed_games:
        print("Database is already up to date. No new games to play.")
        return

    # --- Phase 4: Execute unplayed games in parallel ---
    all_results = []
    print(f"\n--- Playing {len(unplayed_games)} games using up to {max_workers} threads ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # tqdm provides a nice progress bar
        results_iterator = executor.map(play_game_worker, unplayed_games)
        all_results = list(tqdm(results_iterator, total=len(unplayed_games), desc="Playing games"))

    # --- Phase 5: Store all results in the database sequentially ---
    if all_results:
        print(f"\n--- Storing {len(all_results)} new match results in the database ---")
        conn = get_conn()
        cursor = conn.cursor()
        for result_data in tqdm(all_results, desc="Saving results"):
            params, result = result_data
            store_match(cursor,
                        params.god_g,
                        params.god_b,
                        params.engine_g,
                        params.engine_b,
                        result.result,
                        params.time_g,
                        result.moves,
                        params.position_str)
        conn.commit()  # Commit all changes at once
        conn.close()

    print("\nDatabase repopulation complete.")


def play_matches_with_specific_gods_multithreaded(
        god_list: List[God],
        engine1: str,
        engine2: str,
        starting_time: int = 60,
        max_workers: int = MAX_WORKERS
):
    """
    Plays matches between two engines where at least one of the specified gods is present.
    Executes games in parallel and saves results at the end.
    """
    # 1. Initial Setup & DB History Fetch
    official_positions = load_official_positions(POSITIONS_FILE_PATH)
    if not official_positions:
        print("Halting execution due to missing positions file.")
        return

    official_positions += [reverse_pos(x) for x in official_positions]
    conn = get_conn()
    cursor = conn.cursor()
    played_matches = get_played_matches(cursor)
    conn.close()
    print(f"Found {len(played_matches)} previously played matches.")

    # 2. Generate Filtered God Matchups
    all_god_matchups = list(combinations(God, 2))
    filtered_god_matchups = [
        matchup for matchup in all_god_matchups
        if matchup[0] in god_list or matchup[1] in god_list
    ]

    if not filtered_god_matchups:
        print(f"No valid god matchups found for the provided list: {[god.name for god in god_list]}")
        return

    # 3. Build the schedule of potential games
    games_to_schedule: List[Dict] = []
    num_games_per_pairing = GAMES_PER_MATCHUP // 4 if engine1 != engine2 else GAMES_PER_MATCHUP // 2
    for i in range(num_games_per_pairing):
        for god1, god2 in filtered_god_matchups:
            template_pos = official_positions[i]
            pos_g1_b2 = prepare_position_string(template_pos, god1, god2)
            pos_g2_b1 = prepare_position_string(template_pos, god2, god1)

            games_to_schedule.append(
                {'engine_g': engine1, 'engine_b': engine2, 'god_g': god1, 'god_b': god2, 'pos': pos_g1_b2,
                 'starting_time': starting_time}
            )
            games_to_schedule.append(
                {'engine_g': engine1, 'engine_b': engine2, 'god_g': god2, 'god_b': god1, 'pos': pos_g2_b1,
                 'starting_time': starting_time}
            )

            if engine1 != engine2:
                games_to_schedule.append(
                    {'engine_g': engine2, 'engine_b': engine1, 'god_g': god1, 'god_b': god2, 'pos': pos_g1_b2,
                     'starting_time': starting_time}
                )
                games_to_schedule.append(
                    {'engine_g': engine2, 'engine_b': engine1, 'god_g': god2, 'god_b': god1, 'pos': pos_g2_b1,
                     'starting_time': starting_time}
                )

    # 4. Filter out played games
    unplayed_games = [
        game for game in games_to_schedule
        if (game['pos'], game['engine_g'], game['engine_b'], starting_time) not in played_matches
    ]
    print(f"\nTotal potential games for this set: {len(games_to_schedule)}")
    print(f"Games to play after filtering: {len(unplayed_games)}")

    if not unplayed_games:
        print("Database is up to date for this set. No new games to play.")
        return

    # 5. Execute games in parallel
    all_results = []
    print(f"\n--- Playing {len(unplayed_games)} games using up to {max_workers} threads ---")
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results_iterator = executor.map(play_game_worker, unplayed_games)
        all_results = list(tqdm(results_iterator, total=len(unplayed_games), desc="Playing games"))

    # 6. Store results
    if all_results:
        print(f"\n--- Storing {len(all_results)} new match results in the database ---")
        conn = get_conn()
        cursor = conn.cursor()
        for result_data in tqdm(all_results, desc="Saving results"):
            store_match(cursor, **result_data)
        conn.commit()  # Commit all changes at once
        conn.close()

    print(f"\nMatch series complete for engines {engine1} and {engine2} with specified gods.")


if __name__ == "__main__":
    # --- Make sure you have tqdm installed: pip install tqdm ---

    # --- Option 1: Run the new multithreaded full repopulation ---
    repopulate_database_multithreaded(starting_time=60, max_workers=MAX_WORKERS)

    # # --- Option 2: Run multithreaded matches with a specific list of gods ---
    # engine_a = "Paladini_5.5.40_Velocity"
    # engine_b = "Paladini_6.5.2_Prince"
    # gods_to_test = [God.ATLAS, God.HERMES, God.HEPHAESTUS]
    #
    # print(f"--- Starting new match series with at least one of: {[g.name for g in gods_to_test]} ---")
    # play_matches_with_specific_gods_multithreaded(
    #     god_list=gods_to_test,
    #     engine1=engine_a,
    #     engine2=engine_b,
    #     starting_time=60,
    #     max_workers=MAX_WORKERS
    # )