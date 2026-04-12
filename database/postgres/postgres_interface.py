import os
from typing import Tuple, List, Dict, Any
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text


load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

def get_engine() -> Engine:
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL não encontrada no arquivo .env")

    engine = create_engine(DATABASE_URL)
    return engine


def get_pg_mappings(pg_engine: Engine) -> Tuple[dict, dict]:
    with pg_engine.connect() as conn:
        gods_result = conn.execute(text("SELECT god_id, god_name FROM tb_gods"))
        gods_map = {row.god_name: row.god_id for row in gods_result}

        engines_result = conn.execute(text("SELECT engine_id, engine_name FROM tb_engines"))
        engines_map = {row.engine_name: row.engine_id for row in engines_result}
    return gods_map, engines_map


def map_sqlite_result(sqlite_result: int) -> Tuple[bool, str]:
    gray_win = sqlite_result > 0

    match abs(sqlite_result):
        case 1:
            result_type = 'N'
        case 2:
            result_type = 'T'
        case 3:
            result_type = 'I'
        case _:
            raise ValueError("Invalid result type")

    return gray_win, result_type


def load_matches_from_pg(engine: Engine, limit: int = 100) -> List[Dict[str, Any]]:
    query = text("""
        SELECT 
            m.match_id, 
            m.winner_side, 
            m.result_type, 
            m.timestamp, 
            m.starting_pos, 
            m.moves,
            eng_gray.engine_name AS gray_engine, 
            god_gray.god_name AS gray_god,
            eng_blue.engine_name AS blue_engine, 
            god_blue.god_name AS blue_god
        FROM tb_matches m
        -- Join for Gray Player (side = TRUE based on python migration script)
        JOIN tb_match_participants part_gray 
            ON m.match_id = part_gray.match_id AND part_gray.side = TRUE
        JOIN tb_engines eng_gray 
            ON part_gray.engine_id = eng_gray.engine_id
        JOIN tb_gods god_gray 
            ON part_gray.god_id = god_gray.god_id

        -- Join for Blue Player (side = FALSE based on python migration script)
        JOIN tb_match_participants part_blue 
            ON m.match_id = part_blue.match_id AND part_blue.side = FALSE
        JOIN tb_engines eng_blue 
            ON part_blue.engine_id = eng_blue.engine_id
        JOIN tb_gods god_blue 
            ON part_blue.god_id = god_blue.god_id

        ORDER BY m.timestamp DESC
        LIMIT :limit
    """)

    loaded_matches = []

    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit})

        for row in result:
            loaded_matches.append({
                "match_id": row.match_id,
                "winner_side": "Gray" if row.winner_side else "Blue",
                "result_type": row.result_type,
                "timestamp": row.timestamp,
                "starting_pos": row.starting_pos,
                "moves": row.moves,  # Raw bytes (requires decompression)
                "gray_player": {
                    "engine": row.gray_engine,
                    "god": row.gray_god
                },
                "blue_player": {
                    "engine": row.blue_engine,
                    "god": row.blue_god
                }
            })

    return loaded_matches
