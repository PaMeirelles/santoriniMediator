import pygame

from replay import load_match_from_db, Replay

match_id = 36724

god_g, god_b, moves_list, pos = load_match_from_db(match_id)

# Initialize pygame and the replay system.
screen_size = 800
pygame.init()
pygame.key.set_repeat(200, 50)
replay = Replay(pos, moves_list, screen_size)
replay.run()