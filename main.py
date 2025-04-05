from controller import Controller
from database import get_conn, store_match

st = 15 * 60
pos = "0N0N0B0N0G0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0B0G0500"
path = "engines/Fitos/Atium/Fitos_4.6_Atium.exe"

controller = Controller(pos, st, st, path, "human", headless=False)

result, moves = controller.run_game()
conn = get_conn()
cursor = conn.cursor()
store_match(cursor, controller.board.gods[0], controller.board.gods[1], "Fitos_4.6_Atium", "rmeirelles",result, st, moves, pos)
conn.commit()
conn.close()