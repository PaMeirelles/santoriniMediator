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


def run_match(cursor, engine_name_g, engine_name_b, god_a, god_b, starting_time):
    """
    Runs one match between (engine_name_g, god_a) and (engine_name_b, god_b).
    Stores the result in TB_MATCHES but does NOT do rating updates.

    Returns: result = 1 if Gray wins, -1 if Blue wins.
    """
    # Must be in the ENGINES dict, else ValueError
    path_g = ENGINES.get(engine_name_g)
    path_b = ENGINES.get(engine_name_b)
    if not path_g or not path_b:
        raise ValueError(f"Both engines must have valid executable paths. "
                         f"Got engine_g={engine_name_g}, engine_b={engine_name_b}")

    # Position
    workers = generate_workers()
    pos = make_position([0]*25, workers[:2], workers[2:], 1, god_a, god_b)

    # Run the match
    controller = Controller(pos, starting_time, starting_time, path_g, path_b, headless=True)
    result = controller.run_game()  # 1 (Gray wins) or -1 (Blue wins)

    store_match(cursor, god_a, god_b, engine_name_g, engine_name_b, result)
    return result


















if __name__ == '__main__':
    all_combinations("Fitos_4.0_Atium", "Fitos_4.0_Atium", 60)
