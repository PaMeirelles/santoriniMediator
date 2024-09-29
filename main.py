from controller import Controller


starting_pos = "0N0N0N0N0N0N0N0G0N0N0N0N0B0G0N0N0N0B0N0N0N0N0N0N0N0"

starting_time = 60

cyan_path = "engines/cyan.exe"

c = Controller(starting_pos, starting_time, starting_time, cyan_path, cyan_path)

c.run_game()