import os
import random
import sqlite3

from adaptative_tournament import run_match
from board import God
from controller import Controller
from tqdm import tqdm


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
    conn.commit()
    return conn


def all_combinations(name_a, name_b, starting_time):
    conn = setup_db()
    cursor = conn.cursor()
    for _ in tqdm(range(1000), desc="Overall Iterations"):
        for god_a in God:
            for god_b in God:
                if god_a == god_b:
                    continue
                run_match(cursor, name_a, name_b, god_a, god_b, starting_time)
        conn.commit()
    conn.close()


all_combinations("Fitos_3.2_Life", "Fitos_3.2_Life", 1000)
