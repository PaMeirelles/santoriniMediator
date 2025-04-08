from tqdm import tqdm

from board import God
from controller import Controller
from database import get_conn, store_match
from manager import run_match

st = 1 * 60
path_a = "engines/Fitos/Trick/Fitos_6.0_Trick.exe"
path_b = "engines/Fitos/Truthless/Fitos_5.1_Truthless.exe"

name_a = "Fitos_6.0_Trick"
name_b = "Fitos_5.1_Truthless"

conn = get_conn()
cursor = conn.cursor()
for _ in tqdm(range(1000), desc="Overall Iterations"):
    for god_a in [God.ARTEMIS, God.HERMES, God.PROMETHEUS, God.DEMETER]:
        for god_b in God:
            if god_a.value == god_b.value:
                continue
            run_match(cursor, name_a, name_b, god_a, god_b, st)
            run_match(cursor, name_b, name_a, god_b, god_a, st)

            run_match(cursor, name_a, name_b, god_b, god_a, st)
            run_match(cursor, name_b, name_a, god_a, god_b, st)

            conn.commit()
conn.close()