from abc import ABC, abstractmethod
from typing import Type, TypeVar, List
from typing import Optional
from dataclasses import dataclass

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


T = TypeVar('T', bound='Move')

class Move(ABC):
    @abstractmethod
    def move_to_text(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def from_text(cls: Type[T], move_text: str) -> T:
        pass


@dataclass
class ApolloMove(Move):
    from_sq: int
    to_sq: int
    build_sq: int

    def move_to_text(self) -> str:
        return (
            square_to_text(self.from_sq) +
            square_to_text(self.to_sq) +
            square_to_text(self.build_sq)
        )

    @classmethod
    def from_text(cls, move_text: str) -> "ApolloMove":
        if len(move_text) != 6:
            raise ValueError("Apollo move text must be exactly 6 characters")
        return cls(
            from_sq=text_to_square(move_text[0:2]),
            to_sq=text_to_square(move_text[2:4]),
            build_sq=text_to_square(move_text[4:6]),
        )


@dataclass
class ArtemisMove(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    mid_sq: Optional[int] = None

    def move_to_text(self) -> str:
        parts = [square_to_text(self.from_sq)]
        if self.mid_sq is not None:
            parts.append(square_to_text(self.mid_sq))
        parts.append(square_to_text(self.to_sq))
        parts.append(square_to_text(self.build_sq))
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "ArtemisMove":
        if len(move_text) == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
            )
        elif len(move_text) == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                mid_sq=text_to_square(move_text[2:4]),
                to_sq=text_to_square(move_text[4:6]),
                build_sq=text_to_square(move_text[6:8]),
            )
        else:
            raise ValueError("Move text must be 6 or 8 characters long")


@dataclass
class HermesMove(Move):
    from_sq: int
    squares: List[int]
    build: int

    def move_to_text(self) -> str:
        # Convert 'from_sq' to text
        from_part = square_to_text(self.from_sq)
        # Convert each intermediate square
        squares_part = "".join(square_to_text(sq) for sq in self.squares)
        # Convert 'build' square
        build_part = square_to_text(self.build)
        return from_part + squares_part + build_part

    @classmethod
    def from_text(cls, move_text: str) -> "HermesMove":
        if len(move_text) < 4 or len(move_text) % 2 != 0:
            raise ValueError("Hermes move text must be at least 4 characters (and even in length).")

        # First 2 chars → from_sq
        from_part = move_text[:2]
        # Last 2 chars → build
        build_part = move_text[-2:]
        # Everything in between → intermediate squares
        middle = move_text[2:-2]

        from_sq = text_to_square(from_part)
        build_sq = text_to_square(build_part)

        squares = []
        # Parse 2-char chunks in the middle
        for i in range(0, len(middle), 2):
            chunk = middle[i:i+2]
            squares.append(text_to_square(chunk))

        return cls(from_sq=from_sq, squares=squares, build=build_sq)


@dataclass
class DemeterMove(Move):
    from_sq: int
    to_sq: int
    build_sq_1: int
    build_sq_2: Optional[int] = None

    def move_to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq_1),
        ]
        if self.build_sq_2 is not None:
            parts.append(square_to_text(self.build_sq_2))

        return "".join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "DemeterMove":
        length = len(move_text)
        if length == 6:
            # from(0..2), to(2..4), build1(4..6)
            from_sq = text_to_square(move_text[0:2])
            to_sq = text_to_square(move_text[2:4])
            build_sq_1 = text_to_square(move_text[4:6])
            return cls(from_sq, to_sq, build_sq_1)
        elif length == 8:
            # from(0..2), to(2..4), build1(4..6), build2(6..8)
            from_sq = text_to_square(move_text[0:2])
            to_sq = text_to_square(move_text[2:4])
            build_sq_1 = text_to_square(move_text[4:6])
            build_sq_2 = text_to_square(move_text[6:8])
            return cls(from_sq, to_sq, build_sq_1, build_sq_2)
        else:
            raise ValueError("Demeter move text must be either 6 or 8 characters long.")

@dataclass
class Hephaestus(DemeterMove):
    pass

@dataclass
class PanGod(ApolloMove):
    pass

@dataclass
class Prometheus(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    optional_build: Optional[int] = None

    def move_to_text(self) -> str:
        """
        If we do NOT use the optional build, we have 6 chars: from(2)+to(2)+build(2).
        If we use the optional build, we have 8 chars: from(2)+to(2)+build(2)+optional(2).
        """
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq),
        ]
        if self.optional_build is not None:
            parts.append(square_to_text(self.optional_build))
        return "".join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "Prometheus":
        length = len(move_text)
        if length == 6:
            # from(0..2), to(2..4), build(4..6)
            from_sq = text_to_square(move_text[0:2])
            to_sq = text_to_square(move_text[2:4])
            build_sq = text_to_square(move_text[4:6])
            return cls(from_sq, to_sq, build_sq)
        elif length == 8:
            # from(0..2), to(2..4), build(4..6), optional(6..8)
            from_sq = text_to_square(move_text[0:2])
            to_sq = text_to_square(move_text[2:4])
            build_sq = text_to_square(move_text[4:6])
            optional_build = text_to_square(move_text[6:8])
            return cls(from_sq, to_sq, build_sq, optional_build)
        else:
            raise ValueError("Prometheus move text must be 6 or 8 characters long.")


@dataclass
class Athena(ApolloMove):
    pass

@dataclass
class Minotaur(ApolloMove):
    pass

@dataclass
class Atlas(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    dome: bool

    def move_to_text(self) -> str:
        """
        6 chars if building a normal block:
           from(2) + to(2) + build(2)
        7 chars if building a dome (add 'D' at the end):
           from(2) + to(2) + build(2) + 'D'
        """
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq),
        ]
        if self.dome:
            parts.append("D")
        return "".join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "Atlas":
        """
        Accept either 6 or 7 characters:
         - 6 => normal build (no dome)
         - 7 => last char must be 'D' to indicate a dome
        Example:
          'a1b2c3'  => from_sq=a1, to_sq=b2, build_sq=c3, dome=False
          'a1b2c3D' => from_sq=a1, to_sq=b2, build_sq=c3, dome=True
        """
        length = len(move_text)
        if length not in (6, 7):
            raise ValueError("Atlas move text must be 6 or 7 characters long.")

        # First 6 chars are the squares (from, to, build)
        from_sq = text_to_square(move_text[0:2])
        to_sq = text_to_square(move_text[2:4])
        build_sq = text_to_square(move_text[4:6])

        # If there's a 7th char, it must be "D" for dome
        if length == 6:
            dome = False
        else:
            if move_text[6] == "D":
                dome = True
            else:
                raise ValueError("Atlas 7th char must be 'D' if present.")

        return cls(from_sq=from_sq, to_sq=to_sq, build_sq=build_sq, dome=dome)
