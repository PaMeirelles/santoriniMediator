from game.board import Board
from game.move import (
    Move, SingleBuildMove, DoubleBuildMove, ArtemisMove,
    HermesMove, PrometheusMove, AtlasMove
)


def starting_position_to_bytes(position: str | Board) -> bytes:
    if isinstance(position, str):
        board = Board(position)
    else:
        board = position

    w0, w1 = sorted(board.workers[0:2])
    w2, w3 = sorted(board.workers[2:4])

    packed_int = (w0 << 15) | (w1 << 10) | (w2 << 5) | w3
    return packed_int.to_bytes(3, byteorder='big')


def move_to_bytes(move: Move) -> bytes:
    from_sq = move.from_sq
    to_sq = move.final_sq
    extra_sq = 31  # Usado para build_sq_2, mid_sq, optional_build
    atlas_flag = 0

    match move:
        case SingleBuildMove(build_sq=b_sq):
            build_sq = b_sq
        case DoubleBuildMove(build_sq_1=b1, build_sq_2=b2):
            build_sq = b1
            if b2 is not None:
                extra_sq = b2
        case AtlasMove(build_sq=b_sq, dome=is_dome):
            build_sq = b_sq
            if is_dome:
                atlas_flag = 1
        case _:  # Equivalent to F# wildcard '_'
            build_sq = 31  # 31 (0b11111) representa nulo/vazio, já que as casas vão de 0 a 24.

    # Empacota os bits na ordem definida (21 bits no total)
    # [Atlas: 1 bit] [From: 5 bits] [To: 5 bits] [Build: 5 bits] [Extra: 5 bits]
    packed = (atlas_flag << 20) | (from_sq << 15) | (to_sq << 10) | (build_sq << 5) | extra_sq

    return packed.to_bytes(3, byteorder='big')