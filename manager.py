import os
import random
from typing import Optional, List, Tuple

from board import God
from tqdm import tqdm
from database import get_conn
from constants import ENGINES
from controller import Controller
from database import store_match
from util import generate_workers, make_position


def all_combinations(name_a: str, name_b: str, starting_time: int,
                     iterations: int = 1000,
                     matchups: Optional[List[Tuple[God, God]]] = None):
    conn = get_conn()
    cursor = conn.cursor()

    if matchups is None:
        matchups = [(g1, g2) for g1 in God for g2 in God if g1.value < g2.value]

    for _ in tqdm(range(iterations), desc="Overall Iterations"):
        for god_a, god_b in matchups:
            workers = generate_workers()
            pos_a = make_position([0] * 25, workers[:2], workers[2:], 1, god_a, god_b)
            pos_b = make_position([0] * 25, workers[:2], workers[2:], 1, god_b, god_a)

            run_match(cursor, name_a, name_b, god_a, god_b, starting_time, pos_a)
            run_match(cursor, name_b, name_a, god_a, god_b, starting_time, pos_a)
            run_match(cursor, name_a, name_b, god_b, god_a, starting_time, pos_b)
            run_match(cursor, name_b, name_a, god_b, god_a, starting_time, pos_b)

            conn.commit()

    conn.close()


def run_match(cursor, engine_name_g, engine_name_b, god_a, god_b, starting_time, pos=None):
    if pos is None:
        workers = generate_workers()
        pos = make_position([0] * 25, workers[:2], workers[2:], 1, god_a, god_b)

    controller = Controller(pos, starting_time, starting_time,
                            ENGINES[engine_name_g], ENGINES[engine_name_b],
                            headless=True)
    result, moves = controller.run_game()

    store_match(cursor, god_a, god_b, engine_name_g, engine_name_b,
                result, starting_time, moves, pos)
    return god_a, god_b, result

import random
import time

def play_least_played_forever(engine_a: str, engine_b: str, starting_time: int = 60, pause: float = 0.0):
    conn = get_conn()
    cursor = conn.cursor()

    matchups = [(g1, g2) for g1 in God for g2 in God if g1.value < g2.value]
    counts = {}
    for g1, g2 in matchups:
        cursor.execute(
            """
            SELECT COUNT(*) FROM TB_MATCHES
            WHERE ((GOD_G = ? AND GOD_B = ?) OR (GOD_G = ? AND GOD_B = ?))
              AND ((Engine_G = ? AND Engine_B = ?) OR (Engine_G = ? AND Engine_B = ?))
            """,
            (g1.name, g2.name, g2.name, g1.name, engine_a, engine_b, engine_b, engine_a),
        )
        counts[(g1, g2)] = cursor.fetchone()[0]

    try:
        while True:
            min_val = min(counts.values())
            god_a, god_b = random.choice([k for k, v in counts.items() if v == min_val])

            workers = generate_workers()
            pos_a = make_position([0] * 25, workers[:2], workers[2:], 1, god_a, god_b)
            pos_b = make_position([0] * 25, workers[:2], workers[2:], 1, god_b, god_a)

            run_match(cursor, engine_a, engine_b, god_a, god_b, starting_time, pos_a)
            run_match(cursor, engine_b, engine_a, god_a, god_b, starting_time, pos_a)
            run_match(cursor, engine_a, engine_b, god_b, god_a, starting_time, pos_b)
            run_match(cursor, engine_b, engine_a, god_b, god_a, starting_time, pos_b)

            conn.commit()
            counts[(god_a, god_b)] += 4
            if pause:
                time.sleep(pause)
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()


if __name__ == '__main__':
    base = "Fitos_8.1_Cursed"
    new_engine = "Fitos_9.3_Moth"

    st = 60
    it = 10000
    play_least_played_forever(base, new_engine, st)

