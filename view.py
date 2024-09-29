import pygame

BLACK = 0, 0, 0
BG = 50, 168, 82
WHITE = 255, 255, 255
GRAY = 69, 61, 55
BLUE = 59, 83, 125
DOME = 20, 20, 120

class View:
    def __init__(self, screen_size, board):
        pygame.init()
        self.board = board
        self.screen_size = screen_size
        self.cell_size = self.screen_size // 5
        self.screen = pygame.display.set_mode((self.screen_size, self.screen_size))
        pygame.display.set_caption("Santorini Visualization")
        self.font = pygame.font.SysFont("Arial", 24)

    def draw_board(self):
        self.screen.fill(BG)
        for row in range(5):
            for col in range(5):
                pygame.draw.rect(self.screen,BLACK,(col * self.cell_size, row * self.cell_size,
                                                    self.cell_size, self.cell_size), 1)
                height = self.board.blocks[row * 5 + col]
                if height >= 1:
                    pygame.draw.rect(self.screen, WHITE,(col * self.cell_size + self.cell_size * .05,
                                                         row * self.cell_size + self.cell_size * .05,
                                                         self.cell_size * .9, self.cell_size * .9))
                    pygame.draw.rect(self.screen, BLACK, (col * self.cell_size + self.cell_size * .05,
                                                         row * self.cell_size + self.cell_size * .05,
                                                         self.cell_size * .9, self.cell_size * .9), width=2)
                if height >= 2:
                    pygame.draw.rect(self.screen, WHITE, (col * self.cell_size + self.cell_size * .1,
                                                          row * self.cell_size + self.cell_size * .1,
                                                          self.cell_size * .8, self.cell_size * .8))
                    pygame.draw.rect(self.screen, BLACK, (col * self.cell_size + self.cell_size * .1,
                                                          row * self.cell_size + self.cell_size * .1,
                                                          self.cell_size * .8, self.cell_size * .8), width=2)
                if height >= 3:
                    center = (col * self.cell_size + self.cell_size // 2, + row * self.cell_size + self.cell_size // 2)
                    radius = self.cell_size // 3

                    pygame.draw.circle(self.screen, WHITE, center, radius)
                    pygame.draw.circle(self.screen, BLACK, center, radius, width=2)

                if height >= 4:
                    pygame.draw.circle(self.screen, DOME, center, radius)
                    pygame.draw.circle(self.screen, BLACK, center, radius, width=2)

        for i, w in enumerate(self.board.workers):
            row = w //5
            col = w % 5
            center = (col * self.cell_size + self.cell_size // 2, + row * self.cell_size + self.cell_size // 2)
            radius = self.cell_size // 4
            if i < 2:
                color = GRAY
            else:
                color = BLUE
            pygame.draw.circle(self.screen, color, center, radius)
            pygame.draw.circle(self.screen, BLACK, center, radius, width=2)
        pygame.display.flip()