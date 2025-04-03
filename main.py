import random
from board import God
from controller import Controller
from manager import make_position

blocks = [0] * 25
def generate_workers():
    return random.sample(range(25), 4)
workers = generate_workers()
starting_pos = make_position(blocks, workers[:2], workers[2:], 1, God.DEMETER, God.PAN)

starting_time = 60 * 3

path = "engines/Fitos/Atium/Fitos_4.0_Atium.exe"

c = Controller(starting_pos, starting_time, starting_time, path, path)

c.run_game()