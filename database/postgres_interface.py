import os
import sqlite3
from typing import List, Dict, Tuple
from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine, text

from database.data_compression import starting_position_to_bytes, move_to_bytes
from database.models import God, string_to_god, god_to_string, get_move_from_string
from game.move import Move
from sqlite_interface import get_engines, get_conn

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


def insert_all_gods(engine: Engine) -> None:
    query = text("""
        INSERT INTO tb_gods (god_id, god_name) 
        VALUES (:id, :name) 
        ON CONFLICT (god_id) DO NOTHING
    """)

    data = [{"id": god.value, "name": god_to_string(god)} for god in God]

    try:
        with engine.begin() as conn:
            conn.execute(query, data)
            print(f"Sucesso: {len(data)} deuses processados.")
    except Exception as e:
        print(f"Erro ao inserir deuses: {e}")


def insert_list_of_engines(db_engine: Engine, engines: List[Dict[str, int | str]]) -> None:
    query = text("""
        INSERT INTO tb_engines (engine_id, engine_name) 
        VALUES (:id, :name) 
        ON CONFLICT (engine_id) DO NOTHING
    """)

    try:
        with db_engine.begin() as conn:
            conn.execute(query, engines)
            print(f"Sucesso: {len(engines)} engines processadas.")
    except Exception as e:
        print(f"Erro ao inserir engines: {e}")


def insert_all_engines(db_engine: Engine) -> None:
    conn = get_conn()
    engines = get_engines(conn)

    insert_list_of_engines(db_engine, engines)


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


def migrate_matches(sqlite_conn: sqlite3.Connection, pg_engine: Engine):
    gods_map, engines_map = get_pg_mappings(pg_engine)

    cursor = sqlite_conn.cursor()
    cursor.execute("""
        SELECT Id, God_G, God_B, Engine_G, Engine_B, Result, Date, Starting_pos, Moves
        FROM TB_MATCHES
    """)
    rows = cursor.fetchall()

    matches_data = []
    participants_data = []

    for row in rows:
        (m_id, god_g_str, god_b_str, eng_g, eng_b, result, date_str, start_pos, moves) = row

        god_g, god_b = string_to_god(god_g_str), string_to_god(god_b_str)
        god_g_str, god_b_str = god_to_string(god_g), god_to_string(god_b)

        compressed_moves = None
        if moves is not None and moves != '':
            move_list = []
            for i, move in enumerate(moves.split("\n")):
                if i % 2 == 0:
                    god = god_g
                else:
                    god = god_b

                move_list.append(move_to_bytes(get_move_from_string(move, god)))

            compressed_moves = b"".join(move_list)

        winner_side, result_type = map_sqlite_result(result)

        if start_pos is not None:
            start_pos_bytes = starting_position_to_bytes(start_pos)
            start_pos_int = int.from_bytes(start_pos_bytes, byteorder='big')
            start_pos = f"{start_pos_int:020b}"  # Formats as '0101...'

        # 1. Prepare Match Data
        matches_data.append({
            "match_id": m_id,
            "winner_side": winner_side,
            "result_type": result_type,
            "source_id": None,
            "timestamp": date_str,
            "starting_pos": start_pos,
            "moves": compressed_moves  # Now passing the actual bytea data
        })

        participants_data.extend([
            {
                "match_id": m_id,
                "engine_id": engines_map[eng_g],
                "god_id": gods_map[god_g_str],
                "side": True  # Gray
            },
            {
                "match_id": m_id,
                "engine_id": engines_map[eng_b],
                "god_id": gods_map[god_b_str],
                "side": False  # Blue
            }
        ])

    # 3. Batch Insert into PostgreSQL using Transactions
    print(f"Migrating {len(matches_data)} matches...")
    try:
        with pg_engine.begin() as conn:
            # Insert matches
            conn.execute(
                text("""
                    INSERT INTO tb_matches 
                        (match_id, winner_side, result_type, source_id, timestamp, starting_pos, moves)
                    VALUES 
                        (:match_id, :winner_side, :result_type, :source_id, :timestamp, CAST(:starting_pos AS bit(20)), :moves)
                    ON CONFLICT (match_id) DO NOTHING
                """),
                matches_data
            )

            # Insert participants
            conn.execute(
                text("""
                    INSERT INTO tb_match_participants 
                        (match_id, engine_id, god_id, side)
                    VALUES 
                        (:match_id, :engine_id, :god_id, :side)
                    ON CONFLICT (match_id, side) DO NOTHING
                """),
                participants_data
            )

        print("Migration complete!")

    except Exception as e:
        print(f"Error during migration: {e}")


if __name__ == "__main__":
    engine = get_engine()
    conn = get_conn()
    # insert_all_gods(engine)
    # insert_all_engines(engine)
    migrate_matches(conn, engine)