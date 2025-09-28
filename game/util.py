import random

INVALID_MOVE_FILE = "../data/invalid_moves.txt"

def make_position(blocks, gray_workers, blue_workers, turn, god_gray, god_blue):
    """
    Helper function that builds a position string for your Controller.
    """
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

def generate_workers():
    return random.sample(range(25), 4)

def log_invalid_move(move_text: str):
    with open(INVALID_MOVE_FILE, 'a') as f:
        f.write(move_text + '\n')