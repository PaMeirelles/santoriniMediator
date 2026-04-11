from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Tuple, List
from game.move import Move, ApolloMove, ArtemisMove, HermesMove, PrometheusMove, AtlasMove, DemeterMove, HephaestusMove, \
    MinotaurMove, PanMove, AthenaMove


class God(Enum):
    APOLLO = 0
    ARTEMIS = 1
    ATHENA = 2
    ATLAS = 3
    DEMETER = 4
    HEPHAESTUS = 5
    HERMES = 6
    MINOTAUR = 7
    PAN = 8
    PROMETHEUS = 9

@dataclass
class Pair:
    engine: str
    god: God

class ResultType(Enum):
    NORMAL_WIN = 1
    TIMEOUT = 2
    ILLEGAL_MOVE = 3

@dataclass
class Match:
    game_id: int
    starting_pos: str
    players: Tuple[Pair, Pair] # Gray / Blue
    time_ms: Tuple[int, int] # Gray / Blue
    winner: bool # true = Gray, false = Blue
    result_type: ResultType
    played_at: datetime
    moves: List[Move]


def string_to_god(god_name: str) -> God | None:
    try:
        return God[god_name.upper()]
    except KeyError:
        print(f"Invalid god name: {god_name}")
        return None


def god_to_string(god: God):
    return god.name.capitalize()


def get_move_from_string(move_str: str, god: God) -> Move:
    match god:
        case God.APOLLO:
            return ApolloMove(0, 0, 0).from_text(move_str)
        case God.ARTEMIS:
            return ArtemisMove(0, 0, 0).from_text(move_str)
        case God.HERMES:
            return HermesMove(0, [], 0).from_text(move_str)
        case God.PROMETHEUS:
            return PrometheusMove(0, 0, 0).from_text(move_str)
        case God.ATLAS:
            return AtlasMove(0, 0, 0, False).from_text(move_str)
        case God.DEMETER:
            return DemeterMove(0, 0, 0).from_text(move_str)
        case God.HEPHAESTUS:
            return HephaestusMove(0, 0, 0, 0).from_text(move_str)
        case God.MINOTAUR:
            return MinotaurMove(0, 0, 0).from_text(move_str)
        case God.PAN:
            return PanMove(0, 0, 0).from_text(move_str)
        case God.ATHENA:
            return AthenaMove(0, 0, 0).from_text(move_str)
        case _:
            raise Exception("Invalid god")