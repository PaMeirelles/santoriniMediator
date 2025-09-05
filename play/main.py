from game.board import God
from analysis.database import get_conn, store_match
from play.manager import run_match, play_least_played_forever

# async def main():

st = 60 * .1
engine_b = "Paladini_3.0_Summit"
engine_a = "Paladini_4.0.4_Mystic"
god_a = God.APOLLO
god_b = God.HERMES
pos = "0N0N0N0N0N0N0N0N0G0N0N0B0G0N0N0N0N0B0N0N0N0N0N0N0N0540"
conn = get_conn()
cursor = conn.cursor()

r = run_match(cursor, engine_a, engine_b, god_a, god_b, st, pos, headless=False)
# store_match(cursor, god_a, god_b, engine_a, engine_b, r, st, "", pos)
# play_least_played_forever(engine_a, engine_b)
# conn.commit()
# conn.close()