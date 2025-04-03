# adaptive_tournament.py

import os
import random
import sqlite3
import trueskill
from datetime import datetime
from tqdm import tqdm

# YOUR PROJECT IMPORTS (adjust if needed)
from board import God
from controller import Controller

# ---------------------------------------------------------------------
# 1. TrueSkill Environment
# ---------------------------------------------------------------------
ts_env = trueskill.TrueSkill(
    mu=25.0,
    sigma=8.333,
    beta=4.1667,
    tau=0.08333,
    draw_probability=0.0
)

# ---------------------------------------------------------------------
# 2. Engines – ONLY these two
# ---------------------------------------------------------------------
ENGINES = {
    "Fitos_1.1_Ton": "engines/Fitos/Ton/Fitos_1.1_Ton.exe",
    "Fitos_2.1_Scout": "engines/Fitos/Scout/Fitos_2.1_Scout.exe",
    "Fitos_3.2_Life": "engines/Fitos/Life/Fitos_3.2_Life.exe",
}

# ---------------------------------------------------------------------
# 3. Database Setup
# ---------------------------------------------------------------------
def setup_db(db_path="data/matches.db"):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS TB_MATCHES (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            God_G TEXT,
            God_B TEXT,
            Engine_G TEXT,
            Engine_B TEXT,
            Result INTEGER,
            Date TEXT
        )
    ''')
    cur.execute('''
        CREATE TABLE IF NOT EXISTS TB_RATINGS (
            Engine TEXT,
            God TEXT,
            Mu REAL,
            Sigma REAL,
            PRIMARY KEY (Engine, God)
        )
    ''')
    conn.commit()
    return conn

# ---------------------------------------------------------------------
# 4. Helper: Load only matches with engines in ENGINES
# ---------------------------------------------------------------------
def load_matches_filtered(cursor):
    """
    Return a list of (god_g, god_b, eng_g, eng_b, result)
    but only for rows where eng_g and eng_b are in ENGINES.
    """
    cursor.execute("SELECT God_G, God_B, Engine_G, Engine_B, Result FROM TB_MATCHES")
    valid_matches = []
    for (god_g, god_b, eng_g, eng_b, result) in cursor.fetchall():
        if eng_g in ENGINES and eng_b in ENGINES:
            valid_matches.append((god_g, god_b, eng_g, eng_b, result))
    return valid_matches

# ---------------------------------------------------------------------
# 5. Helpers for position creation
# ---------------------------------------------------------------------
def generate_workers():
    return random.sample(range(25), 4)

def make_position(blocks, gray_workers, blue_workers, turn, god_gray, god_blue):
    """
    Helper function that builds a position string for your Controller.
    """
    position_chars = []
    for sq in range(25):
        h = blocks[sq]
        if sq in gray_workers:
            w = 'G'
        elif sq in blue_workers:
            w = 'B'
        else:
            w = 'N'
        position_chars.append(str(h))
        position_chars.append(w)
    turn_char = '0' if turn == 1 else '1'
    god_gray_char = str(god_gray.value)
    god_blue_char = str(god_blue.value)
    return ''.join(position_chars) + turn_char + god_gray_char + god_blue_char + '0'

# ---------------------------------------------------------------------
# 6. Run a single match (no direct rating updates)
# ---------------------------------------------------------------------
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

    match_date = datetime.now().isoformat(timespec="seconds")
    cursor.execute('''
        INSERT INTO TB_MATCHES (God_G, God_B, Engine_G, Engine_B, Result, Date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (god_a.name, god_b.name, engine_name_g, engine_name_b, result, match_date))

    return result

# ---------------------------------------------------------------------
# 7. Order-Insensitive Batch Recompute
# ---------------------------------------------------------------------
def batch_trueskill_recompute(conn, passes=5):
    """
    Reads ALL valid matches from TB_MATCHES ignoring order,
    does multiple random-pass TrueSkill updates,
    and writes final (Mu, Sigma) to TB_RATINGS.
    """
    cursor = conn.cursor()

    # Load valid matches only
    all_matches = load_matches_filtered(cursor)
    if not all_matches:
        # If no matches, just wipe TB_RATINGS
        cursor.execute("DELETE FROM TB_RATINGS")
        conn.commit()
        return

    # Collect unique (engine, god) pairs
    pair_set = set()
    for (god_g, god_b, eng_g, eng_b, result) in all_matches:
        pair_set.add((eng_g, god_g))
        pair_set.add((eng_b, god_b))

    # Initialize ratings
    ratings_dict = { pair: ts_env.Rating() for pair in pair_set }

    # Multiple passes of random order
    for _ in range(passes):
        random.shuffle(all_matches)
        for (god_g, god_b, eng_g, eng_b, result) in all_matches:
            r_g = ratings_dict[(eng_g, god_g)]
            r_b = ratings_dict[(eng_b, god_b)]

            if result == 1:
                new_g, new_b = trueskill.rate_1vs1(r_g, r_b, env=ts_env)
            else:
                new_b, new_g = trueskill.rate_1vs1(r_b, r_g, env=ts_env)

            ratings_dict[(eng_g, god_g)] = new_g
            ratings_dict[(eng_b, god_b)] = new_b

    # Store final results in TB_RATINGS
    cursor.execute("DELETE FROM TB_RATINGS")
    for (eng, god), rating in ratings_dict.items():
        cursor.execute('''
            INSERT INTO TB_RATINGS (Engine, God, Mu, Sigma) VALUES (?, ?, ?, ?)
        ''', (eng, god, rating.mu, rating.sigma))
    conn.commit()

# ---------------------------------------------------------------------
# 8. Temporary Ratings for Adaptive Match Selection
# ---------------------------------------------------------------------
def compute_temp_ratings(conn, matches=None):
    """
    Computes a quick TrueSkill rating (single-pass) for adaptive selection.
    If 'matches' is None, we load from TB_MATCHES but only for valid engines.
    """
    if matches is None:
        cursor = conn.cursor()
        matches = load_matches_filtered(cursor)

    if not matches:
        return {}

    # Collect unique pairs
    pair_set = set()
    for (god_g, god_b, eng_g, eng_b, result) in matches:
        pair_set.add((eng_g, god_g))
        pair_set.add((eng_b, god_b))

    # Initialize
    ratings_dict = { pair: ts_env.Rating() for pair in pair_set }

    # Single-pass
    for (god_g, god_b, eng_g, eng_b, result) in matches:
        r_g = ratings_dict[(eng_g, god_g)]
        r_b = ratings_dict[(eng_b, god_b)]
        if result == 1:
            new_g, new_b = trueskill.rate_1vs1(r_g, r_b, env=ts_env)
        else:
            new_b, new_g = trueskill.rate_1vs1(r_b, r_g, env=ts_env)
        ratings_dict[(eng_g, god_g)] = new_g
        ratings_dict[(eng_b, god_b)] = new_b

    return ratings_dict

def update_temp_ratings_single_match(ratings_dict, match):
    """
    Incrementally update the ephemeral rating dict
    with one new result: (god_g, god_b, eng_g, eng_b, result).
    """
    (god_g, god_b, eng_g, eng_b, result) = match
    r_g = ratings_dict.setdefault((eng_g, god_g), ts_env.Rating())
    r_b = ratings_dict.setdefault((eng_b, god_b), ts_env.Rating())

    if result == 1:
        new_g, new_b = trueskill.rate_1vs1(r_g, r_b, env=ts_env)
    else:
        new_b, new_g = trueskill.rate_1vs1(r_b, r_g, env=ts_env)

    ratings_dict[(eng_g, god_g)] = new_g
    ratings_dict[(eng_b, god_b)] = new_b

# ---------------------------------------------------------------------
# 9. Adaptive Selection Logic (using temp ratings)
# ---------------------------------------------------------------------
def select_match_temp_ratings(ratings_dict):
    """
    Pick a pair with high uncertainty. Only uses (engine, god)
    that are actually in ENGINES to avoid 2.0 issues.
    Returns ((engine_g, god_g), (engine_b, god_b)) or None if insufficient data.
    """
    # Filter out any pair whose engine is not in ENGINES
    valid_pairs = [p for p in ratings_dict.keys() if p[0] in ENGINES]
    if len(valid_pairs) < 2:
        return None

    best_pair = None
    best_metric = -9999.0

    for i in range(len(valid_pairs)):
        eng1, god1 = valid_pairs[i]
        r1 = ratings_dict[(eng1, god1)]
        for j in range(i+1, len(valid_pairs)):
            eng2, god2 = valid_pairs[j]
            if eng1 == eng2 and god1 == god2:
                continue
            r2 = ratings_dict[(eng2, god2)]
            # Example metric: sum of sigma - abs diff in mu
            metric = (r1.sigma + r2.sigma) - abs(r1.mu - r2.mu)
            if metric > best_metric:
                best_metric = metric
                best_pair = ((eng1, god1), (eng2, god2))

    return best_pair

# ---------------------------------------------------------------------
# 10. Main Tournament Function
# ---------------------------------------------------------------------
def adaptive_tournament(starting_time, iterations=10):
    """
    1) Setup DB
    2) Compute initial temp_ratings from valid matches
    3) For each iteration:
       - select uncertain pair from temp_ratings
       - run the match
       - update temp_ratings
    4) batch_trueskill_recompute (order-insensitive) for final rating
    """
    conn = setup_db()
    cursor = conn.cursor()

    # 1. Compute initial ephemeral rating
    temp_ratings = compute_temp_ratings(conn)

    # 2. For each iteration
    gods = list(God)
    engine_list = list(ENGINES.keys())  # Only has Fitos_1.1_Ton, Fitos_2.1_Scout

    for _ in tqdm(range(iterations), desc="Adaptive Tournament"):
        pair = select_match_temp_ratings(temp_ratings)
        if pair is not None:
            (eng_g, god_g), (eng_b, god_b) = pair
            # Convert string to God enum
            real_god_g = next(g for g in gods if g.name == god_g)
            real_god_b = next(g for g in gods if g.name == god_b)
        else:
            # Fallback if we don't have enough pairs
            eng_g, eng_b = random.sample(engine_list, 2)
            real_god_g, real_god_b = random.sample(gods, 2)

        result = run_match(cursor, eng_g, eng_b, real_god_g, real_god_b, starting_time)
        conn.commit()

        # Build tuple to update ephemeral rating
        match_tuple = (real_god_g.name, real_god_b.name, eng_g, eng_b, result)
        update_temp_ratings_single_match(temp_ratings, match_tuple)

    # 3. Final batch recompute ignoring order
    batch_trueskill_recompute(conn, passes=5)
    conn.close()

# ---------------------------------------------------------------------
# 11. Entry Point
# ---------------------------------------------------------------------
if __name__ == '__main__':
    adaptive_tournament(starting_time=1000, iterations=100)














