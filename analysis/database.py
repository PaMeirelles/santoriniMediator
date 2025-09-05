import sqlite3
from datetime import datetime
from game.board import God
from game.constants import ENGINES


def get_conn(db_path=r"C:\Users\rafae\PycharmProjects\santoriniMediator\data\matches.db"):
    return sqlite3.connect(db_path)

def load_matches_filtered(cursor, engines=ENGINES):
    cursor.execute("SELECT God_G, God_B, Engine_G, Engine_B, Result FROM TB_MATCHES")
    return [
        (god_g, god_b, eng_g, eng_b, result)
        for god_g, god_b, eng_g, eng_b, result in cursor.fetchall()
        if eng_g in engines and eng_b in engines
    ]

def store_match(cursor, god_a:God, god_b:God, engine_name_g:str, engine_name_b:str, result:int, starting_time: int, moves: str, pos:str):
    match_date = datetime.now().isoformat(timespec="seconds")
    cursor.execute('''
        INSERT INTO TB_MATCHES (God_G, God_B, Engine_G, Engine_B, Result, Date, Time_G, Time_B, Moves, Starting_pos)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (god_a.name, god_b.name, engine_name_g, engine_name_b, result, match_date, starting_time, starting_time, moves, pos))
