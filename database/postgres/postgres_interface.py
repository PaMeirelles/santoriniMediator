import os
from typing import Tuple, Dict
from dotenv import load_dotenv
from sqlalchemy import text, Engine, create_engine
from database.models import Match, ResultType, god_to_string, GameParams, string_to_god
from database.data_compression import move_to_bytes, starting_position_to_bytes

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

def reconstruct_position_str(bitstring: str | None, gray_god: str, blue_god: str) -> str | None:
    if bitstring is None: return None

    w0 = int(bitstring[0:5], 2)
    w1 = int(bitstring[5:10], 2)
    w2 = int(bitstring[10:15], 2)
    w3 = int(bitstring[15:20], 2)

    pos_list = []
    for i in range(25):
        if i in (w0, w1):
            pos_list.append("0G")
        elif i in (w2, w3):
            pos_list.append("0B")
        else:
            pos_list.append("0N")

    g1_id = string_to_god(gray_god).value
    g2_id = string_to_god(blue_god).value

    return "".join(pos_list) + "0" + str(g1_id) + str(g2_id) + "0"


def get_played_matches_pg(pg_engine: Engine) -> set[GameParams]:
    query = text("""
        SELECT 
            m.starting_pos::VARCHAR AS starting_pos, 
            eng_gray.engine_name AS gray_engine, 
            eng_blue.engine_name AS blue_engine,
            god_gray.god_name AS gray_god,
            god_blue.god_name AS blue_god,
            part_gray.starting_time AS gray_time,
            part_blue.starting_time AS blue_time
        FROM tb_matches m
        JOIN tb_match_participants part_gray 
            ON m.match_id = part_gray.match_id AND part_gray.side = TRUE
        JOIN tb_engines eng_gray 
            ON part_gray.engine_id = eng_gray.engine_id
        JOIN tb_gods god_gray
            ON part_gray.god_id = god_gray.god_id
        JOIN tb_match_participants part_blue 
            ON m.match_id = part_blue.match_id AND part_blue.side = FALSE
        JOIN tb_engines eng_blue 
            ON part_blue.engine_id = eng_blue.engine_id
        JOIN tb_gods god_blue
            ON part_blue.god_id = god_blue.god_id
    """)

    with pg_engine.connect() as conn:
        result = conn.execute(query)
        return {
            GameParams(
                reconstruct_position_str(row.starting_pos, row.gray_god, row.blue_god),
                row.gray_engine,
                row.blue_engine,
                row.gray_god,
                row.blue_god,
                row.gray_time,
                row.blue_time
            )
            for row in result
        }


def store_match_pg(
        conn,
        match: Match,
        gods_map: Dict[str, int],
        engines_map: Dict[str, int]
):
    start_pos_bytes = starting_position_to_bytes(match.starting_pos)
    start_pos_int = int.from_bytes(start_pos_bytes, byteorder='big')
    start_pos_bitstring = f"{start_pos_int:020b}"

    compressed_moves = b"".join([move_to_bytes(m) for m in match.moves])

    result_map = {
        ResultType.NORMAL_WIN: 'N',
        ResultType.TIMEOUT: 'T',
        ResultType.ILLEGAL_MOVE: 'I'
    }
    db_result_type = result_map.get(match.result_type, 'N')

    match_query = text("""
        INSERT INTO tb_matches 
            (winner_side, result_type, timestamp, starting_pos, moves)
        VALUES 
            (:winner_side, :result_type, :timestamp, CAST(:starting_pos AS bit(20)), :moves)
        RETURNING match_id
    """)

    result = {
        "winner_side": match.winner,
        "result_type": db_result_type,
        "timestamp": match.played_at,
        "starting_pos": start_pos_bitstring,
        "moves": compressed_moves
    }

    match_id = conn.execute(match_query, result).scalar()

    participants_query = text("""
        INSERT INTO tb_match_participants (match_id, engine_id, god_id, side, starting_time)
        VALUES (:m_id, :e_id, :g_id, :side, :starting_time)
    """)

    gray_player = match.players[0]
    blue_player = match.players[1]

    participants_data = [
        {
            "m_id": match_id,
            "e_id": engines_map[gray_player.engine],
            "g_id": gods_map[god_to_string(gray_player.god)],
            "side": True,
            "starting_time": match.time_ms[0]
        },
        {
            "m_id": match_id,
            "e_id": engines_map[blue_player.engine],
            "g_id": gods_map[god_to_string(blue_player.god)],
            "side": False,
            "starting_time": match.time_ms[1]
        }
    ]

    conn.execute(participants_query, participants_data)