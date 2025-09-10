import pandas as pd
from tqdm import tqdm

from game.board import Board, God
from analysis.database import get_conn
from game.move import ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, \
    MinotaurMove, PanMove, PrometheusMove

MOVE_CLASSES = {
    God.APOLLO: ApolloMove,
    God.ARTEMIS: ArtemisMove,
    God.ATHENA: AthenaMove,
    God.ATLAS: AtlasMove,
    God.DEMETER: DemeterMove,
    God.HEPHAESTUS: HephaestusMove,
    God.HERMES: HermesMove,
    God.MINOTAUR: MinotaurMove,
    God.PAN: PanMove,
    God.PROMETHEUS: PrometheusMove,
}

conn = get_conn()

engine_list = [
    # 'Fitos_6.1_Trick',
    # 'Fitos_6.2_Trick',
    # 'Fitos_6.3_Trick',
    # 'Fitos_7.0_Time',
    # 'Fitos_7.1_Time',
    # 'Fitos_7.2_Time',
    # 'Fitos_8.0_Cursed',
    # 'Fitos_8.1_Cursed',
    # 'Fitos_9.4_Moth',
    # 'Fitos_10.5_Astro',
    'Fitos_11.0_Hyperion']

placeholders = "', '".join(engine_list)

query = f"""
    SELECT Id, result AS Result, Starting_pos, moves AS Moves
    FROM TB_MATCHES
    WHERE Engine_G IN ('{placeholders}')
      AND Engine_B IN ('{placeholders}')
"""
df = pd.read_sql_query(query, conn)
cursor = conn.cursor()

insert_query = """
INSERT OR IGNORE INTO TB_POSITIONS (position, match_id, move_count, result)
VALUES (?, ?, ?, ?)
"""

for index, row in tqdm(df.iterrows(), total=len(df)):
    match_id = row['Id']
    moves = row['Moves'].strip().split('\n')
    board = Board(row['Starting_pos'])
    result = row['Result']

    cursor.execute(insert_query, (board.position_to_text(), match_id, 0, result))

    for i, move_str in enumerate(moves, start=1):
        if not move_str.strip():
            continue

        current_turn = board.turn
        god = board.gods[0] if current_turn == 1 else board.gods[1]
        move_cls = MOVE_CLASSES[god]

        move = move_cls.from_text(move_str.strip())
        board.make_move(move)

        cursor.execute(insert_query, (board.position_to_text(), match_id, i, result))


conn.commit()
conn.close()
