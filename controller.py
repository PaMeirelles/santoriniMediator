import subprocess
import time
from threading import Thread
from queue import Queue
from typing import Tuple

import pygame

from view import View
from board import Board, God
from move import Move, ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, MinotaurMove, PanMove, PrometheusMove

FPS = 20

def start_engine(engine_path):
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
    try:
        process.stdin.write(command + "\n")
        process.stdin.flush()
        return process.stdout.readline().strip()
    except Exception as e:
        print(f"Error sending command: {e}")
        return None

def quit_engine(engine_process):
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
        self.board = Board(position)
        self.time_gray = time_gray
        self.time_blue = time_blue
        self.gray_engine_path = gray_engine_path
        self.blue_engine_path = blue_engine_path
        self.headless = headless
        self.view = None if headless else View(600, self.board)

    def run_engine(self, engine_process) -> Tuple[Move, float]:
        board_state = self.board.position_to_text()
        ready_output = send_command(engine_process, "isready")
        if ready_output != "readyok":
            raise RuntimeError(f"Engine is not ready: {ready_output}")

        position_command = f"position {board_state}"
        send_command(engine_process, position_command)

        go_command = f"go gtime {round(self.time_gray * 1000)} btime {round(self.time_blue * 1000)}"
        start = time.perf_counter()
        move_output = send_command(engine_process, go_command)

        if move_output.startswith("bestmove"):
            end = time.perf_counter()
            move_text = move_output.split()[1]
            god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
            move_cls = MOVE_CLASSES[god]
            return move_cls.from_text(move_text), end - start
        else:
            raise RuntimeError(f"Invalid move output: {move_output}")

    def apply_move(self, move):
        self.board.make_move(move)

    def run_game(self):
        gray_engine_process = start_engine(self.gray_engine_path)
        blue_engine_process = start_engine(self.blue_engine_path)

        if gray_engine_process is None or blue_engine_process is None:
            print("Failed to start one or both engines.")
            return

        running = True
        winner = None
        searching_thread = None
        move_queue = Queue()
        duration_queue = Queue()
        clock = pygame.time.Clock() if not self.headless else None

        # This inner function now returns a tuple: (move, error). If error is not None, then an exception occurred.
        def get_move(process, q1, q2):
            try:
                mv, dur = self.run_engine(process)
                q1.put((mv, None))
                q2.put(dur)
            except Exception as e:
                q1.put((None, e))
                q2.put(0)

        while running and winner is None:
            if not self.headless:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                self.view.draw_board()

            if not searching_thread or not searching_thread.is_alive():
                if move_queue.empty():
                    engine_proc = gray_engine_process if self.board.turn == 1 else blue_engine_process
                    # Capture current turn before starting the move retrieval.
                    current_turn = self.board.turn
                    searching_thread = Thread(target=get_move, args=(engine_proc, move_queue, duration_queue))
                    searching_thread.start()

                elif not move_queue.empty():
                    # Capture the current turn (the player making the move).
                    current_turn = self.board.turn
                    move_result, error = move_queue.get()
                    duration = duration_queue.get()
                    # Check if the engine produced an error (invalid move output).
                    if error is not None:
                        with open("invalid_move_log.txt", "a") as f:
                            f.write(f"Invalid move attempted at board state: {self.board.position_to_text()}\n")
                            f.write(f"Error from engine: {str(error)}\n")
                        # If player 1 made the error, they lose with invalid move (win = -3); otherwise, win = 3.
                        winner = -3 if current_turn == 1 else 3
                        break
                    else:
                        move = move_result
                        # Deduct the time used for this move.
                        if current_turn == 1:
                            self.time_gray -= duration
                            if self.time_gray < 0:
                                winner = -2  # Time over: player 1 lost, so win value -2.
                                break
                        else:
                            self.time_blue -= duration
                            if self.time_blue < 0:
                                winner = 2  # Time over: player 2 lost, so win value 2.
                                break
                        # Attempt to apply the move; catch any errors as invalid moves.
                        try:
                            self.apply_move(move)
                        except Exception as e:
                            with open("invalid_move_log.txt", "a") as f:
                                f.write(f"Invalid move attempted at board state: {self.board.position_to_text()}\n")
                                f.write(f"Error applying move: {str(e)}\n")
                            winner = -3 if current_turn == 1 else 3
                            break
                        move_queue.queue.clear()
                        duration_queue.queue.clear()

            state = self.board.check_state()
            if state != 0:
                # Normal win (game-ending move) returns ±1.
                winner = state

            if not self.headless:
                self.view.draw_board()
                clock.tick(FPS)

        quit_engine(gray_engine_process)
        quit_engine(blue_engine_process)

        if not self.headless:
            running = True
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                self.view.draw_board()
                clock.tick(FPS)
            pygame.quit()

        return winner
