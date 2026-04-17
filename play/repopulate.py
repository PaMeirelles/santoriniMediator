import concurrent.futures
from datetime import datetime
from typing import List
from tqdm import tqdm
from database.models import God, Pair, Match, convert_result, GameParams
from play.helpers import load_official_positions, reverse_pos, play_game_worker, filter_unplayed_tasks, \
    generate_engine_god_configs, build_game_tasks
from database.postgres.postgres_interface import get_engine, get_pg_mappings, store_match_pg


def run_tasks(tasks: List[dict], max_workers: int):
    pg_engine = get_engine()
    gods_map, engines_map = get_pg_mappings(pg_engine)

    unplayed: List[GameParams] = filter_unplayed_tasks(tasks, pg_engine)

    if not unplayed:
        print("Database is already up to date.")
        return

    print(f"Executing {len(unplayed)} new games...")


    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {executor.submit(play_game_worker, t): t for t in unplayed}

        for future in tqdm(concurrent.futures.as_completed(future_to_task), total=len(unplayed)):
            params, result = future.result()

            match_data = Match(
                game_id=0,
                starting_pos=params.position_str,
                players=(
                    Pair(engine=params.engine_g, god=params.god_g),
                    Pair(engine=params.engine_b, god=params.god_b)
                ),
                time_ms=(params.time_g, params.time_b),
                winner=(result.result > 0),
                result_type=convert_result(result.result),
                played_at=datetime.now(),
                moves=result.moves
            )

            with pg_engine.begin() as conn:
                store_match_pg(conn, match_data, gods_map, engines_map)



def schedule_and_run(engine_pairs: list[tuple[str, str]], max_workers: int, games_per_matchup: int,
                     starting_time_seconds: int,
                     positions: list[str]|None = None):
    if positions is None:
        positions = load_official_positions("../data/official_starting_pos.txt")
        positions += [reverse_pos(p) for p in positions]

    configs = generate_engine_god_configs(engine_pairs, list(God), games_per_matchup)
    all_tasks = build_game_tasks(configs, positions, starting_time_seconds)

    run_tasks(all_tasks, max_workers=max_workers)


if __name__ == "__main__":
    # --- Configuration ---
    ENGINE_PAIRS = [("Paladini_8.1.8_Firefly", "Paladini_9.2_Prophet")]
    schedule_and_run(engine_pairs=ENGINE_PAIRS, max_workers=8, games_per_matchup=4, starting_time_seconds=10)