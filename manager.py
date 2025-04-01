import csv
import random
from board import God
from controller import Controller

random.seed(0)

def generate_workers():
    return random.sample(range(25), 4)


def make_position(blocks, gray_workers, blue_workers, turn, god_gray, god_blue):
    position_chars = []
    for sq in range(25):
        h = blocks[sq]
        if sq in gray_workers:
            w = 'G'
        elif sq in blue_workers:
            w = 'B'
        else:
            w = 'N'
        position_chars.append(str(h))
        position_chars.append(w)

    turn_char = '0' if turn == 1 else '1'
    god_gray_char = str(god_gray.value)
    god_blue_char = str(god_blue.value)

    return ''.join(position_chars) + turn_char + god_gray_char + god_blue_char + '0'


def run_match(path_a, path_b, god_a, god_b, starting_time, csv_writer):
    workers = generate_workers()
    pos = make_position([0]*25, workers[:2], workers[2:], 1, god_a, god_b)
    controller = Controller(pos, starting_time, starting_time, path_a, path_b, headless=True)
    result = controller.run_game()
    csv_writer.writerow([god_a.name, god_b.name, result])


def all_combinations(path_a, path_b, starting_time):
    with open("match_results.csv", "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["God_A", "God_B", "Result"])
        for god_a in God:
            for god_b in God:
                if god_a == god_b: continue
                run_match(path_a, path_b, god_a, god_b, starting_time, writer)


all_combinations("engines/Fitos_1.0_Ton.exe", "engines/Fitos_1.0_Ton.exe", 1000)