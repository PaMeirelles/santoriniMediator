from controller import Controller


starting_pos = "0N0N0N0N0N0N0N0G0N0N0N0N0B0G0N0N0N0B0N0N0N0N0N0N0N0010"

starting_time = 1

path = "engines/Fitos/Scout/Fitos_2.0_Scout.exe"

c = Controller(starting_pos, starting_time, starting_time, path, path)

c.run_game()