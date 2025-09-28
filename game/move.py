from abc import ABC, abstractmethod
from typing import Type, TypeVar, List, Optional
from dataclasses import dataclass

from game.util import log_invalid_move


def text_to_square(square_text: str) -> int:
    row = ord(square_text[0]) - ord('a')
    col = int(square_text[1]) - 1
    sq = col * 5 + row
    if sq < 0 or sq > 24:
        raise ValueError(f"Invalid square: {square_text}")
    return sq

def square_to_text(square: int) -> str:
    row = chr(square % 5 + ord('a'))
    col = str(square // 5 + 1)
    return row + col

##############################################################################
# Abstract Base
##############################################################################

T = TypeVar('T', bound='Move')

@dataclass
class Move(ABC):
    """
    Abstract base for all moves. Each move *must* define:
      - from_text(cls, move_text)
      - final_sq property
      - move_to_text()
    """
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

##############################################################################
# Common base classes for single/double building
##############################################################################

@dataclass
class SingleBuildMove(Move):
    """
    For gods with exactly one step: from_sq -> to_sq, then a single build on build_sq.
    Examples: Apollo, Athena, Minotaur, Pan.
    """
    to_sq: int
    build_sq: int

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        return (
            square_to_text(self.from_sq)
            + square_to_text(self.to_sq)
            + square_to_text(self.build_sq)
        )

    @classmethod
    def from_text(cls, move_text: str) -> "SingleBuildMove":
        if len(move_text) != 6:
            log_invalid_move(move_text)
            raise ValueError(f"{cls.__name__} text must be 6 chars, e.g. 'a1b2b3'")
        from_sq = text_to_square(move_text[0:2])
        to_sq   = text_to_square(move_text[2:4])
        build_sq= text_to_square(move_text[4:6])
        return cls(from_sq=from_sq, to_sq=to_sq, build_sq=build_sq)

@dataclass
class DoubleBuildMove(Move):
    """
    For gods who can build up to twice: from_sq -> to_sq, then build_sq_1, optional build_sq_2
    Examples: Demeter, Hephaestus.
    """
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
    def from_text(cls, move_text: str) -> "DoubleBuildMove":
        length = len(move_text)
        if length not in (6, 8):
            log_invalid_move(move_text)
            raise ValueError(f"{cls.__name__} text must be 6 or 8 chars")
        from_sq = text_to_square(move_text[0:2])
        to_sq   = text_to_square(move_text[2:4])
        build_sq_1 = text_to_square(move_text[4:6])
        build_sq_2 = None
        if length == 8:
            build_sq_2 = text_to_square(move_text[6:8])
        return cls(from_sq=from_sq, to_sq=to_sq,
                   build_sq_1=build_sq_1, build_sq_2=build_sq_2)


##############################################################################
# Gods that do single-step + single build
##############################################################################

@dataclass
class ApolloMove(SingleBuildMove):
    pass

@dataclass
class AthenaMove(SingleBuildMove):
    pass

@dataclass
class MinotaurMove(SingleBuildMove):
    pass

@dataclass
class PanMove(SingleBuildMove):
    pass

##############################################################################
# Gods that do single-step + optional second build
##############################################################################

@dataclass
class DemeterMove(DoubleBuildMove):
    pass

@dataclass
class HephaestusMove(DoubleBuildMove):
    pass

##############################################################################
# Gods with unique move signatures
##############################################################################

@dataclass
class ArtemisMove(Move):
    """
    Artemis can move up to twice:
      from_sq -> [mid_sq?] -> to_sq, then build_sq
    If mid_sq is None => single-step.
    """
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
        length = len(move_text)
        if length == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6])
            )
        elif length == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                mid_sq=text_to_square(move_text[2:4]),
                to_sq=text_to_square(move_text[4:6]),
                build_sq=text_to_square(move_text[6:8])
            )
        else:
            log_invalid_move(move_text)
            raise ValueError("ArtemisMove must be 6 or 8 chars.")

@dataclass
class HermesMove(Move):
    """
    Hermes: can do multiple ground-level steps:
      from_sq, squares[], build_sq
    e.g. 'a1b1b2b3' => from=a1, squares=[b1,b2], build=b3
    """
    squares: List[int]
    build_sq: int

    @property
    def final_sq(self) -> int:
        return self.squares[-1] if self.squares else self.from_sq

    def move_to_text(self) -> str:
        return (
            square_to_text(self.from_sq)
            + ''.join(square_to_text(sq) for sq in self.squares)
            + square_to_text(self.build_sq)
        )

    @classmethod
    def from_text(cls, move_text: str) -> "HermesMove":
        if len(move_text) < 4 or (len(move_text) % 2) != 0:
            log_invalid_move(move_text)
            raise ValueError("HermesMove must be even length >= 4")
        from_sq = text_to_square(move_text[0:2])
        build_sq = text_to_square(move_text[-2:])
        middle   = move_text[2:-2]
        squares  = [text_to_square(middle[i:i+2]) for i in range(0, len(middle), 2)]
        return cls(from_sq=from_sq, squares=squares, build_sq=build_sq)

@dataclass
class PrometheusMove(Move):
    """
    Prometheus: optional build first, then from_sq->to_sq, then build_sq.
    If optional_build is not None => we used the pre-move build.
    e.g. 'a1b2b3' => no optional build
         'a1b2b3c4' => optional build on c4
    """
    to_sq: int
    build_sq: int
    optional_build: Optional[int] = None

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        txt = square_to_text(self.from_sq) + square_to_text(self.to_sq) + square_to_text(self.build_sq)
        if self.optional_build is not None:
            txt += square_to_text(self.optional_build)
        return txt

    @classmethod
    def from_text(cls, move_text: str) -> "PrometheusMove":
        length = len(move_text)
        if length == 6:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6])
            )
        elif length == 8:
            return cls(
                from_sq=text_to_square(move_text[0:2]),
                to_sq=text_to_square(move_text[2:4]),
                build_sq=text_to_square(move_text[4:6]),
                optional_build=text_to_square(move_text[6:8])
            )
        else:
            log_invalid_move(move_text)
            raise ValueError("PrometheusMove must be 6 or 8 chars.")

@dataclass
class AtlasMove(Move):
    """
    Atlas can put a dome on build_sq by appending 'D' in the text:
      'a1b2b3' => no dome
      'a1b2b3D' => dome
    """
    to_sq: int
    build_sq: int
    dome: bool

    @property
    def final_sq(self) -> int:
        return self.to_sq

    def move_to_text(self) -> str:
        txt = square_to_text(self.from_sq) + square_to_text(self.to_sq) + square_to_text(self.build_sq)
        if self.dome:
            txt += "D"
        return txt

    @classmethod
    def from_text(cls, move_text: str) -> "AtlasMove":
        length = len(move_text)
        if length not in (6, 7):
            log_invalid_move(move_text)
            raise ValueError("AtlasMove must be 6 or 7 chars, e.g. 'a1b2b3' or 'a1b2b3D'")
        from_sq = text_to_square(move_text[0:2])
        to_sq   = text_to_square(move_text[2:4])
        build_sq= text_to_square(move_text[4:6])
        dome = (length == 7)
        if dome and move_text[6] != 'D':
            log_invalid_move(move_text)
            raise ValueError("AtlasMove: 7th char must be 'D' if present.")
        return cls(from_sq=from_sq, to_sq=to_sq, build_sq=build_sq, dome=dome)
