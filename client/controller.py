import subprocess
import time
from threading import Thread
from queue import Queue
from typing import Tuple, Dict, Optional

import pygame

from client.view import View
from game.board import Board
from database.models import God
from game.move import Move, ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, \
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
            text=True,
            bufsize=1
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
        # For setoption, we don't need to wait for a specific response line
        if command.startswith("setoption"):
            return None
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
    def __init__(self, position: str, time_gray: int, time_blue: int,
                 gray_engine_path: str, blue_engine_path: str, headless: bool = False,
                 gray_engine_params: Optional[Dict[str, float]] = None,
                 blue_engine_params: Optional[Dict[str, float]] = None):
        """
        Initializes the game controller.

        Args:
            position: The starting board position string.
            time_gray: Time in seconds for the Gray player.
            time_blue: Time in seconds for the Blue player.
            gray_engine_path: Path to the Gray player's engine or "human".
            blue_engine_path: Path to the Blue player's engine or "human".
            headless: If True, runs without a GUI.
            gray_engine_params: Optional dictionary of parameters to set for the Gray engine.
            blue_engine_params: Optional dictionary of parameters to set for the Blue engine.
        """
        self.board = Board(position)
        self.time_gray = time_gray
        self.time_blue = time_blue
        self.gray_engine_path = gray_engine_path
        self.blue_engine_path = blue_engine_path
        self.headless = headless
        self.gray_engine_params = gray_engine_params
        self.blue_engine_params = blue_engine_params
        self.view = None if headless else View(600, self.board)
        self.last_pos = None
        self.moves = []

    def _setup_engine_params(self, engine_process, params: Dict[str, float]):
        """Sends setoption commands to configure an engine."""
        if not engine_process or not params:
            return
        # It's good practice to ensure the engine is ready before setting options
        ready_output = send_command(engine_process, "isready")
        if ready_output != "readyok":
            raise RuntimeError(f"Engine not ready for setup: {ready_output}")

        for name, value in params.items():
            send_command(engine_process, f"setoption name {name} value {value}")

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
        end = time.perf_counter()

        if not move_output or not move_output.startswith("bestmove"):
            raise RuntimeError(f"Invalid move output: '{move_output}'")

        move_text = move_output.split()[1]
        god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
        move_cls = MOVE_CLASSES[god]
        return move_cls.from_text(move_text), (end - start)

    def run_human_move_with_time(self, time_left: float):
        """
        Asks a human for a move, but only once, enforcing 'time_left' seconds.
        """
        start = time.perf_counter()
        god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
        move_cls = MOVE_CLASSES[god]

        q = Queue()
        t = Thread(target=lambda q_ref: q_ref.put(input(f"Player {self.board.turn} ({god.name}), enter your move: ")),
                   args=(q,))
        t.daemon = True
        t.start()

        t.join(timeout=time_left)
        elapsed = time.perf_counter() - start

        if q.empty():
            return None, elapsed

        user_move_str = q.get()
        if not user_move_str.strip():
            return None, elapsed

        move_obj = move_cls.from_text(user_move_str.strip())
        return move_obj, elapsed

    def get_legal_human_move(self, time_left: float):
        total_used = 0.0
        while True:
            remain = time_left - total_used
            if remain <= 0:
                return None, total_used

            start_attempt = time.perf_counter()
            move_obj, used_local = None, 0.0
            try:
                move_obj, used_local = self.run_human_move_with_time(remain)
                if not self.board.move_is_valid(move_obj):
                    raise ValueError("Move is not legal")
            except Exception as parse_err:
                used_local = time.perf_counter() - start_attempt
                move_obj = None
                print(f"Invalid input or illegal move: {parse_err}")

            total_used += used_local
            if total_used >= time_left:
                return None, total_used

            if move_obj is None:
                print("Empty or invalid move attempt. Please try again.")
                continue
            return move_obj, total_used

    def apply_move(self, move):
        self.last_pos = self.board.position_to_text()
        self.board.make_move(move)
        self.moves.append(move.move_to_text())

    def run_game(self):
        gray_engine_process = start_engine(self.gray_engine_path)
        blue_engine_process = start_engine(self.blue_engine_path)

        # --- NEW: Setup engine parameters after launch ---
        self._setup_engine_params(gray_engine_process, self.gray_engine_params)
        self._setup_engine_params(blue_engine_process, self.blue_engine_params)
        # ------------------------------------------------

        running = True
        winner = None
        searching_thread = None
        move_queue = Queue()
        duration_queue = Queue()
        clock = pygame.time.Clock() if not self.headless else None

        def engine_move_thread_func(process, q_move, q_dur):
            try:
                mv, dur = self.run_engine_move(process)
                q_move.put((mv, None))
                q_dur.put(dur)
            except Exception as e:
                q_move.put((None, e))
                q_dur.put(0)

        def get_move_for_current_player():
            current_turn = self.board.turn
            is_gray_human = self.gray_engine_path is None or self.gray_engine_path == "human"
            is_blue_human = self.blue_engine_path is None or self.blue_engine_path == "human"

            if current_turn == 1 and is_gray_human:
                return self.get_legal_human_move(self.time_gray) + (None,)
            elif current_turn == -1 and is_blue_human:
                return self.get_legal_human_move(self.time_blue) + (None,)
            else:
                return None, None, None

        while running and winner is None:
            if not self.headless:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: running = False
                self.view.draw_board(self.time_gray, self.time_blue)

            if not searching_thread or not searching_thread.is_alive():
                if move_queue.empty():
                    move_obj, duration, _ = get_move_for_current_player()
                    current_turn = self.board.turn

                    if move_obj is not None:
                        if current_turn == 1:
                            self.time_gray -= duration
                        else:
                            self.time_blue -= duration

                        if self.time_gray <= 0: winner = -2; break
                        if self.time_blue <= 0: winner = 2; break
                        self.apply_move(move_obj)
                    else:
                        is_engine_turn = (current_turn == 1 and self.gray_engine_path not in ["human", None]) or \
                                         (current_turn == -1 and self.blue_engine_path not in ["human", None])
                        if is_engine_turn:
                            engine_proc = gray_engine_process if current_turn == 1 else blue_engine_process
                            searching_thread = Thread(target=engine_move_thread_func,
                                                      args=(engine_proc, move_queue, duration_queue))
                            searching_thread.start()
                        else:
                            winner = -2 if current_turn == 1 else 2
                            break
                else:
                    move_result, error = move_queue.get()
                    duration = duration_queue.get()
                    current_turn = self.board.turn
                    if error is not None:
                        print(f"Engine error: {error}")
                        winner = -3 if current_turn == 1 else 3
                        break

                    if current_turn == 1:
                        self.time_gray -= duration
                    else:
                        self.time_blue -= duration

                    if self.time_gray < 0: winner = -2; break
                    if self.time_blue < 0: winner = 2; break

                    try:
                        self.apply_move(move_result)
                    except Exception as e:
                        print(f"Error applying engine move: {e}")
                        winner = -3 if current_turn == 1 else 3
                        break
                    move_queue.queue.clear()
                    duration_queue.queue.clear()

            state = self.board.check_state()
            if state != 0:
                winner = state

            if not self.headless:
                clock.tick(FPS)

        quit_engine(gray_engine_process)
        quit_engine(blue_engine_process)

        if not self.headless and winner is not None:
            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT: running = False
                self.view.draw_board(self.time_gray, self.time_blue)
                clock.tick(FPS)
            pygame.quit()

        return winner, "\n".join(self.moves)
