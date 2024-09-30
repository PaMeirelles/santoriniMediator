import subprocess
import time
from threading import Thread
from queue import Queue
from typing import Tuple

import pygame

from view import View
from board import Board
from move import Move

FPS = 20

def start_engine(engine_path):
    try:
        process = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True  # Ensure text mode for input/output
        )

        if process.poll() is None:
            print("Engine started successfully.")
        else:
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


class Controller:
    def __init__(self, position, time_gray, time_blue, gray_engine_path, blue_engine_path):
        self.board = Board(position)
        self.time_gray = time_gray
        self.time_blue = time_blue
        self.gray_engine_path = gray_engine_path
        self.blue_engine_path = blue_engine_path
        self.view = View(600, self.board)

    def run_engine(self, engine_process) -> Tuple[Move, float]:
        board_state = self.board.position_to_text()
        ready_output = send_command(engine_process, "isready")
        if ready_output != "readyok":
            raise RuntimeError(f"Engine is not ready: {ready_output}")

        position_command = f"position {board_state}"
        send_command(engine_process, position_command)

        go_command = f"go gtime {self.time_gray * 1000} btime {self.time_blue * 1000}"
        print(position_command, go_command)
        start = time.perf_counter()
        move_output = send_command(engine_process, go_command)

        if move_output.startswith("bestmove"):
            end = time.perf_counter()
            print(move_output)
            return Move(move_output.split()[1]), end - start
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
        clock = pygame.time.Clock()
        move_queue = Queue()
        duration_queue = Queue()

        def get_move(process, q1, q2):
            mv, dur = self.run_engine(process)
            q1.put(mv)
            q2.put(dur)

        while running and winner is None:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

            self.view.draw_board()

            if not searching_thread or not searching_thread.is_alive():
                if move_queue.empty():
                    if self.board.turn == 1:
                        arg = gray_engine_process
                    else:
                        arg = blue_engine_process

                    searching_thread = Thread(target=get_move, args=(arg, move_queue, duration_queue))
                    searching_thread.start()

                elif not move_queue.empty():
                    move = move_queue.get()
                    duration = duration_queue.get()
                    if self.board.turn == 1:
                        self.time_gray -= duration
                        if self.time_gray < 0:
                            winner = -1
                            break
                    else:
                        self.time_blue -= duration
                        if self.time_blue < 0:
                            winner = 1
                            break

                    self.apply_move(move)
                    move_queue.queue.clear()  # Clear the queue to avoid processing the same move multiple times
                    duration_queue.queue.clear()

            state = self.board.check_state()
            if state != 0:
                winner = state

            self.view.draw_board()
            clock.tick(FPS)

        quit_engine(gray_engine_process)
        quit_engine(blue_engine_process)

        print("Game over!")
        print(f"Winner: {winner}")
