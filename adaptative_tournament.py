# adaptive_tournament.py
import os
import random
import sqlite3
import trueskill
from board import God
from controller import Controller
from tqdm import tqdm

# Initialize the TrueSkill environment.
ts = trueskill.TrueSkill(mu=25.0, sigma=8.333, beta=4.1667, tau=0.08333, draw_probability=0.0)

# Define your engines using the exact names used in TB_MATCHES.
ENGINES = {
    "Fitos_1.1_Ton": "engines/Fitos/Ton/Fitos_1.1_Ton.exe",
    "Fitos_2.1_Scout": "engines/Fitos/Scout/Fitos_2.1_Scout.exe"
}


def setup_db():
    conn = sqlite3.connect("data/matches.db")
    cur = conn.cursor()
    cur.execute('''
        CREATE TABLE IF NOT EXISTS TB_MATCHES (
            Id INTEGER PRIMARY KEY AUTOINCREMENT,
            God_G TEXT,
            God_B TEXT,
            Engine_G TEXT,
            Engine_B TEXT,
            Result INTEGER
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


def generate_workers():
    return random.sample(range(25), 4)


def make_position(blocks, gray_workers, blue_workers, turn, god_gray, god_blue):
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


def update_ratings(cursor, engine_g, god_g, engine_b, god_b, result):
    cursor.execute("SELECT Mu, Sigma FROM TB_RATINGS WHERE Engine=? AND God=?", (engine_g, god_g))
    row = cursor.fetchone()
    if row is None:
        rating_g = ts.Rating()
        cursor.execute("INSERT INTO TB_RATINGS (Engine, God, Mu, Sigma) VALUES (?, ?, ?, ?)",
                       (engine_g, god_g, rating_g.mu, rating_g.sigma))
    else:
        rating_g = ts.Rating(mu=row[0], sigma=row[1])

    cursor.execute("SELECT Mu, Sigma FROM TB_RATINGS WHERE Engine=? AND God=?", (engine_b, god_b))
    row = cursor.fetchone()
    if row is None:
        rating_b = ts.Rating()
        cursor.execute("INSERT INTO TB_RATINGS (Engine, God, Mu, Sigma) VALUES (?, ?, ?, ?)",
                       (engine_b, god_b, rating_b.mu, rating_b.sigma))
    else:
        rating_b = ts.Rating(mu=row[0], sigma=row[1])

    if result == 1:
        new_rating_g, new_rating_b = trueskill.rate_1vs1(rating_g, rating_b)
    else:
        new_rating_b, new_rating_g = trueskill.rate_1vs1(rating_b, rating_g)

    cursor.execute("UPDATE TB_RATINGS SET Mu=?, Sigma=? WHERE Engine=? AND God=?",
                   (new_rating_g.mu, new_rating_g.sigma, engine_g, god_g))
    cursor.execute("UPDATE TB_RATINGS SET Mu=?, Sigma=? WHERE Engine=? AND God=?",
                   (new_rating_b.mu, new_rating_b.sigma, engine_b, god_b))


def bootstrap_from_matches(cursor):
    """
    Load all existing matches from TB_MATCHES and update ratings.
    """
    cursor.execute("SELECT God_G, God_B, Engine_G, Engine_B, Result FROM TB_MATCHES ORDER BY Id")
    for god_g, god_b, eng_g, eng_b, result in cursor.fetchall():
        update_ratings(cursor, eng_g, god_g, eng_b, god_b, result)


from datetime import datetime

def run_match(cursor, engine_name_g, engine_name_b, god_a, god_b, starting_time):
    path_a = ENGINES.get(engine_name_g)
    path_b = ENGINES.get(engine_name_b)
    if path_a is None or path_b is None:
        raise ValueError("Both engines must have valid executable paths.")

    workers = generate_workers()
    pos = make_position([0] * 25, workers[:2], workers[2:], 1, god_a, god_b)
    controller = Controller(pos, starting_time, starting_time, path_a, path_b, headless=True)
    result = controller.run_game()

    match_date = datetime.now().isoformat(timespec="seconds")
    cursor.execute('''
        INSERT INTO TB_MATCHES (God_G, God_B, Engine_G, Engine_B, Result, Date)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (god_a.name, god_b.name, engine_name_g, engine_name_b, result, match_date))

    update_ratings(cursor, engine_name_g, god_a.name, engine_name_b, god_b.name, result)
    return result



def select_match(cursor):
    allowed_engines = set(ENGINES.keys())
    cursor.execute("SELECT Engine, God, Mu, Sigma FROM TB_RATINGS")
    ratings = cursor.fetchall()
    rating_dict = {(row[0], row[1]): (row[2], row[3]) for row in ratings if row[0] in allowed_engines}

    if len(rating_dict) < 2:
        return None

    best_pair = None
    best_uncertainty = float('inf')
    for (eng1, god1), (mu1, sigma1) in rating_dict.items():
        for (eng2, god2), (mu2, sigma2) in rating_dict.items():
            if (eng1, god1) == (eng2, god2):
                continue
            diff = abs(mu1 - mu2)
            combined_uncertainty = sigma1 + sigma2
            uncertainty_metric = diff / combined_uncertainty if combined_uncertainty > 0 else diff
            if uncertainty_metric < best_uncertainty:
                best_uncertainty = uncertainty_metric
                best_pair = ((eng1, god1), (eng2, god2))
    return best_pair

def adaptive_tournament(starting_time, iterations=1000):
    conn = setup_db()
    cursor = conn.cursor()

    # Bootstrap TB_RATINGS from past results.
    bootstrap_from_matches(cursor)
    conn.commit()

    gods = list(God)

    for _ in tqdm(range(iterations), desc="Adaptive Tournament"):
        match_pair = select_match(cursor)
        if match_pair is None:
            engine_pair = random.sample(list(ENGINES.keys()), 2)
            god_pair = random.sample(gods, 2)
            engine_g, engine_b = engine_pair
            god_a, god_b = god_pair
        else:
            (engine_g, god_g), (engine_b, god_b) = match_pair
            god_a = next(g for g in gods if g.name == god_g)
            god_b = next(g for g in gods if g.name == god_b)

        run_match(cursor, engine_g, engine_b, god_a, god_b, starting_time)
        conn.commit()

    conn.close()


if __name__ == '__main__':
    adaptive_tournament(starting_time=1000, iterations=1000)
