import random
from board import God
from controller import Controller
from database import get_conn
from manager import make_position, run_match

controller = Controller("0N0B0N0N0B0N0N0N0N0N0N0N0G0N0N0N0N0N0G0N0N0N0N0N0N0160", 10, 10,
                        "human",
                        "engines/Fitos/Atium/Fitos_4.6_Atium.exe", headless=False)

controller.run_game()