import pygame

# Colors
BLACK = (0, 0, 0)
BG = (50, 168, 82)
WHITE = (255, 255, 255)
GRAY = (69, 61, 55)
BLUE = (59, 83, 125)
DOME = (20, 20, 120)

# Layout constants
BOARD_DIMENSION = 5
PANEL_WIDTH_FACTOR = 2  # panel_width = cell_size * PANEL_WIDTH_FACTOR

# Grid and building drawing constants
GRID_LINE_WIDTH = 1

# Level 1 constants
LEVEL1_OFFSET_FACTOR = 0.05
LEVEL1_SIZE_FACTOR = 0.9
LEVEL1_BORDER_WIDTH = 2

# Level 2 constants
LEVEL2_OFFSET_FACTOR = 0.1
LEVEL2_SIZE_FACTOR = 0.8
LEVEL2_BORDER_WIDTH = 2

# Level 3 (and Dome) constants
LEVEL3_RADIUS_DIVISOR = 3
LEVEL3_BORDER_WIDTH = 2

# Worker drawing constants (used later for animation too)
WORKER_RADIUS_DIVISOR = 4
WORKER_BORDER_WIDTH = 2

# Info panel constants
PANEL_BORDER_WIDTH = 2
TURN_RADIUS = 40
GOD_NAME_OFFSET = 50  # vertical spacing between the circle and god names

# Font constants
FONT_SIZE = 28

class View:
    def __init__(self, screen_size, board):
        pygame.init()

        self.board = board
        self.cell_size = screen_size // BOARD_DIMENSION
        self.board_size = BOARD_DIMENSION * self.cell_size
        self.panel_width = self.cell_size * PANEL_WIDTH_FACTOR  # white panel on the right
        self.total_width = self.board_size + self.panel_width
        self.total_height = self.board_size

        self.screen = pygame.display.set_mode((self.total_width, self.total_height))
        pygame.display.set_caption("Santorini Visualization")

        # Bolder font
        self.font_bold = pygame.font.SysFont("Arial", FONT_SIZE, bold=True)

    def draw_board_static(self):
        """Draw the board grid, blocks, and info panel—but not the workers."""
        # Fill entire screen with WHITE
        self.screen.fill(WHITE)

        # Draw the board area (green) on the left
        board_rect = pygame.Rect(0, 0, self.board_size, self.board_size)
        pygame.draw.rect(self.screen, BG, board_rect)

        # Draw grid cells & blocks
        for row in range(BOARD_DIMENSION):
            for col in range(BOARD_DIMENSION):
                cell_x = col * self.cell_size
                cell_y = row * self.cell_size
                pygame.draw.rect(
                    self.screen,
                    BLACK,
                    (cell_x, cell_y, self.cell_size, self.cell_size),
                    width=GRID_LINE_WIDTH
                )

                height = self.board.blocks[row * BOARD_DIMENSION + col]

                # Level 1
                if height >= 1:
                    pygame.draw.rect(
                        self.screen,
                        WHITE,
                        (
                            cell_x + self.cell_size * LEVEL1_OFFSET_FACTOR,
                            cell_y + self.cell_size * LEVEL1_OFFSET_FACTOR,
                            self.cell_size * LEVEL1_SIZE_FACTOR,
                            self.cell_size * LEVEL1_SIZE_FACTOR
                        )
                    )
                    pygame.draw.rect(
                        self.screen,
                        BLACK,
                        (
                            cell_x + self.cell_size * LEVEL1_OFFSET_FACTOR,
                            cell_y + self.cell_size * LEVEL1_OFFSET_FACTOR,
                            self.cell_size * LEVEL1_SIZE_FACTOR,
                            self.cell_size * LEVEL1_SIZE_FACTOR
                        ),
                        width=LEVEL1_BORDER_WIDTH
                    )

                # Level 2
                if height >= 2:
                    pygame.draw.rect(
                        self.screen,
                        WHITE,
                        (
                            cell_x + self.cell_size * LEVEL2_OFFSET_FACTOR,
                            cell_y + self.cell_size * LEVEL2_OFFSET_FACTOR,
                            self.cell_size * LEVEL2_SIZE_FACTOR,
                            self.cell_size * LEVEL2_SIZE_FACTOR
                        )
                    )
                    pygame.draw.rect(
                        self.screen,
                        BLACK,
                        (
                            cell_x + self.cell_size * LEVEL2_OFFSET_FACTOR,
                            cell_y + self.cell_size * LEVEL2_OFFSET_FACTOR,
                            self.cell_size * LEVEL2_SIZE_FACTOR,
                            self.cell_size * LEVEL2_SIZE_FACTOR
                        ),
                        width=LEVEL2_BORDER_WIDTH
                    )

                # Level 3
                if height >= 3:
                    center = (cell_x + self.cell_size // 2,
                              cell_y + self.cell_size // 2)
                    radius = self.cell_size // LEVEL3_RADIUS_DIVISOR
                    pygame.draw.circle(self.screen, WHITE, center, radius)
                    pygame.draw.circle(self.screen, BLACK, center, radius, width=LEVEL3_BORDER_WIDTH)

                # Dome (Level 4)
                if height >= 4:
                    pygame.draw.circle(self.screen, DOME, center, radius)
                    pygame.draw.circle(self.screen, BLACK, center, radius, width=LEVEL3_BORDER_WIDTH)

        # Draw the info panel on the right (static part)
        panel_x = self.board_size
        panel_rect = pygame.Rect(panel_x, 0, self.panel_width, self.total_height)
        pygame.draw.rect(self.screen, BLACK, panel_rect, width=PANEL_BORDER_WIDTH)

        # Big circle in the center of the panel (indicates turn)
        turn_center = (panel_x + self.panel_width // 2, self.total_height // 2)
        circle_color = GRAY if self.board.turn == 1 else BLUE
        pygame.draw.circle(self.screen, circle_color, turn_center, TURN_RADIUS)
        pygame.draw.circle(self.screen, BLACK, turn_center, TURN_RADIUS, width=PANEL_BORDER_WIDTH)

        # God names: draw them just above and below the circle
        if self.board.gods[0] is not None:
            text_gray = self.font_bold.render(self.board.gods[0].name, True, GRAY)
            gray_rect = text_gray.get_rect(
                center=(turn_center[0], turn_center[1] - TURN_RADIUS - GOD_NAME_OFFSET)
            )
            self.screen.blit(text_gray, gray_rect)

        if self.board.gods[1] is not None:
            text_blue = self.font_bold.render(self.board.gods[1].name, True, BLUE)
            blue_rect = text_blue.get_rect(
                center=(turn_center[0], turn_center[1] + TURN_RADIUS + GOD_NAME_OFFSET)
            )
            self.screen.blit(text_blue, blue_rect)

    def draw_board(self):
        """Draw the full board including workers."""
        self.draw_board_static()
        # Draw workers (using board.workers, which are assumed to be cell indices)
        for i, w in enumerate(self.board.workers):
            row = w // BOARD_DIMENSION
            col = w % BOARD_DIMENSION
            center = (col * self.cell_size + self.cell_size // 2,
                      row * self.cell_size + self.cell_size // 2)
            radius = self.cell_size // WORKER_RADIUS_DIVISOR
            color = GRAY if i < 2 else BLUE
            pygame.draw.circle(self.screen, color, center, radius)
            pygame.draw.circle(self.screen, BLACK, center, radius, width=WORKER_BORDER_WIDTH)
        pygame.display.flip()
