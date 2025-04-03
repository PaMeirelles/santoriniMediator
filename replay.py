import pygame
from typing import List, TypeVar
from board import Board, God
from database import get_conn
from view import View
from move import ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove, HephaestusMove, HermesMove, MinotaurMove, PanMove, PrometheusMove

T = TypeVar('T', bound='Move')

# ---------------------------
# Replay Class
# ---------------------------
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

    def go_forward(self):
        """Advance the replay by one move (if available)."""
        if self.current_move_index < len(self.moves_text):
            self.current_move_index += 1
            self.update_board()

    def go_backward(self):
        """Step back one move (if possible) by rebuilding the board."""
        if self.current_move_index > 0:
            self.current_move_index -= 1
            self.update_board()

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


# ---------------------------
# Database Loader Function
# ---------------------------
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


# ---------------------------
# Main Function
# ---------------------------
def main():
    # Example: use a match with ID 1
    match_id = 34049

    god_g, god_b, moves_list, pos = load_match_from_db(match_id)

    # Initialize pygame and the replay system.
    screen_size = 800
    pygame.init()
    replay = Replay(pos, moves_list, screen_size)
    replay.run()


if __name__ == "__main__":
    main()
