import random
import os
import concurrent.futures
from tqdm import tqdm
from typing import Tuple
from board import God
from controller import Controller
from database import get_conn, store_match
from constants import ENGINES
from manager import run_match, run_single_match
from util import generate_workers, make_position
# async def main():

st = 60 * 30
engine_a = "Fitos_13.1_Legacy"
engine_b = "Fitos_12.0_Never"
god_a = God.MINOTAUR
god_b = God.PROMETHEUS

run_single_match(engine_a, engine_b, god_a, god_b, st, headless=False)