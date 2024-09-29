from constants import NEIGHBOURS
from move import Move

class Board:
    def __init__(self, position):
        self.blocks = [0] * 25  # Initialize an empty board
        self.workers = [0] * 4  # 4 workers (2 for each player)
        self.turn = 1  # Default to player 1's turn

        self.parse_position(position)  # Parse the provided position string

    def parse_position(self, position):
        if len(position) != 51:
            raise ValueError(f"Invalid position: Expected length 50, got {len(position)}")

        num_gray_workers = 0
        num_blue_workers = 0

        for i in range(25):
            # Parse the blocks height
            height = int(position[2 * i])
            if height < 0 or height > 4:
                raise ValueError(f"Invalid block height at index {i}: {height}")
            self.blocks[i] = height

            # Parse the workers
            worker_code = position[2 * i + 1]
            if worker_code == 'G':  # Gray worker
                if num_gray_workers >= 2:
                    raise ValueError("Invalid position: More than 2 gray workers found")
                self.workers[num_gray_workers] = i
                num_gray_workers += 1
            elif worker_code == 'B':  # Blue worker
                if num_blue_workers >= 2:
                    raise ValueError("Invalid position: More than 2 blue workers found")
                self.workers[2 + num_blue_workers] = i
                num_blue_workers += 1
            elif worker_code != 'N':  # 'N' means no worker on that block
                raise ValueError(f"Invalid worker code '{worker_code}' at index {2 * i + 1}")

        # Check if exactly 2 gray and 2 blue workers are present
        if num_gray_workers != 2 or num_blue_workers != 2:
            raise ValueError(f"Invalid worker count: Found {num_gray_workers} gray workers and {num_blue_workers} blue workers")

        # Parse the turn (either '0' or '1' at position 50)
        if position[50] == '0':
            self.turn = 1
        elif position[50] == '1':
            self.turn = -1
        else:
            raise ValueError(f"Invalid turn: Expected '0' or '1', got '{position[50]}'")

    def position_to_text(self):
        position = []
        for i in range(25):
            block_height = str(self.blocks[i])
            if i in self.workers[:2]:
                worker_code = 'G'
            elif i in self.workers[2:]:
                worker_code = 'B'
            else:
                worker_code = 'N'
            position.append(block_height + worker_code)
        return ''.join(position) + ('0' if self.turn == 1 else '1')

    def is_free(self, square):
        return square not in self.workers and self.blocks[square] < 4

    def check_state(self):
        state = None

        for i, worker_pos in enumerate(self.workers):
            # Check if a worker is on a block of height 3 (winning condition)
            if self.blocks[worker_pos] == 3:
                if state is None:
                    state = 1 if i < 2 else -1
                else:
                    raise Exception("Invalid state: Multiple winning workers")

            # Check if there are any valid moves for the worker
            valid_move = any(self.is_free(n) for n in NEIGHBOURS[worker_pos])
            if not valid_move:
                # No valid moves left for current worker
                if (self.turn == 1 and i < 2) or (self.turn == -1 and i >= 2):
                    if state is None:
                        state = -1 if self.turn == 1 else 1
                    else:
                        raise Exception("Invalid state: Multiple losing workers")

        # Return the state: 0 if no terminal condition, 1 if gray wins, -1 if blue wins
        return state if state is not None else 0

    def move_is_valid(self, move: Move) ->bool:
        if move.begin not in self.workers:
            return False
        # Check if the move is valid
        if not self.is_free(move.end) or move.build == move.end:
            return False  # Destination is not free
        if move.build != move.begin and not self.is_free(move.build):
            return False
        if abs(self.blocks[move.end] - self.blocks[move.begin]) > 1:
            return False  # Can't move more than 1 level up
        if move.build < 0 or move.build >= 25:
            return False  # Invalid build position
        if move.end not in NEIGHBOURS[move.begin] or move.build not in NEIGHBOURS[move.end]:
            return False # Non adjacent square
        return True

    def make_move(self, move:Move) -> None:
        if not self.move_is_valid(move):
            raise Exception("Invalid move")
        for i, w in enumerate(self.workers):
            if w == move.begin:
                self.workers[i] = move.end
                break

        self.blocks[move.build] += 1
        self.turn *= 1

