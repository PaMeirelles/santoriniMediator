import pygame

BLACK = (0, 0, 0)
BG = (50, 168, 82)
WHITE = (255, 255, 255)
GRAY = (69, 61, 55)
BLUE = (59, 83, 125)
DOME = (20, 20, 120)

class View:
    def __init__(self, screen_size, board):
        pygame.init()

        self.board = board
        self.cell_size = screen_size // 5
        self.board_size = 5 * self.cell_size
        self.panel_width = self.cell_size * 2  # white panel on the right
        self.total_width = self.board_size + self.panel_width
        self.total_height = self.board_size

        self.screen = pygame.display.set_mode((self.total_width, self.total_height))
        pygame.display.set_caption("Santorini Visualization")

        # Bolder font
        self.font_bold = pygame.font.SysFont("Arial", 28, bold=True)

    def draw_board(self):
        # 1) Fill entire screen with WHITE
        self.screen.fill(WHITE)

        # 2) Draw the green board area on the left
        board_rect = pygame.Rect(0, 0, self.board_size, self.board_size)
        pygame.draw.rect(self.screen, BG, board_rect)

        # 3) Draw grid cells & blocks
        for row in range(5):
            for col in range(5):
                cell_x = col * self.cell_size
                cell_y = row * self.cell_size
                pygame.draw.rect(
                    self.screen,
                    BLACK,
                    (cell_x, cell_y, self.cell_size, self.cell_size),
                    width=1
                )

                height = self.board.blocks[row * 5 + col]

                # Level 1
                if height >= 1:
                    pygame.draw.rect(
                        self.screen,
                        WHITE,
                        (
                            cell_x + self.cell_size * 0.05,
                            cell_y + self.cell_size * 0.05,
                            self.cell_size * 0.9,
                            self.cell_size * 0.9
                        )
                    )
                    pygame.draw.rect(
                        self.screen,
                        BLACK,
                        (
                            cell_x + self.cell_size * 0.05,
                            cell_y + self.cell_size * 0.05,
                            self.cell_size * 0.9,
                            self.cell_size * 0.9
                        ),
                        width=2
                    )

                # Level 2
                if height >= 2:
                    pygame.draw.rect(
                        self.screen,
                        WHITE,
                        (
                            cell_x + self.cell_size * 0.1,
                            cell_y + self.cell_size * 0.1,
                            self.cell_size * 0.8,
                            self.cell_size * 0.8
                        )
                    )
                    pygame.draw.rect(
                        self.screen,
                        BLACK,
                        (
                            cell_x + self.cell_size * 0.1,
                            cell_y + self.cell_size * 0.1,
                            self.cell_size * 0.8,
                            self.cell_size * 0.8
                        ),
                        width=2
                    )

                # Level 3
                if height >= 3:
                    center = (cell_x + self.cell_size // 2,
                              cell_y + self.cell_size // 2)
                    radius = self.cell_size // 3
                    pygame.draw.circle(self.screen, WHITE, center, radius)
                    pygame.draw.circle(self.screen, BLACK, center, radius, width=2)

                # Dome (Level 4)
                if height >= 4:
                    pygame.draw.circle(self.screen, DOME, center, radius)
                    pygame.draw.circle(self.screen, BLACK, center, radius, width=2)

        # 4) Draw workers
        for i, w in enumerate(self.board.workers):
            row = w // 5
            col = w % 5
            center = (col * self.cell_size + self.cell_size // 2,
                      row * self.cell_size + self.cell_size // 2)
            radius = self.cell_size // 4
            color = GRAY if i < 2 else BLUE
            pygame.draw.circle(self.screen, color, center, radius)
            pygame.draw.circle(self.screen, BLACK, center, radius, width=2)

        # 5) Info panel on the right
        panel_x = self.board_size
        panel_rect = pygame.Rect(panel_x, 0, self.panel_width, self.total_height)
        pygame.draw.rect(self.screen, BLACK, panel_rect, width=2)  # optional border

        # Big circle in the center
        turn_center = (panel_x + self.panel_width // 2, self.total_height // 2)
        turn_radius = 40

        circle_color = GRAY if self.board.turn == 1 else BLUE


        pygame.draw.circle(self.screen, circle_color, turn_center, turn_radius)
        pygame.draw.circle(self.screen, BLACK, turn_center, turn_radius, width=2)

        # Place Gray God name above the circle with more spacing
        if self.board.gods[0] is not None:
            text_gray = self.font_bold.render(self.board.gods[0].name, True, GRAY)
            # Center horizontally, ~50px above the circle
            gray_rect = text_gray.get_rect(
                center=(turn_center[0], turn_center[1] - turn_radius - 50)
            )
            self.screen.blit(text_gray, gray_rect)

        # Place Blue God name below the circle with more spacing
        if self.board.gods[1] is not None:
            text_blue = self.font_bold.render(self.board.gods[1].name, True, BLUE)
            # Center horizontally, ~50px below the circle
            blue_rect = text_blue.get_rect(
                center=(turn_center[0], turn_center[1] + turn_radius + 50)
            )
            self.screen.blit(text_blue, blue_rect)

        # Finally, update the display
        pygame.display.flip()
