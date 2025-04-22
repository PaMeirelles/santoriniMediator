import random
import time
from typing import Optional
from board import God
from database import get_conn, store_match
from constants import ENGINES
from controller import Controller


def fetch_fairest_unplayed_position(
    cursor, god_a: God, god_b: God,
    engine_a: str, engine_b: str
) -> Optional[str]:
    rows = cursor.execute("""
        SELECT Position
        FROM TB_EVALUATION
        WHERE Engine = ?
          AND Depth = 2
          AND substr(Position, 52, 1) = ?
          AND substr(Position, 53, 1) = ?
          AND Position NOT IN (
              SELECT Starting_pos FROM TB_MATCHES
              WHERE
                God_G = ? AND God_B = ?
                AND ((Engine_G = ? AND Engine_B = ?) OR (Engine_G = ? AND Engine_B = ?))
          )
        ORDER BY ABS(Eval) ASC
        LIMIT 1
    """, (
        engine_a,
        str(god_a.value),
        str(god_b.value),
        god_a.name, god_b.name,
        engine_a, engine_b, engine_b, engine_a
    )).fetchall()

    return rows[0][0] if rows else None


def fetch_unplayed_central_position(
    cursor, god_a: God, god_b: God,
    engine_a: str, engine_b: str
) -> Optional[str]:
    # map enum → single digit string
    ga, gb = str(god_a.value), str(god_b.value)

    rows = cursor.execute("""
        SELECT Position
        FROM TB_CENTRAL_POSITIONS
        WHERE
            -- ensure the gods encoded in the string match
            substr(Position, length(Position) - 2, 1) = ?
          AND substr(Position, length(Position) - 1, 1) = ?
          AND Position NOT IN (
            SELECT Starting_pos
            FROM TB_MATCHES
            WHERE
              God_G = ? AND God_B = ?
              AND (
                (Engine_G = ? AND Engine_B = ?)
             OR (Engine_G = ? AND Engine_B = ?)
              )
          )
        ORDER BY RANDOM()
        LIMIT 1
    """, (
        ga, gb,                         # two checks on the Position column
        god_a.name, god_b.name,         # to exclude already‐played
        engine_a, engine_b,
        engine_b, engine_a
    )).fetchall()

    return rows[0][0] if rows else None



def fetch_position(
    cursor, god_a: God, god_b: God,
    engine_a: str, engine_b: str,
    central: bool = False
) -> Optional[str]:
    if central:
        return fetch_unplayed_central_position(
            cursor, god_a, god_b, engine_a, engine_b
        )
    else:
        return fetch_fairest_unplayed_position(
            cursor, god_a, god_b, engine_a, engine_b
        )


def run_match(
    cursor,
    engine_name_g: str,
    engine_name_b: str,
    god_a: God,
    god_b: God,
    starting_time: int,
    pos: str,
    headless: bool = True
):
    ctrl = Controller(
        pos, starting_time, starting_time,
        ENGINES[engine_name_g],
        ENGINES[engine_name_b],
        headless=headless
    )
    result, moves = ctrl.run_game()
    store_match(
        cursor,
        god_a, god_b, engine_name_g, engine_name_b,
        result, starting_time, moves, pos
    )
    return result


def play_least_played_forever(
    engine_a: str, engine_b: str,
    starting_time: int = 60,
    pause: float = 0.0,
    central: bool = False
):
    conn = get_conn()
    cur = conn.cursor()

    # all god‐pairs
    matchups = [(g1, g2) for g1 in God for g2 in God if g1 != g2]
    counts = {}
    for g1, g2 in matchups:
        cur.execute("""
            SELECT COUNT(*) FROM TB_MATCHES
            WHERE God_G = ? AND God_B = ?
              AND ((Engine_G = ? AND Engine_B = ?) OR (Engine_G = ? AND Engine_B = ?))
        """, (g1.name, g2.name, engine_a, engine_b, engine_b, engine_a))
        counts[(g1, g2)] = cur.fetchone()[0]

    try:
        while True:
            # pick a least‐played matchup
            min_played = min(counts.values())
            god_a, god_b = random.choice(
                [pair for pair, c in counts.items() if c == min_played]
            )

            pos = fetch_position(
                cur, god_a, god_b, engine_a, engine_b,
                central=central
            )
            if not pos:
                print(f"No unplayed positions for {god_a}-{god_b}")
                counts[(god_a, god_b)] += 1_000_000
                continue

            # play both colors if distinct engines
            run_match(cur, engine_a, engine_b, god_a, god_b, starting_time, pos)
            if engine_a != engine_b:
                run_match(cur, engine_b, engine_a, god_a, god_b, starting_time, pos)

            conn.commit()
            counts[(god_a, god_b)] += 4
            if pause:
                time.sleep(pause)

    except KeyboardInterrupt:
        pass

    finally:
        conn.close()


if __name__ == "__main__":
    base       = "Fitos_13.0_Legacy"
    new_engine = "Fitos_14.1_Broken"
    st         = 60

    # change central=True to pull from TB_CENTRAL_POSITIONS
    play_least_played_forever(base, new_engine, st, pause=0.0, central=True)
