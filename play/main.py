from gamePython.board import God
from analysis.database import get_conn
from play.manager import run_match

# async def main():

st = 60
engine_a = "Fitos_13.1_Legacy"
engine_b = "Fitos_14.8_Echo"
god_a = God.PROMETHEUS
god_b = God.MINOTAUR
pos = "0N0N0N0N0N0N0N0B0N0N0N0B0N0G0N0N0N0G0N0N0N0N0N0N0N0090"
conn = get_conn()
cursor = conn.cursor()

run_match(cursor, engine_a, engine_b, god_a, god_b, st, pos, headless=False)
# store_match(cursor, god_a, god_b, engine_a, engine_b, 18, st, "", pos)