import random
from board import God
from controller import Controller
from database import get_conn
from manager import make_position, run_match

conn = get_conn()
cursor = conn.cursor()
run_match(cursor, "Fitos_4.0_Atium", "Fitos_4.0_Atium", God.MINOTAUR, God.HERMES, 60)
run_match(cursor, "Fitos_4.0_Atium", "Fitos_4.0_Atium", God.MINOTAUR, God.PROMETHEUS, 60)
conn.commit()
ida = [God.PAN, God.PROMETHEUS]
for ga in ida:
    for gb in God:
        run_match(cursor, "Fitos_4.0_Atium", "Fitos_4.0_Atium", ga, gb, 60)
        conn.commit()
conn.close()
