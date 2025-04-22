from multiprocessing import Process

import pygame
from typing import List, TypeVar
from board import Board, God, _calculate_push_square
from database import get_conn
from view import View, GRAY, BLUE, WORKER_RADIUS_DIVISOR, BLACK, WORKER_BORDER_WIDTH, BOARD_DIMENSION
from move import ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, MinotaurMove, PanMove, PrometheusMove

T = TypeVar('T', bound='Move')

# Duration (in milliseconds) for the worker move animation
WORKER_ANIMATION_DURATION = 100

class Replay:
    def __init__(self, initial_position: str, moves_text: List[str], screen_size: int = 500):
        """
        :param initial_position: A 54-character string representing the starting board state.
        :param moves_text: List of moves (each as a text string, one per line).
        :param screen_size: Size of the pygame window.
        """
        self.initial_position = initial_position
        self.moves_text = moves_text  # list of move strings
        self.current_move_index = 0  # 0 means no moves have been applied yet
        self.screen_size = screen_size
        self.board = Board(initial_position)
        self.view = View(screen_size, self.board)

    def update_board(self):
        """
        Rebuild the board from the initial position and then apply all moves
        up to self.current_move_index.
        """
        self.board = Board(self.initial_position)
        # Mapping from god to the corresponding Move class.
        god_to_move = {
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
        for i in range(self.current_move_index):
            move_str = self.moves_text[i].strip()
            if not move_str:
                continue
            current_god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
            move_class = god_to_move.get(current_god)
            if move_class is None:
                raise Exception("No move class found for god: {}".format(current_god))
            move = move_class.from_text(move_str)
            self.board.make_move(move)
        self.view.board = self.board

    def animate_workers(self, old_positions: List[int], new_positions: List[int], duration=WORKER_ANIMATION_DURATION):
        """
        Animate moving workers from ol d_positions to new_positions over 'duration' milliseconds.
        Positions are given as cell indices (0 to 24).
        """
        start_time = pygame.time.get_ticks()
        while True:
            now = pygame.time.get_ticks()
            t = (now - start_time) / duration
            if t > 1:
                t = 1
            # Draw the board static background (grid, blocks, info panel)
            self.view.draw_board_static()
            # Draw each worker: if a worker moved, interpolate its pixel center.
            for i in range(len(new_positions)):
                # Determine old and new cell for worker i
                old_cell = old_positions[i]
                new_cell = new_positions[i]
                # Compute final pixel center for new_cell:
                new_row = new_cell // BOARD_DIMENSION
                new_col = new_cell % BOARD_DIMENSION
                new_center = (new_col * self.view.cell_size + self.view.cell_size // 2,
                              new_row * self.view.cell_size + self.view.cell_size // 2)
                if old_cell == new_cell:
                    current_center = new_center
                else:
                    old_row = old_cell // BOARD_DIMENSION
                    old_col = old_cell % BOARD_DIMENSION
                    old_center = (old_col * self.view.cell_size + self.view.cell_size // 2,
                                  old_row * self.view.cell_size + self.view.cell_size // 2)
                    current_center = (
                        int(old_center[0] + (new_center[0] - old_center[0]) * t),
                        int(old_center[1] + (new_center[1] - old_center[1]) * t)
                    )
                color = GRAY if i < 2 else BLUE
                radius = self.view.cell_size // WORKER_RADIUS_DIVISOR
                pygame.draw.circle(self.view.screen, color, current_center, radius)
                pygame.draw.circle(self.view.screen, BLACK, current_center, radius, width=WORKER_BORDER_WIDTH)
            pygame.display.flip()

            # Process events during animation so the window remains responsive
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    return

            if t >= 1:
                break
            pygame.time.delay(10)

    from board import _calculate_push_square  # import the helper if not already imported

    def go_forward(self):
        """Advance the replay by one move with animated worker movement, handling intermediate moves for Artemis, Hermes, and Minotaur."""
        if self.current_move_index < len(self.moves_text):
            # Record the board's worker positions before the move.
            old_positions = self.board.workers.copy()
            next_move_str = self.moves_text[self.current_move_index].strip()

            # Mapping from god to move class.
            god_to_move = {
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
            current_god = self.board.gods[0] if self.board.turn == 1 else self.board.gods[1]
            move_class = god_to_move.get(current_god)
            last_move = move_class.from_text(next_move_str)

            new_positions = old_positions.copy()
            moving_worker_index = new_positions.index(last_move.from_sq)

            if isinstance(last_move, ArtemisMove) and last_move.mid_sq is not None:
                mid_positions = old_positions.copy()
                mid_positions[moving_worker_index] = last_move.mid_sq
                self.animate_workers(old_positions, mid_positions)
                new_positions[moving_worker_index] = last_move.final_sq
                self.animate_workers(mid_positions, new_positions)
            elif isinstance(last_move, ApolloMove):
                # If the target square is occupied, perform a swap animation.
                if last_move.to_sq in old_positions:
                    opponent_worker_index = old_positions.index(last_move.to_sq)
                    new_positions[moving_worker_index] = last_move.final_sq
                    new_positions[opponent_worker_index] = last_move.from_sq
                    self.animate_workers(old_positions, new_positions)
                else:
                    # Otherwise, it's a normal move.
                    new_positions[moving_worker_index] = last_move.final_sq
                    self.animate_workers(old_positions, new_positions)
            elif isinstance(last_move, HermesMove) and last_move.squares:
                current_positions = old_positions.copy()
                for intermediate_sq in last_move.squares:
                    next_positions = current_positions.copy()
                    next_positions[moving_worker_index] = intermediate_sq
                    self.animate_workers(current_positions, next_positions)
                    current_positions = next_positions
                new_positions = current_positions  # Final position after all intermediate moves.
            elif isinstance(last_move, MinotaurMove):
                # Animate the minotaur moving first.
                new_positions = old_positions.copy()
                new_positions[moving_worker_index] = last_move.final_sq
                self.animate_workers(old_positions, new_positions)

                # Now animate the pushed worker (if any).
                try:
                    pushed_worker_index = old_positions.index(last_move.to_sq)
                    push_sq = _calculate_push_square(last_move.from_sq, last_move.to_sq)
                    if push_sq is not None:
                        pushed_positions = new_positions.copy()
                        pushed_positions[pushed_worker_index] = push_sq
                        self.animate_workers(new_positions, pushed_positions)
                except ValueError:
                    # No pushed worker.
                    pass
            elif isinstance(last_move, PrometheusMove) and last_move.optional_build is not None:
                # Prometheus's optional build happens before the move.
                # Animate the optional build first.
                # Update the board's block for the optional build and redraw.
                self.board.blocks[last_move.optional_build] += 1
                self.view.draw_board()
                pygame.time.delay(WORKER_ANIMATION_DURATION)
                # Now animate the worker movement.
                new_positions[moving_worker_index] = last_move.final_sq
                self.animate_workers(old_positions, new_positions)

            else:
                new_positions[moving_worker_index] = last_move.final_sq
                self.animate_workers(old_positions, new_positions)

            # Update the board state and redraw.
            self.current_move_index += 1
            self.update_board()
            self.view.draw_board()

    def go_backward(self):
        """Step back one move with animated worker movement."""
        if self.current_move_index > 0:
            old_positions = self.board.workers.copy()
            self.current_move_index -= 1
            self.update_board()
            new_positions = self.board.workers.copy()
            self.animate_workers(old_positions, new_positions)
            self.view.draw_board()

    def handle_event(self, event):
        """
        Listen for KEYDOWN events to move the replay forward (right arrow)
        or backward (left arrow).
        """
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RIGHT:
                self.go_forward()
            elif event.key == pygame.K_LEFT:
                self.go_backward()
            elif event.key == pygame.K_SPACE:
                # Print the current board position to the console
                print(self.board.position_to_text())

    def draw(self):
        """Draw the current board state using the View."""
        self.view.draw_board()

    def run(self):
        """Run the main loop for the replay."""
        running = True
        clock = pygame.time.Clock()
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                self.handle_event(event)
            self.draw()
            clock.tick(30)  # Limit to 30 FPS
        pygame.quit()


def load_match_from_db(match_id: int):
    """
    Query the TB_MATCHES table for a given match_id.
    Returns the gods for Gray and Blue (as strings), a list of move strings, and the starting position.
    """
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT God_G, God_B, Moves, Starting_pos FROM TB_MATCHES WHERE Id = ?", (match_id,))
    row = cursor.fetchone()
    if row is None:
        raise Exception(f"Match with ID {match_id} not found")
    god_g, god_b, moves_text, pos = row
    moves_list = moves_text.strip().splitlines()
    conn.close()
    return god_g, god_b, moves_list, pos

def run_replay(match_id):
    god_g, god_b, moves_list, pos = load_match_from_db(match_id)
    screen_size = 800
    pygame.init()
    pygame.key.set_repeat(200, 50)
    replay = Replay(pos, moves_list, screen_size)
    replay.run()

if __name__ == "__main__":
    p1 = Process(target=run_replay, args=(67758,))
    p2 = Process(target=run_replay, args=(67759,))

    p1.start()
    p2.start()
    p1.join()
    p2.join()
