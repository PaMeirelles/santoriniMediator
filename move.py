from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Optional
from dataclasses import dataclass

def text_to_square(square_text):
    row = ord(square_text[0]) - ord('a')
    col = int(square_text[1]) - 1
    square = col * 5 + row
    if square < 0 or square > 24:
        raise Exception(f"Invalid square: {square_text}")
    return square

def square_to_text(square):
    row = chr(square % 5 + ord('a'))
    col = str(square // 5 + 1)
    return row + col

T = TypeVar('T', bound='Move')

@dataclass
class Move(ABC):
    from_sq: int

    @property
    @abstractmethod
    def final_sq(self) -> int:
        pass

    @abstractmethod
    def move_to_text(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def from_text(cls: Type[T], move_text: str) -> T:
        pass

@dataclass
class ApolloMove(Move):
    to_sq: int
    build_sq: int

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        return square_to_text(self.from_sq) + square_to_text(self.to_sq) + square_to_text(self.build_sq)

    @classmethod
    def from_text(cls, move_text: str) -> "ApolloMove":
        return cls(
            from_sq=text_to_square(move_text[0:2]),
            to_sq=text_to_square(move_text[2:4]),
            build_sq=text_to_square(move_text[4:6]),
        )

@dataclass
class ArtemisMove(Move):
    to_sq: int
    build_sq: int
    mid_sq: Optional[int] = None

    @property
    def final_sq(self) -> int:
        return self.to_sq

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
    squares: List[int]
    build_sq: int

    @property
    def final_sq(self) -> int:
        return self.squares[-1] if self.squares else self.from_sq

    def move_to_text(self) -> str:
        return (
            square_to_text(self.from_sq) +
            ''.join(square_to_text(sq) for sq in self.squares) +
            square_to_text(self.build_sq)
        )

    @classmethod
    def from_text(cls, move_text: str) -> "HermesMove":
        if len(move_text) < 4 or len(move_text) % 2 != 0:
            raise ValueError("Hermes move text must be even and at least 4 chars")
        from_sq = text_to_square(move_text[0:2])
        build_sq = text_to_square(move_text[-2:])
        middle = move_text[2:-2]
        squares = [text_to_square(middle[i:i+2]) for i in range(0, len(middle), 2)]
        return cls(from_sq=from_sq, squares=squares, build_sq=build_sq)

@dataclass
class DemeterMove(Move):
    to_sq: int
    build_sq_1: int
    build_sq_2: Optional[int] = None

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq_1),
        ]
        if self.build_sq_2 is not None:
            parts.append(square_to_text(self.build_sq_2))
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "DemeterMove":
        if len(move_text) == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq_1=text_to_square(move_text[4:6]),
            )
        elif len(move_text) == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq_1=text_to_square(move_text[4:6]),
                build_sq_2=text_to_square(move_text[6:8]),
            )
        else:
            raise ValueError("Demeter move text must be 6 or 8 characters")

@dataclass
class HephaestusMove(DemeterMove):
    pass

@dataclass
class PanMove(ApolloMove):
    pass

@dataclass
class PrometheusMove(Move):
    to_sq: int
    build_sq: int
    optional_build: Optional[int] = None

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq),
        ]
        if self.optional_build is not None:
            parts.append(square_to_text(self.optional_build))
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "PrometheusMove":
        if len(move_text) == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
            )
        elif len(move_text) == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
                optional_build=text_to_square(move_text[6:8]),
            )
        else:
            raise ValueError("Prometheus move text must be 6 or 8 characters")

@dataclass
class AthenaMove(ApolloMove):
    pass

@dataclass
class MinotaurMove(ApolloMove):
    pass

@dataclass
class AtlasMove(Move):
    to_sq: int
    build_sq: int
    dome: bool

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        parts = [
            square_to_text(self.from_sq),
            square_to_text(self.to_sq),
            square_to_text(self.build_sq),
        ]
        if self.dome:
            parts.append("D")
        return ''.join(parts)

    @classmethod
    def from_text(cls, move_text: str) -> "AtlasMove":
        if len(move_text) not in (6, 7):
            raise ValueError("Atlas move must be 6 or 7 characters")
        from_sq = text_to_square(move_text[0:2])
        to_sq = text_to_square(move_text[2:4])
        build_sq = text_to_square(move_text[4:6])
        dome = len(move_text) == 7 and move_text[6] == "D"
        if len(move_text) == 7 and not dome:
            raise ValueError("Atlas 7th char must be 'D' if present.")
        return cls(from_sq=from_sq, to_sq=to_sq, build_sq=build_sq, dome=dome)