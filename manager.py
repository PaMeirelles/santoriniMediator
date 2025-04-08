import concurrent.futures
from typing import Optional, List, Tuple

from board import God
from tqdm import tqdm
from database import get_conn
from constants import ENGINES
from controller import Controller
from database import store_match
from util import generate_workers, make_position

def all_combinations(name_a, name_b, starting_time):
    conn = get_conn()
    cursor = conn.cursor()
    for _ in tqdm(range(1000), desc="Overall Iterations"):
        for god_a in God:
            for god_b in God:
                if god_a == god_b:
                    continue
                run_match(cursor, name_a, name_b, god_a, god_b, starting_time)
                conn.commit()
    conn.close()


def run_match(engine_name_g, engine_name_b, god_a, god_b, starting_time):
    # Each process gets its own DB connection
    conn = get_conn()
    cursor = conn.cursor()
    # Generate workers and position
    workers = generate_workers()
    pos = make_position([0] * 25, workers[:2], workers[2:], 1, god_a, god_b)
    # Instantiate controller and run the game
    controller = Controller(pos, starting_time, starting_time, ENGINES[engine_name_g], ENGINES[engine_name_b],
                            headless=True)
    result, moves = controller.run_game()
    # Store the match result
    store_match(cursor, god_a, god_b, engine_name_g, engine_name_b, result, starting_time, moves, pos)
    conn.commit()
    conn.close()
    return god_a, god_b, result


def all_combinations_parallel(name_a, name_b, starting_time, matchups:Optional[List[Tuple[God, God]]]=None,
                              iterations:int = 1000):
    tasks = []
    if matchups is None:
        matchups = [(god_a, god_b) for god_a in God for god_b in God if god_a.value < god_b.value]
    # Setup tasks for every match across 1000 iterations and god combinations.
    for _ in range(iterations):
        for god_a, god_b in matchups:
            tasks.append((name_a, name_b, god_a, god_b, starting_time))
            tasks.append((name_b, name_a, god_a, god_b, starting_time))
            tasks.append((name_a, name_b, god_b, god_a, starting_time))
            tasks.append((name_b, name_a, god_b, god_a, starting_time))


    # Use ProcessPoolExecutor for parallel execution.
    results = []
    with concurrent.futures.ProcessPoolExecutor() as executor:
        # Map tasks to processes
        future_to_match = {executor.submit(run_match, *task): task for task in tasks}
        for future in concurrent.futures.as_completed(future_to_match):
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                print(f'Generated an exception: {exc}')
    return results


if __name__ == '__main__':
    engine = "Fitos_6.2_Trick"
    st = 60
    it = 1
    all_combinations_parallel(engine, engine, st, iterations=it)
