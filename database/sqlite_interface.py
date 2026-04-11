import sqlite3
from typing import List, Tuple, Dict


def get_conn(db_path=r"C:\Users\rafae\PycharmProjects\santoriniMediator\data\matches.db"):
    return sqlite3.connect(db_path)

def get_engines(conn) -> List[Dict[str, int | str]]:
    cursor = conn.cursor()
    engines = cursor.execute("SELECT DISTINCT Engine_G, Engine_B FROM TB_MATCHES ORDER BY Date")
    engine_count = 0
    engine_list = {}
    for engine_g, engine_b in engines.fetchall():
        if engine_g not in engine_list:
            engine_list[engine_g] = engine_count
            engine_count += 1
        if engine_b not in engine_list:
            engine_list[engine_b] = engine_count
            engine_count += 1
    return [{"id": value, "name": key} for (key, value) in engine_list.items()]