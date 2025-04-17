import os
import random
import time
from typing import Optional, List, Tuple

from board import God
from tqdm import tqdm
from database import get_conn
from constants import ENGINES
from controller import Controller
from database import store_match
from util import make_position


def fetch_fairest_unplayed_position(cursor, god_a: God, god_b: God, engine_a: str, engine_b: str) -> Optional[str]:
    """
    Fetch the fairest (lowest abs(eval)) unplayed position for (god_a, god_b),
    where no match yet exists between engine_a vs engine_b using that position.
    Considers Depth=2 evaluations only.
    """
    rows = cursor.execute("""
        SELECT Position
        FROM TB_EVALUATION
        WHERE Engine = 'Fitos_11.0_Hyperion'
          AND Depth = 2
          AND substr(Position, 52, 1) = ?
          AND substr(Position, 53, 1) = ?
          AND Position NOT IN (
              SELECT Starting_pos FROM TB_MATCHES
              WHERE (
                  (God_G = ? AND God_B = ?)
                  AND ((Engine_G = ? AND Engine_B = ?) OR (Engine_G = ? AND Engine_B = ?))
              )
          )
        ORDER BY ABS(Eval) ASC
        LIMIT 1
    """, (
        str(god_a.value),
        str(god_b.value),
        god_a.name,
        god_b.name,
        engine_a, engine_b,
        engine_b, engine_a
    )).fetchall()

    return rows[0][0] if rows else None


def run_match(cursor, engine_name_g, engine_name_b, god_a, god_b, starting_time, pos: str, headless=True):
    controller = Controller(pos, starting_time, starting_time,
                            ENGINES[engine_name_g], ENGINES[engine_name_b],
                            headless=headless)
    result, moves = controller.run_game()

    store_match(cursor, god_a, god_b, engine_name_g, engine_name_b,
                result, starting_time, moves, pos)
    return god_a, god_b, result


def play_least_played_forever(engine_a: str, engine_b: str, starting_time: int = 60, pause: float = 0.0):
    conn = get_conn()
    cursor = conn.cursor()

    matchups = [(g1, g2) for g1 in God for g2 in God if g1 != g2]

    counts = {}
    for g1, g2 in matchups:
        cursor.execute(
            """
            SELECT COUNT(*) FROM TB_MATCHES
            WHERE (GOD_G = ? AND GOD_B = ?)
              AND ((Engine_G = ? AND Engine_B = ?) OR (Engine_G = ? AND Engine_B = ?))
            """,
            (g1.name, g2.name, engine_a, engine_b, engine_b, engine_a),
        )
        counts[(g1, g2)] = cursor.fetchone()[0]

    try:
        while True:
            min_val = min(counts.values())
            god_a, god_b = random.choice([k for k, v in counts.items() if v == min_val])

            pos = fetch_fairest_unplayed_position(cursor, god_a, god_b, engine_a, engine_b)
            if not pos:
                print(f"No unplayed positions left for {god_a.name} vs {god_b.name}")
                counts[(god_a, god_b)] += 999999
                continue

            run_match(cursor, engine_a, engine_b, god_a, god_b, starting_time, pos)
            if engine_a != engine_b: run_match(cursor, engine_b, engine_a, god_a, god_b, starting_time, pos)

            conn.commit()
            counts[(god_a, god_b)] += 4
            if pause:
                time.sleep(pause)
    except KeyboardInterrupt:
        pass
    finally:
        conn.close()

def run_single_match(engine_a: str, engine_b: str, god_a: God, god_b: God, starting_time: int = 60, headless=True) -> Optional[Tuple[God, God, int]]:
    conn = get_conn()
    cursor = conn.cursor()

    pos = fetch_fairest_unplayed_position(cursor, god_a, god_b, engine_a, engine_b)
    if not pos:
        print(f"No unplayed positions left for {god_a.name} vs {god_b.name}")
        conn.close()
        return None

    result = run_match(cursor, engine_a, engine_b, god_a, god_b, starting_time, pos, headless=headless)
    conn.commit()
    conn.close()
    return result

if __name__ == '__main__':
    base = "Fitos_11.0_Hyperion"
    new_engine = "Fitos_11.0_Hyperion"

    st = 60
    play_least_played_forever(base, new_engine, st)
