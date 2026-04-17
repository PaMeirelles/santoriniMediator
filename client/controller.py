import subprocess
import time
import queue
from threading import Thread
from queue import Queue
from typing import Tuple, Dict, Optional

import pygame

from client.view import View
from game.board import Board
from database.models import God, GameResult
from game.move import Move, ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, \
    MinotaurMove, PanMove, PrometheusMove

FPS = 20


def start_engine(engine_path):
    if engine_path is None or engine_path == "human":
        return None
    try:
        process = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
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
        if command.startswith("setoption") or command == "quit":
            return None
        return process.stdout.readline().strip()
    except Exception as e:
        print(f"Error sending command: {e}")
        return None


def quit_engine(engine_process):
    if engine_process:
        send_command(engine_process, "quit")
        try:
            engine_process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            engine_process.terminate()
            engine_process.wait()

        for pipe in (engine_process.stdin, engine_process.stdout, engine_process.stderr):
            if pipe:
                try:
                    pipe.close()
                except Exception:
                    pass


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


def _setup_engine_params(engine_process, params: Dict[str, float]):
    if not engine_process or not params:
        return
    ready_output = send_command(engine_process, "isready")
    if ready_output != "readyok":
        raise RuntimeError(f"Engine not ready for setup: {ready_output}")
    for name, value in params.items():
        send_command(engine_process, f"setoption name {name} value {value}")


def _pump_events():
    """Processes Pygame events. Returns True if user triggered QUIT."""
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return True
    return False


class Controller:
    def __init__(self, position: str, time_gray: int, time_blue: int,
                 gray_engine_path: str, blue_engine_path: str, headless: bool = False,
                 gray_engine_params: Optional[Dict[str, float]] = None,
                 blue_engine_params: Optional[Dict[str, float]] = None):

        self.board = Board(position)
        self.time_gray = time_gray
        self.time_blue = time_blue

        self.gray_engine_path = gray_engine_path
        self.blue_engine_path = blue_engine_path
        self.gray_engine_params = gray_engine_params
        self.blue_engine_params = blue_engine_params

        self.headless = headless
        self.view = None if headless else View(600, self.board)
        self.last_pos = None
        self.moves: list[Move] = []

        # Engine state variables (moved to instance level for easier cleanup)
        self.gray_process = None
        self.blue_process = None
        self.searching_thread = None
        self.move_queue = Queue()
        self.duration_queue = Queue()

    # --- Engine Setup & Teardown ---

    def _init_engines(self):
        """Starts engines and applies configuration parameters."""
        self.gray_process = start_engine(self.gray_engine_path)
        self.blue_process = start_engine(self.blue_engine_path)
        _setup_engine_params(self.gray_process, self.gray_engine_params)
        _setup_engine_params(self.blue_process, self.blue_engine_params)

    def _cleanup_engines(self):
        """Safely shuts down both engines."""
        quit_engine(self.gray_process)
        quit_engine(self.blue_process)

    # --- Move Execution Methods ---

    def run_engine_move(self, engine_process) -> Tuple[Move, float]:
        board_state = self.board.position_to_text()
        ready_output = send_command(engine_process, "isready")
        if ready_output != "readyok":
            raise RuntimeError(f"Engine is not ready: {ready_output}")

        send_command(engine_process, f"position {board_state}")
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
        start = time.perf_counter()
        god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
        move_cls = MOVE_CLASSES[god]

        q = Queue()
        t = Thread(target=lambda q_ref: q_ref.put(input(f"Player {self.board.turn} ({god.name}), enter your move: ")),
                   args=(q,), daemon=True)
        t.start()
        t.join(timeout=time_left)

        elapsed = time.perf_counter() - start
        if q.empty() or not (user_move_str := q.get().strip()):
            return None, elapsed

        return move_cls.from_text(user_move_str), elapsed

    def get_legal_human_move(self, time_left: float):
        total_used = 0.0
        while True:
            remain = time_left - total_used
            if remain <= 0:
                return None, total_used

            start_attempt = time.perf_counter()
            try:
                move_obj, used_local = self.run_human_move_with_time(remain)
                if move_obj and not self.board.move_is_valid(move_obj):
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
        self.moves.append(move)

    # --- Game Loop Mechanics ---

    def _engine_thread_wrapper(self, process):
        """Wrapper to execute the engine move and put results in the queue safely."""
        try:
            mv, dur = self.run_engine_move(process)
            self.move_queue.put((mv, None))
            self.duration_queue.put(dur)
        except Exception as e:
            self.move_queue.put((None, e))
            self.duration_queue.put(0)

    def _start_engine_search(self):
        """Spawns a background thread to calculate the next engine move."""
        is_gray_turn = self.board.turn == 1
        current_engine = self.gray_process if is_gray_turn else self.blue_process

        self.searching_thread = Thread(
            target=self._engine_thread_wrapper,
            args=(current_engine,),
            daemon=True
        )
        self.searching_thread.start()

    def _poll_engine(self):
        """Checks the queue for an engine response, with a timeout failsafe."""
        max_wait = (self.time_gray if self.board.turn == 1 else self.time_blue) + 5.0

        try:
            # Will wait until the engine finishes OR it exceeds the max wait time
            move_result, error = self.move_queue.get(timeout=max_wait)
            duration = self.duration_queue.get()
        except queue.Empty:
            print(f"Engine timeout/freeze detected for Player {self.board.turn}. Forfeiting.")
            return -3 if self.board.turn == 1 else 3  # Return forfeit state

        if error is not None:
            print(f"Engine error: {error}")
            return -3 if self.board.turn == 1 else 3

        # Apply time and move
        if self.board.turn == 1:
            self.time_gray -= duration
        else:
            self.time_blue -= duration

        if self.time_gray < 0: return -2
        if self.time_blue < 0: return 2

        try:
            self.apply_move(move_result)
        except Exception as e:
            print(f"Error applying engine move: {e}")
            return -3 if self.board.turn == 1 else 3

        self.move_queue.queue.clear()
        self.duration_queue.queue.clear()
        return None  # No winner yet

    def _handle_turn(self):
        """Manages the logic for a single turn based on who is playing."""
        current_turn = self.board.turn
        is_gray_human = self.gray_engine_path in ["human", None]
        is_blue_human = self.blue_engine_path in ["human", None]
        is_human_turn = (current_turn == 1 and is_gray_human) or (current_turn == -1 and is_blue_human)

        if is_human_turn:
            time_left = self.time_gray if current_turn == 1 else self.time_blue
            move_obj, duration = self.get_legal_human_move(time_left)

            if move_obj is not None:
                if current_turn == 1:
                    self.time_gray -= duration
                else:
                    self.time_blue -= duration

                if self.time_gray <= 0: return -2
                if self.time_blue <= 0: return 2

                self.apply_move(move_obj)
            else:
                return -2 if current_turn == 1 else 2  # Timeout / forfeit
        else:
            # Engine Turn
            if not self.searching_thread or not self.searching_thread.is_alive():
                self._start_engine_search()
            else:
                # The thread is running, check if it has yielded a result yet
                return self._poll_engine()

        return None

    def run_game(self) ->tuple[int, list[Move]]:
        """The main game loop. Now drastically simplified."""
        self._init_engines()
        winner = None
        clock = pygame.time.Clock() if not self.headless else None

        while winner is None:
            # 1. Update UI
            if not self.headless:
                if _pump_events():
                    break  # User closed the window
                self.view.draw_board(self.time_gray, self.time_blue)

            # 2. Process Turn
            turn_result = self._handle_turn()
            if turn_result is not None:
                winner = turn_result

            # 3. Check Board State
            state = self.board.check_state()
            if state != 0:
                winner = state

            # 4. Tick Clock
            if not self.headless:
                clock.tick(FPS)

        # Game Over Cleanup
        self._cleanup_engines()

        if not self.headless and winner is not None:
            # Post-game screen loop
            running = True
            while running:
                running = not _pump_events()
                self.view.draw_board(self.time_gray, self.time_blue)
                clock.tick(FPS)
            pygame.quit()

        return winner, self.moves