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

        go_command = f"go gtime {round(self.time_gray * 1000)} btime {round(self.time_blue * 1000)}"
        start = time.perf_counter()
        move_output = send_command(engine_process, go_command)
        if not move_output or not move_output.startswith("bestmove"):
            raise RuntimeError(f"Invalid move output: {move_output}")

        end = time.perf_counter()
        move_text = move_output.split()[1]

        # Determine which god is moving
        god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
        move_cls = MOVE_CLASSES[god]
        return move_cls.from_text(move_text), (end - start)

    def run_human_move_with_time(self, time_left: float):
        """
        Asks a human for a move, but only once, enforcing 'time_left' seconds.
        Returns (MoveObj, used_time) or (None, used_time) if time runs out or user typed nothing.

        If the user typed an invalid format (cannot be parsed), that will raise an exception
        that you can catch in the caller to re-prompt them.
        """
        start = time.perf_counter()
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
                # Time is up => we return None
                return None, elapsed
            time.sleep(0.05)  # short sleep to reduce CPU usage

        # Thread is done => user typed something
        user_move_str = q.get()  # could be empty if an error occurred
        elapsed = time.perf_counter() - start

        # If user typed nothing, treat as invalid
        if not user_move_str.strip():
            return None, elapsed

        # Attempt to parse. Could raise an exception if input is invalid format.
        move_obj = move_cls.from_text(user_move_str.strip())
        return move_obj, elapsed

    def get_legal_human_move(self, time_left: float):
        total_used = 0.0
        while True:
            remain = time_left - total_used
            if remain <= 0:
                return None, total_used

            # We'll measure attempt time on our own,
            # so we always know how much time to add to 'total_used'
            start_attempt = time.perf_counter()

            move_obj = None
            used_local = 0.0
            try:
                move_obj, used_local = self.run_human_move_with_time(remain)
                if not self.board.move_is_valid(move_obj):
                    raise ValueError("Move is not legal")
            except Exception as parse_err:
                used_local = time.perf_counter() - start_attempt
                move_obj = None
                print(f"Invalid input parse: {parse_err}")

            # In either case, add the time used in this attempt
            total_used += used_local

            # If time is up:
            if total_used >= time_left:
                return None, total_used

            # Check if move_obj is None => user typed nothing or timed out or parse error
            if move_obj is None:
                print("Empty or invalid move attempt. Please try again (if time remains).")
                continue
            return move_obj, total_used


    def apply_move(self, move):
        """Apply the move to the board and record it."""
        self.last_pos = self.board.position_to_text()
        self.board.make_move(move)
        self.moves.append(move.move_to_text())

    def run_game(self):
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
            If it's a human side, we do repeated prompts until a LEGAL move or time out.
            If it's an engine side, we return (None, None, None) so the concurrency code can pick it up.
            """
            current_turn = self.board.turn
            if current_turn == 1:
                # Gray side
                if self.gray_engine_path is None or self.gray_engine_path == "human":
                    move_obj, used_time = self.get_legal_human_move(self.time_gray)
                    return move_obj, used_time, None
                else:
                    return None, None, None  # engine side
            else:
                # Blue side
                if self.blue_engine_path is None or self.blue_engine_path == "human":
                    move_obj, used_time = self.get_legal_human_move(self.time_blue)
                    return move_obj, used_time, None
                else:
                    return None, None, None

        while running and winner is None:
            # Handle GUI events
            if not self.headless:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                self.view.draw_board(self.time_gray, self.time_blue)

            # Is there an existing engine thread running?
            if not searching_thread or not searching_thread.is_alive():
                if move_queue.empty():
                    # => we are ready to get the next move from the current player
                    move_obj, duration, _ = get_move_for_current_player()
                    current_turn = self.board.turn

                    if move_obj is not None:
                        # We have a valid, legal move from the user
                        # Deduct the time used
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
                        self.apply_move(move_obj)
                    else:
                        # Means either time out or it's an engine side
                        # 1) If a user truly timed out => we detect it
                        #    (move_obj is None, duration>0, and side was human).
                        # 2) If it's an engine side => we spin up the thread
                        # Let's check if current side is engine or time out:
                        if (current_turn == 1 and self.gray_engine_path != "human" and self.gray_engine_path is not None) \
                           or (current_turn == -1 and self.blue_engine_path != "human" and self.blue_engine_path is not None):
                            # It's an engine => run engine thread
                            engine_proc = gray_engine_process if current_turn == 1 else blue_engine_process
                            searching_thread = Thread(
                                target=engine_move_thread_func,
                                args=(engine_proc, move_queue, duration_queue)
                            )
                            searching_thread.start()
                        else:
                            # It's a human side that ended up with None => time out
                            winner = -2 if current_turn == 1 else 2
                            break
                else:
                    # The engine thread just finished
                    move_result, error = move_queue.get()
                    duration = duration_queue.get()
                    current_turn = self.board.turn
                    if error is not None:
                        # Engine produced invalid move => that side loses
                        with open("invalid_move_log.txt", "a") as f:
                            f.write(f"Previous board state: {self.last_pos}\n")
                            f.write(f"Current board state: {self.board.position_to_text()}\n")
                            f.write(f"Error from engine: {str(error)}\n")
                        winner = -3 if current_turn == 1 else 3
                        break
                    else:
                        # Valid move => deduct time
                        if current_turn == 1:
                            self.time_gray -= duration
                            if self.time_gray < 0:
                                winner = -2
                                break
                        else:
                            self.time_blue -= duration
                            if self.time_blue < 0:
                                winner = 2
                                break
                        # Apply move
                        try:
                            self.apply_move(move_result)
                        except Exception as e:
                            with open("invalid_move_log.txt", "a") as f:
                                f.write(f"Previous board state: {self.last_pos}\n")
                                f.write(f"Current board state: {self.board.position_to_text()}\n")
                                f.write(f"Error applying engine move: {str(e)}\n")
                            winner = -3 if current_turn == 1 else 3
                            break

                        move_queue.queue.clear()
                        duration_queue.queue.clear()

            # After the move, check if the board is in a terminal state
            state = self.board.check_state()
            if state != 0:
                winner = state

            if not self.headless:
                self.view.draw_board(self.time_gray, self.time_blue)
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
                self.view.draw_board(self.time_gray, self.time_blue)
                clock.tick(FPS)
            pygame.quit()

        return winner, "\n".join(self.moves)
