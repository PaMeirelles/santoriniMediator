import subprocess
from board import Board
from move import Move


def start_engine(engine_path):
    try:
        process = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,  # Ensure text mode for input/output
            universal_newlines=True  # Same as text=True, for older Python versions
        )

        # Check if the process started successfully
        if process.poll() is None:  # poll() returns None if process is still running
            print("Engine started successfully.")
        else:
            raise RuntimeError(f"Engine terminated early with code: {process.poll()}")

        return process

    except Exception as e:
        print(f"Error starting engine: {e}")
        return None


def send_command(process, command):
    """
    Send a command to the engine and retrieve the output.
    """
    try:
        process.stdin.write(command + "\n")
        process.stdin.flush()
        output = process.stdout.readline().strip()
        return output
    except Exception as e:
        print(f"Error sending command: {e}")
        return None


def quit_engine(engine_process):
    """
    Send the 'quit' command to the engine and close the process.
    """
    send_command(engine_process, "quit")
    engine_process.terminate()


class Controller:
    def __init__(self, position, time_gray, time_blue, gray_engine_path, blue_engine_path):
        self.board = Board(position)  # Initialize the board with the position
        self.time_gray = time_gray  # Time limit for the gray player
        self.time_blue = time_blue  # Time limit for the blue player
        self.gray_engine_path = gray_engine_path  # Path to the gray player's C++ engine
        self.blue_engine_path = blue_engine_path  # Path to the blue player's C++ engine

    def run_engine(self, engine_process) -> Move:
        """
        Send the board position and time control to the engine and get the best move.
        """
        board_state = self.board.position_to_text()

        # Check if the engine is ready
        ready_output = send_command(engine_process, "isready")
        if ready_output != "readyok":
            raise RuntimeError(f"Engine is not ready: {ready_output}")

        # Send the position to the engine
        position_command = f"position {board_state}"
        send_command(engine_process, position_command)

        # Send the 'go' command with time control
        go_command = f"go gtime {self.time_gray} btime {self.time_blue}"
        move_output = send_command(engine_process, go_command)

        # Extract the move from the engine's output
        if move_output.startswith("bestmove"):
            return Move(move_output.split()[1])
        else:
            raise RuntimeError(f"Invalid move output: {move_output}")

    def apply_move(self, move):
        """
        Apply the move to the board.
        :param move: The move received from the engine.
        """
        self.board.make_move(move)  # Assuming Board has apply_move method

    def run_game(self):
        """
        Main game loop: runs until the game ends.
        """
        # Start both engines
        gray_engine_process = start_engine(self.gray_engine_path)
        blue_engine_process = start_engine(self.blue_engine_path)

        if gray_engine_process is None or blue_engine_process is None:
            print("Failed to start one or both engines.")
            return

        while self.board.check_state() == 0:
            if self.board.turn == 1:
                move = self.run_engine(gray_engine_process)
            else:
                move = self.run_engine(blue_engine_process)

            if move is None:
                print(f"Error: Could not retrieve a valid move for {self.board.turn}")
                break
            print(move.move_to_text())
            self.apply_move(move)


        # Quit both engines
        quit_engine(gray_engine_process)
        quit_engine(blue_engine_process)

        print("Game over!")
        winner = self.board.check_state()  # Assuming Board has a get_winner method
        print(f"Winner: {winner}")