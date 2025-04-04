import subprocess
import time
from threading import Thread
from queue import Queue
from typing import Tuple

import pygame

from view import View
from board import Board, God
from move import Move, ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, \
    MinotaurMove, PanMove, PrometheusMove

FPS = 20


def start_engine(engine_path):
    """Launch engine process if engine_path is a string, else return None."""
    if engine_path is None or engine_path == "human":
        return None
    try:
        process = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if process.poll() is not None:
            raise RuntimeError(f"Engine terminated early with code: {process.poll()}")
        return process
    except Exception as e:
        print(f"Error starting engine: {e}")
        return None


def send_command(process, command):
    if not process:
        return None
    try:
        process.stdin.write(command + "\n")
        process.stdin.flush()
        return process.stdout.readline().strip()
    except Exception as e:
        print(f"Error sending command: {e}")
        return None


def quit_engine(engine_process):
    if engine_process:
        send_command(engine_process, "quit")
        engine_process.terminate()


MOVE_CLASSES = {
    God.APOLLO: ApolloMove,
    God.ARTEMIS: ArtemisMove,
    God.ATHENA: AthenaMove,
    God.ATLAS: AtlasMove,
    God.DEMETER: DemeterMove,
    God.HEPHAESTUS: HephaestusMove,
    God.HERMES: HermesMove,
    God.MINOTAUR: MinotaurMove,
    God.PAN: PanMove,
    God.PROMETHEUS: PrometheusMove,
}


class Controller:
    def __init__(self, position, time_gray, time_blue, gray_engine_path, blue_engine_path, headless=False):
        """
        If gray_engine_path == "human" or None, that means Player 1 is controlled by a human.
        If blue_engine_path == "human" or None, that means Player 2 is controlled by a human.
        Otherwise, each side is an engine path (string).
        """
        self.board = Board(position)
        self.time_gray = time_gray  # seconds left for Player 1 (Gray)
        self.time_blue = time_blue  # seconds left for Player 2 (Blue)
        self.gray_engine_path = gray_engine_path
        self.blue_engine_path = blue_engine_path
        self.headless = headless
        self.view = None if headless else View(600, self.board)
        self.last_pos = None
        self.moves = []

    def run_engine_move(self, engine_process) -> Tuple[Move, float]:
        """
        Runs one move using an external engine. Returns (MoveObj, duration).
        Raises an exception if invalid engine output.
        """
        board_state = self.board.position_to_text()
        ready_output = send_command(engine_process, "isready")
        if ready_output != "readyok":
            raise RuntimeError(f"Engine is not ready: {ready_output}")

        position_command = f"position {board_state}"
        send_command(engine_process, position_command)

        # Convert time in seconds -> milliseconds (typical format)
        go_command = f"go gtime {round(self.time_gray * 1000)} btime {round(self.time_blue * 1000)}"
        start = time.perf_counter()
        move_output = send_command(engine_process, go_command)
        if not move_output or not move_output.startswith("bestmove"):
            raise RuntimeError(f"Invalid move output: {move_output}")

        end = time.perf_counter()
        move_text = move_output.split()[1]

        # Determine which god is moving: If board.turn==1 => Player1's god = board.gods[0], else board.gods[1]
        god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
        move_cls = MOVE_CLASSES[god]
        return move_cls.from_text(move_text), (end - start)

    def run_human_move_with_time(self, time_left: float):
        """
        Asks a human for a move, but enforces 'time_left' seconds.
        Returns (Move, actual_duration) or (None, elapsed) if time runs out or no valid move is read.

        We'll spawn a thread that does blocking input(). If time exceeds 'time_left', we treat
        it as a time loss (return None).
        """
        start = time.perf_counter()
        # Which god is moving?
        god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
        move_cls = MOVE_CLASSES[god]

        # We'll read the user input in a separate thread
        def read_user_input(q):
            try:
                user_in = input(f"Player {self.board.turn} ({god.name}), enter your move: ")
                q.put(user_in)
            except:
                q.put("")

        q = Queue()
        t = Thread(target=read_user_input, args=(q,))
        t.start()

        # Poll until user typed something or time runs out
        while t.is_alive():
            elapsed = time.perf_counter() - start
            if elapsed >= time_left:
                # Time is up
                return None, elapsed
            time.sleep(0.05)  # short sleep to reduce CPU usage

        # Thread is done => user typed something
        user_move_str = q.get()  # could be empty if an error occurred
        elapsed = time.perf_counter() - start

        if not user_move_str.strip():
            # User typed nothing => treat as invalid
            return None, elapsed

        # Try parsing the typed move
        # If the parse fails, let the caller handle it as invalid
        move_obj = move_cls.from_text(user_move_str.strip())
        return move_obj, elapsed

    def apply_move(self, move):
        self.last_pos = self.board.position_to_text()
        self.board.make_move(move)
        self.moves.append(move.move_to_text())

    def run_game(self):
        """
        Main loop that plays out the game.
        If a player is "human", we read from console with time enforcement.
        If a player is an engine path, we use concurrency + engine logic.
        """
        # Start up engines (None if "human")
        gray_engine_process = start_engine(self.gray_engine_path)
        blue_engine_process = start_engine(self.blue_engine_path)

        running = True
        winner = None
        searching_thread = None
        move_queue = Queue()
        duration_queue = Queue()
        clock = pygame.time.Clock() if not self.headless else None

        def engine_move_thread_func(process, q_move, q_dur):
            """Runs the engine on a thread and puts (MoveObj, error) plus duration in the queues."""
            try:
                mv, dur = self.run_engine_move(process)
                q_move.put((mv, None))
                q_dur.put(dur)
            except Exception as e:
                q_move.put((None, e))
                q_dur.put(0)

        def get_move_for_current_player():
            """
            Returns (move_obj, duration, error).
            If it's a human side, we do a time-limited input in the main thread (blocking).
            If it's an engine side, we return (None, None, None) so the concurrency code can pick it up.
            """
            current_turn = self.board.turn
            if current_turn == 1:
                # Gray side
                if self.gray_engine_path is None or self.gray_engine_path == "human":
                    # Time-limited human input
                    move_obj, elapsed = self.run_human_move_with_time(self.time_gray)
                    return move_obj, elapsed, None  # error can be signaled if we can't parse
                else:
                    return None, None, None  # engine side
            else:
                # Blue side
                if self.blue_engine_path is None or self.blue_engine_path == "human":
                    move_obj, elapsed = self.run_human_move_with_time(self.time_blue)
                    return move_obj, elapsed, None
                else:
                    return None, None, None

        while running and winner is None:
            if not self.headless:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                self.view.draw_board()

            # Is there an existing engine thread running?
            if (not searching_thread) or (not searching_thread.is_alive()):
                if move_queue.empty():
                    # Try to get a move from whichever side is on move
                    move_obj, duration, _ = get_move_for_current_player()
                    current_turn = self.board.turn

                    # If we got 'None' and 'duration' is definitely > 0, that likely means a human timed out or typed nothing
                    if move_obj is not None:
                        # Then we are dealing with a human's valid move
                        # Subtract time from the appropriate side
                        if current_turn == 1:
                            self.time_gray -= duration
                            if self.time_gray <= 0:
                                winner = -2  # Gray out of time
                                break
                        else:
                            self.time_blue -= duration
                            if self.time_blue <= 0:
                                winner = 2  # Blue out of time
                                break

                        # Apply the move; if invalid parse, an exception is thrown
                        try:
                            self.apply_move(move_obj)
                        except Exception as e:
                            print(f"Invalid move from user: {e}")
                            winner = -3 if current_turn == 1 else 3  # invalid move => that side loses
                            break
                    else:
                        # This means either we have an engine side or the human timed out
                        if duration is not None and duration > 0:
                            # That means it's a human who took too long or typed empty => time out
                            winner = -2 if current_turn == 1 else 2  # side that timed out loses
                            break
                        else:
                            # It's an engine side => start the engine thread
                            if current_turn == 1:
                                engine_proc = gray_engine_process
                            else:
                                engine_proc = blue_engine_process

                            searching_thread = Thread(
                                target=engine_move_thread_func,
                                args=(engine_proc, move_queue, duration_queue)
                            )
                            searching_thread.start()
                else:
                    # If we come here, that means the engine thread just finished
                    move_result, error = move_queue.get()
                    duration = duration_queue.get()
                    current_turn = self.board.turn
                    if error is not None:
                        # engine produced invalid move => that side loses
                        with open("invalid_move_log.txt", "a") as f:
                            f.write(f"Previous board state: {self.last_pos}\n")
                            f.write(f"Current board state: {self.board.position_to_text()}\n")
                            f.write(f"Error from engine: {str(error)}\n")
                        winner = -3 if current_turn == 1 else 3
                        break
                    else:
                        # valid move => deduct time
                        if current_turn == 1:
                            self.time_gray -= duration
                            if self.time_gray < 0:
                                winner = -2  # player1 out of time
                                break
                        else:
                            self.time_blue -= duration
                            if self.time_blue < 0:
                                winner = 2  # player2 out of time
                                break

                        # Now apply the move, possible board errors
                        try:
                            self.apply_move(move_result)
                        except Exception as e:
                            with open("invalid_move_log.txt", "a") as f:
                                f.write(f"Previous board state: {self.last_pos}\n")
                                f.write(f"Current board state: {self.board.position_to_text()}\n")
                                f.write(f"Error applying engine move: {str(e)}\n")
                            winner = -3 if current_turn == 1 else 3
                            break

                        # Clear out the queues
                        move_queue.queue.clear()
                        duration_queue.queue.clear()

            # After the move, check if the board is in a terminal state
            state = self.board.check_state()
            if state != 0:
                winner = state

            if not self.headless:
                self.view.draw_board()
                clock.tick(FPS)

        # Quit engines
        quit_engine(gray_engine_process)
        quit_engine(blue_engine_process)

        # Let user see final board if in GUI mode
        if not self.headless:
            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                self.view.draw_board()
                clock.tick(FPS)
            pygame.quit()

        return winner, "\n".join(self.moves)
