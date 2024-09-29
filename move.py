def text_to_square(square_text):
    # Convert square notation to an index (0-24)
    row = ord(square_text[0]) - ord('a')
    col = int(square_text[1]) - 1

    square = col * 5 + row
    if square < 0 or square > 24:
        raise Exception(f"Invalid square: {square_text}")
    return square


def square_to_text(square):
    # Convert square index back to notation (e.g., 'A1', 'E5')
    row = chr(square % 5 + ord('a'))
    col = str(square // 5 + 1)
    return row + col


class Move:
    def __init__(self, move: str):
        # Convert move notation to internal representation
        self.begin = text_to_square(move[:2])
        self.end = text_to_square(move[2:4])
        self.build = text_to_square(move[4:6])

    def move_to_text(self):
        # Convert internal move representation back to text notation
        return square_to_text(self.begin) + square_to_text(self.end) + square_to_text(self.build)

