import random
import os
import concurrent.futures
from tqdm import tqdm
from typing import Tuple
from board import God
from controller import Controller
from database import get_conn, store_match
from constants import ENGINES
from manager import run_match
from util import generate_workers, make_position
# async def main():

st = 60 * 5
engine_b = "Tuning_Moth_multsh2_1.2"
engine_a = "Fitos_8.1_Cursed"

c = Controller("0N0N0N0N0N0N0N0N0N0N0N0N0G0N0B0N0G0N0N0N0N0B0N0N0N0470", st, st, ENGINES[engine_a], ENGINES[engine_b], headless=False)
c.run_game()