import unittest

from board import Board, God
from move import (
    Move, ApolloMove, ArtemisMove, AthenaMove, AtlasMove, DemeterMove,
    HephaestusMove, HermesMove, MinotaurMove, PanMove, PrometheusMove
)


###############################################################################
#                        HELPER FUNCTIONS / DEFINITIONS
###############################################################################

def make_position(
    blocks,        # list of 25 integers in [0..4]
    gray_workers,  # tuple of 2 squares for Gray
    blue_workers,  # tuple of 2 squares for Blue
    turn,          # 1 => Gray to move, -1 => Blue to move
    god_gray,      # a Gods enum (e.g. Gods.APOLLO)
    god_blue,
    athena_up=False # a Gods enum (e.g. Gods.ARTEMIS)
) -> str:
    """
    Creates the canonical 54-char position string:
      - 25 pairs of (block height + worker code)
      - 1 char for turn
      - 1 char for god_gray (its numeric value)
      - 1 char for god_blue (its numeric value)
      - 1 char if athena went up last turn
    """
    # Validate input quickly
    if len(blocks) != 25:
        raise ValueError("blocks must have length 25")
    for b in blocks:
        if not (0 <= b <= 4):
            raise ValueError("Invalid block height, must be 0..4")
    # Build the first 50 chars
    position_chars = []
    for sq in range(25):
        # block height
        h = blocks[sq]
        # worker code
        if sq == gray_workers[0] or sq == gray_workers[1]:
            w = 'G'
        elif sq == blue_workers[0] or sq == blue_workers[1]:
            w = 'B'
        else:
            w = 'N'
        position_chars.append(str(h))
        position_chars.append(w)

    # Turn: '0' => Gray, '1' => Blue
    turn_char = '0' if turn == 1 else '1'
    # Convert gods
    god_gray_char = str(god_gray.value)
    god_blue_char = str(god_blue.value)

    athena_up = '1' if athena_up else '0'

    return ''.join(position_chars) + turn_char + god_gray_char + god_blue_char + athena_up


def create_board(
    blocks=None,
    gray_workers=(0,10),
    blue_workers=(23,24),
    turn=1,
    god_gray=God.APOLLO,
    god_blue=God.ARTEMIS
) -> Board:
    """
    Creates and returns a Board with default or custom parameters.
    By default, everything is set to minimal valid (all blocks=0,
    workers in squares 0,1,23,24, Gray=APOLLO, Blue=ARTEMIS).
    """
    if blocks is None:
        blocks = [0]*25

    pos_str = make_position(
        blocks,
        gray_workers,
        blue_workers,
        turn,
        god_gray,
        god_blue
    )
    return Board(pos_str)


def moves_equal(m1: Move, m2: Move) -> bool:
    """
    Helper to compare two Move objects quickly if needed.
    (Only works if they're the same type and have same squares.)
    """
    if type(m1) != type(m2):
        return False
    return (
        m1.from_sq == m2.from_sq and
        m1.final_sq == m2.final_sq
    )


###############################################################################
#                          TEST POSITION PARSING
###############################################################################
class TestPositionParsing(unittest.TestCase):

    def test_valid_parsing(self):
        """
        Test a few valid positions with different turns/gods.
        """
        # All blocks = 0, Gray workers at 0,1; Blue workers at 23,24
        # Turn = Gray's turn, Gray=Apollo(1), Blue=Artemis(2)
        blocks = [0]*25
        pos_str = make_position(blocks, (0,1), (23,24), 1, God.APOLLO, God.ARTEMIS)
        board = Board(pos_str)
        self.assertEqual(board.turn, 1)
        self.assertEqual(board.gods[0], God.APOLLO)
        self.assertEqual(board.gods[1], God.ARTEMIS)
        self.assertEqual(board.workers, [0,1,23,24])
        self.assertEqual(board.blocks, blocks)

        # Now try turn = Blue, Gray=Pan(9), Blue=Prometheus(10)
        # And have some non-zero blocks
        blocks = [2,2,0,4,0] + [1]*20
        pos_str = make_position(blocks, (0,1), (2,3), -1, God.PAN, God.PROMETHEUS)
        board = Board(pos_str)
        self.assertEqual(board.turn, -1)
        self.assertEqual(board.gods[0], God.PAN)
        self.assertEqual(board.gods[1], God.PROMETHEUS)
        self.assertEqual(board.workers, [0,1,2,3])
        self.assertEqual(board.blocks, blocks)

    def test_invalid_length(self):
        # Should raise ValueError if not length 54
        with self.assertRaises(ValueError):
            Board("012345")  # way too short

        with self.assertRaises(ValueError):
            Board("0"*54)    # length 54

    def test_invalid_block_heights(self):
        # Give a block height of 9 (invalid)
        bad_blocks = [0]*24 + [9]
        with self.assertRaises(ValueError):
            Board(make_position(bad_blocks, (0,1), (2,3), 1, God.APOLLO, God.ARTEMIS))

    def test_invalid_worker_codes(self):
        # Use 'X' instead of 'G', 'B', or 'N'
        # We'll just hand-construct a minimal string so we can inject 'X'
        blocks = [0]*25
        base_str = make_position(blocks, (0,1), (2,3), 1, God.APOLLO, God.ARTEMIS)
        # base_str[1] is the worker code for square 0, so let's replace it with 'X'
        bad_str = base_str[:1] + 'X' + base_str[2:]
        with self.assertRaises(ValueError):
            Board(bad_str)

    def test_invalid_worker_count(self):
        # We try to put 3 gray workers
        # E.g. squares 0,1,2 => Gray, squares 3,4 => Blue
        blocks = [0]*25
        # We'll manually generate the string:
        # We only want (0,1,2) as Gray, (3,4) as Blue => 5 total workers => invalid
        # We'll just do something naive:
        pos_list = []
        for i in range(25):
            if i in (0,1,2):
                pos_list.append("0G")
            elif i in (3,4):
                pos_list.append("0B")
            else:
                pos_list.append("0N")
        # Turn + gods
        pos_str = "".join(pos_list) + "012"  # '0' => Gray turn, '1','2' => APOLLO, ARTEMIS
        with self.assertRaises(ValueError):
            Board(pos_str)

    def test_invalid_turn_char(self):
        blocks = [0]*25
        # Turn must be '0' or '1'. Let's set it to '5' for example
        pos_str = make_position(blocks, (0,1), (2,3), 1, God.APOLLO, God.ARTEMIS)
        # Replace position[50] with '5'
        pos_str = pos_str[:50] + '5' + pos_str[51:]
        with self.assertRaises(ValueError):
            Board(pos_str)

    def test_invalid_god_char(self):
        # God must be an integer in 1..10
        blocks = [0]*25
        # We'll put 'X' in position[51]
        pos_str = make_position(blocks, (0,1), (2,3), 1, God.APOLLO, God.ARTEMIS)
        pos_str = pos_str[:51] + 'X' + pos_str[52:]
        with self.assertRaises(ValueError):
            Board(pos_str)

    def test_athena_flag_parsed(self):
        """
        Test that the final character in the position string sets the 'prevent_up_next_turn' flag.
        """
        blocks = [0] * 25
        blocks[4] = 1
        pos_str = make_position(blocks, (0, 1), (2, 3), -1, God.ATHENA, God.APOLLO, athena_up=True)
        board = Board(pos_str)
        move = ApolloMove(3, 4, 3)
        self.assertFalse(board.move_is_valid(move))


###############################################################################
#                     TEST GENERAL/COMMON MOVEMENT RULES
###############################################################################
class TestGeneralRules(unittest.TestCase):

    def test_move_down_any_number_of_squares(self):
        """
        You can step down from e.g. height=3 to height=0 without restriction,
        so long as adjacency is satisfied.
        """
        blocks = [0]*25
        blocks[0] = 3
        # Gray worker on square 0
        board = create_board(blocks=blocks, gray_workers=(0,1), blue_workers=(23,24))

        # Let's do a standard "ApolloMove" because that’s what Gray has by default in create_board
        # Move from 0 -> 5 (assuming 5 is adjacent to 0). We'll set final_sq=5, build_sq=6 for example.
        # Our adjacency structure presumably allows 0->5 because 0 and 5 share an edge (since NEIGHBOURS is 5 wide).
        move = ApolloMove(from_sq=0, to_sq=5, build_sq=6)

        # We must ensure adjacency is indeed correct in your code: 0’s neighbors typically are 1 and 5 and 6 in a 5x5?
        # We'll assume it's correct. The block difference is 0 - 3 = -3 => allowed.
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        self.assertEqual(board.workers[0], 5)   # worker moved from 0->5
        self.assertEqual(board.blocks[6], 1)    # built +1 on square 6

    def test_can_build_where_you_came_from(self):
        """
        If the square you came from is still adjacent to your final position,
        you can build there.
        E.g. from 0 -> 1, then build at 0 if it is legal (adjacent to 1).
        """
        blocks = [0]*25
        board = create_board(blocks=blocks, gray_workers=(0,2), blue_workers=(23,24))

        # Move from 0 -> 1, build at 0
        move = ApolloMove(from_sq=0, to_sq=1, build_sq=0)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        self.assertEqual(board.workers[0], 1)
        self.assertEqual(board.blocks[0], 1)  # built +1

    def test_cant_warp_around_the_board(self):
        """
        Attempt a move from square 0 to square 24 (non-adjacent).
        Should be invalid.
        """
        board = create_board()
        move = ApolloMove(from_sq=0, to_sq=24, build_sq=1)
        self.assertFalse(board.move_is_valid(move))

    def test_cant_build_on_square_adjacent_to_fromsq_but_not_tosq(self):
        """
        E.g. from 0->1, then attempt building on a square that’s adjacent to 0 but not to 1.
        This must fail (since you must build adjacent to your final position).
        """
        board = create_board()
        # Suppose squares 0 & 2 are neighbors, but squares 1 & 2 are NOT neighbors.
        # If so, you can’t build on 2 after moving 0->1.
        # We’ll try that move: from_sq=0, final_sq=1, build_sq=2
        move = ApolloMove(from_sq=1, to_sq=2, build_sq=5)
        self.assertFalse(board.move_is_valid(move))

    def test_no_build_on_worker(self):
        board = create_board()
        move = ApolloMove(from_sq=0, to_sq=5, build_sq=10)
        self.assertFalse(board.move_is_valid(move))

    def test_win_not_registered(self):
        blocks = [0]*25
        blocks[0] = 2
        blocks[1] = 3
        board = create_board(blocks=blocks, gray_workers=(0,2), blue_workers=(23,24), turn=1)
        board.make_move(ApolloMove(from_sq=0, to_sq=1, build_sq=0))
        self.assertEqual(board.check_state(), 1)


###############################################################################
#                           TEST APOLLO
###############################################################################
class TestApollo(unittest.TestCase):

    def test_swap_up_one_height(self):
        """
        Apollo can move into an opponent's space if it’s an adjacent square with occupant.
        Check that we can do so if the occupant is on a block that’s 1 higher or any lower.
        """
        blocks = [0]*25
        blocks[1] = 1  # square 1 is height=1
        # Gray at 0, Blue at 1. Gray's turn, Gray=Apollo, Blue=Apollo
        board = create_board(blocks=blocks, gray_workers=(0,2), blue_workers=(1,3),
                             turn=1, god_gray=God.APOLLO, god_blue=God.APOLLO)

        # from 0->1, occupant is Blue. That occupant is on height=1, which is only 1 higher than height=0 => valid
        # build on 2 for example
        move = ApolloMove(from_sq=0, to_sq=1, build_sq=6)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        # They swap, so Blue’s worker is now on 0, Gray’s worker on 1
        self.assertEqual(board.workers, [1,2,0,3])  # worker0->1, worker1 still=2, worker2->0, worker3=3
        self.assertEqual(board.blocks[6], 1)        # built +1

    def test_can_only_swap_with_enemy(self):
        """
        Apollo cannot swap with your own worker.
        So if occupant is an ally, it must fail.
        """
        # Gray at 0,1; Blue at 23,24. Gray tries to swap with square=1 => occupant is Gray => invalid.
        board = create_board(gray_workers=(0,1), blue_workers=(23,24),
                             turn=1, god_gray=God.APOLLO, god_blue=God.ARTEMIS)
        move = ApolloMove(from_sq=0, to_sq=1, build_sq=2)
        self.assertFalse(board.move_is_valid(move))

    def test_no_moves_but_apollo_swap_saves_you(self):
        """
        Suppose you'd normally have no legal moves (all squares are blocked or too high),
        but an adjacent enemy worker can be swapped. That is a valid move and thus you
        do NOT lose automatically.
        """
        # We'll create a scenario where Gray is on square 0 with height=2,
        # and every adjacent square is height=4 except square 1 which is an enemy occupant.
        # Because of Apollo, Gray can swap with the occupant on 1 (assuming 1 is not dome).
        blocks = [4]*25
        # Let’s say we set square 0 = 2, square 1 = 2 (not a dome) but occupant is Blue
        blocks[0] = 2
        blocks[1] = 2
        blocks[2] = 2
        blocks[3] = 2
        blocks[7] = 3

        # Gray at 0, second Gray worker at 2 (irrelevant?), Blue at 1,3
        board = create_board(blocks=blocks, gray_workers=(0,2), blue_workers=(1,3),
                             turn=1, god_gray=God.APOLLO, god_blue=God.APOLLO)

        # If not for Apollo swap, everything else is 4 => no moves. But we do have an Apollo swap with occupant on 1.
        # We'll do from_sq=0 -> to_sq=1, build at square=2 for instance.
        move = ApolloMove(from_sq=0, to_sq=1, build_sq=7)
        self.assertTrue(board.move_is_valid(move))  # This means we are not forced-losing.
        # We can even apply the move
        board.make_move(move)
        self.assertEqual(board.workers[0], 1)  # Gray’s worker on 1
        self.assertEqual(board.workers[2], 0)  # Blue’s worker swapped onto 0

    def test_no_build_on_from_when_swapping(self):
        board = create_board(gray_workers=(0,1), blue_workers=(2,3))
        move = ApolloMove(from_sq=1, to_sq=2, build_sq=1)
        self.assertFalse(board.move_is_valid(move))

    def test_no_swap_can_build(self):
        blocks = [0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        board = Board(make_position(blocks, (7, 15), (0, 2), 1, God.APOLLO, God.ARTEMIS))
        move = ApolloMove(from_sq=7, to_sq=3, build_sq=7)
        self.assertTrue(board.move_is_valid(move))

    def test_misc(self):
        board = Board("2N1N1N1N1N2N4N4N4N4N1N3N1N4N0G3N4N1N4N1G2N1B4N4N1B0060")
        state = board.check_state()
        self.assertEqual(state, -1)

    def test_tricky_swap(self):
        blocks = [0] * 25
        board = create_board(blocks=blocks, gray_workers=(7, 11), blue_workers=(6, 12), turn=-1, god_blue=God.APOLLO)
        move = ApolloMove(from_sq=6, to_sq=7, build_sq=2)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        self.assertEqual(board.workers[0], 6)
        self.assertEqual(board.workers[2], 7)


###############################################################################
#                           TEST ARTEMIS
###############################################################################
class TestArtemis(unittest.TestCase):

    def test_cannot_move_back_to_where_you_started(self):
        """
        Artemis gets up to two moves, but cannot return to the original square.
        """
        # Gray=Artemis
        board = create_board(god_gray=God.ARTEMIS, god_blue=God.ARTEMIS)
        # Attempt from 0->1->0
        move = ArtemisMove(from_sq=0, mid_sq=1, to_sq=0, build_sq=5)
        self.assertFalse(board.move_is_valid(move))

    def test_can_move_only_once_if_she_wants(self):
        """
        Artemis can either make a single move or a double move.
        So from 0->1 with mid_sq=None is also valid.
        """
        board = create_board(god_gray=God.ARTEMIS, god_blue=God.ARTEMIS)
        # single step from 0->1
        move = ArtemisMove(from_sq=0, to_sq=6, build_sq=5)
        self.assertTrue(board.move_is_valid(move))


###############################################################################
#                           TEST ATHENA
###############################################################################
class TestAthena(unittest.TestCase):

    def test_athena_power_works(self):
        """
        If Athena moves up, the opponent cannot move up on their next turn.
        Test that scenario explicitly.
        """
        # Let’s have Gray=Athena, Blue=Apollo for variety
        blocks = [0]*25
        # squares 0 => height=0, 1 => height=1
        blocks[1] = 1
        board = create_board(blocks=blocks,
                             gray_workers=(0,2), blue_workers=(3,4),
                             turn=1, god_gray=God.ATHENA, god_blue=God.APOLLO)

        # Gray moves from 0 (height=0) to 1 (height=1) => that's an "up" move
        move_athena = AthenaMove(from_sq=0, to_sq=1, build_sq=5)
        self.assertTrue(board.move_is_valid(move_athena))
        board.make_move(move_athena)
        # Now it's Blue’s turn, but they have the Apollo power.
        # They cannot move up if that’s required. Let’s see if from 3->8 is an up move (assuming blocks[3]=0, blocks[8]=1).
        blocks[3] = 0
        blocks[8] = 1
        # We can manipulate the existing board:
        board.blocks[3] = 0
        board.blocks[8] = 1

        # Blue tries from 3->8 (adjacent?), that’s an up move => should fail due to Athena’s effect
        move_apollo = ApolloMove(from_sq=3, to_sq=8, build_sq=2)
        self.assertFalse(board.move_is_valid(move_apollo))

    def test_athena_opponent_no_move_loses(self):
        """
        If Athena's power forbids the opponent from moving up,
        and that means the opponent has 0 possible moves, they lose immediately.
        """

        blocks = [0]*25
        blocks[2] = 1
        blocks[5] = 1
        blocks[6] = 1
        blocks[7] = 1

        # Gray turn
        board = create_board(blocks=blocks,
                             gray_workers=(0,1), blue_workers=(3,4),
                             turn=-1, god_gray=God.APOLLO, god_blue=God.ATHENA)

        # Gray moves up somehow => e.g. from 0->5
        move_athena = AthenaMove(from_sq=3, to_sq=2, build_sq=8)
        self.assertTrue(board.move_is_valid(move_athena))
        board.make_move(move_athena)
        self.assertEqual(board.check_state(), -1)  # 1 => Gray wins

    def test_athena_build_on_from(self):
        blocks = [0]*25
        blocks[2] = 1
        board = create_board(blocks=blocks, gray_workers=(0,1), blue_workers=(3,4), turn=1, god_gray=God.ATHENA)
        move_athena = AthenaMove(from_sq=1, to_sq=2, build_sq=1)
        self.assertTrue(board.move_is_valid(move_athena))
        board.make_move(move_athena)
        self.assertTrue(board.prevent_up_next_turn)

###############################################################################
#                           TEST ATLAS
###############################################################################
class TestAtlas(unittest.TestCase):

    def test_no_one_moves_on_domes(self):
        """
        Once a square has block=4 (dome), no one can move there anymore.
        Check that the board disallows it for any standard move.
        """
        # Gray=Atlas. We'll do a normal Atlas move but test that after building a dome,
        # next turn the opponent can't move onto that dome.
        blocks = [0]*25
        board = create_board(blocks=blocks,
                             gray_workers=(0,2), blue_workers=(1,3),
                             turn=1, god_gray=God.ATLAS, god_blue=God.APOLLO)
        # Gray uses Atlas power to move from 0->5, then build a dome at 6
        move_atlas = AtlasMove(from_sq=0, to_sq=5, build_sq=6, dome=True)
        self.assertTrue(board.move_is_valid(move_atlas))
        board.make_move(move_atlas)
        self.assertEqual(board.blocks[6], 4)  # Dome

        # Now Blue tries to move onto 6 => invalid
        move_blue = ApolloMove(from_sq=1, to_sq=6, build_sq=2)
        self.assertFalse(board.move_is_valid(move_blue))


###############################################################################
#                           TEST DEMETER
###############################################################################
class TestDemeter(unittest.TestCase):

    def test_cannot_build_twice_on_same_square(self):
        """
        Demeter can build twice, but NOT on the same square.
        """
        # Gray=Demeter
        board = create_board(god_gray=God.DEMETER, god_blue=God.ARTEMIS)
        # Attempt from 0->1, build_sq_1=2, build_sq_2=2 => invalid
        move = DemeterMove(from_sq=0, to_sq=1, build_sq_1=2, build_sq_2=2)
        self.assertFalse(board.move_is_valid(move))

    def test_can_build_only_once_if_desired(self):
        """
        Demeter’s second build is optional (build_sq_2 can be None).
        """
        board = create_board(god_gray=God.DEMETER, god_blue=God.ARTEMIS)
        # from 0->1, build at 2 only once
        move = DemeterMove(from_sq=0, to_sq=1, build_sq_1=2)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        self.assertEqual(board.blocks[2], 1)


###############################################################################
#                           TEST HEPHAESTUS
###############################################################################
class TestHephaestus(unittest.TestCase):

    def test_cannot_build_twice_on_different_squares(self):
        """
        Hephaestus's second build must be on the same square as the first.
        """
        board = create_board(god_gray=God.HEPHAESTUS, god_blue=God.ARTEMIS)
        # Attempt from 0->1, build1=2, build2=3 => invalid
        move = HephaestusMove(from_sq=0, to_sq=1, build_sq_1=2, build_sq_2=3)
        self.assertFalse(board.move_is_valid(move))

    def test_can_build_only_once_if_desired(self):
        """
        Hephaestus's second build is optional.
        """
        board = create_board(god_gray=God.HEPHAESTUS, god_blue=God.ARTEMIS)
        move = HephaestusMove(from_sq=0, to_sq=1, build_sq_1=2)
        self.assertTrue(board.move_is_valid(move))

    def test_cannot_dome_on_second_build(self):
        """
        If the second build would raise the block from 3->4, that’s a dome.
        Hephaestus's code forbids building a dome on the second block
        (the code checks `self.blocks[build_sq_2] <= 2`).
        """
        blocks = [0]*25
        blocks[2] = 2
        board = create_board(blocks=blocks, god_gray=God.HEPHAESTUS)
        move = HephaestusMove(from_sq=0, to_sq=1, build_sq_1=2, build_sq_2=2)
        self.assertFalse(board.move_is_valid(move))

    def test_can_dome_normally(self):
        """
        Hephaestus can build a single block that results in a dome
        if the square was already 3. That’s a normal single build to 4, allowed.
        """
        blocks = [0]*25
        blocks[2] = 3  # so building once => 4 => dome
        board = create_board(blocks=blocks, god_gray=God.HEPHAESTUS)

        # Single build from 0->1, build at 2 => from 3->4 => dome => that should be allowed
        # if we do only one build.
        move = HephaestusMove(from_sq=0, to_sq=1, build_sq_1=2)
        self.assertTrue(board.move_is_valid(move))

    def test_misc(self):
        board = Board("0N3N3N0G2G2N3N4N4N4N2N3N3N1B3N0N1N3N0B1N0N0N1N0N1N0580")
        state = board.check_state()
        self.assertEqual(state, -1)

###############################################################################
#                           TEST HERMES
###############################################################################
class TestHermes(unittest.TestCase):

    def test_can_survive_by_standing_still(self):
        blocks = [0]*25
        blocks[2] = 2
        blocks[5] = 2
        blocks[6] = 2
        blocks[7] = 2
        board = create_board(blocks=blocks, gray_workers=(0, 1), blue_workers=(3, 4), god_gray=God.HERMES, god_blue=God.ARTEMIS)
        self.assertEqual(board.check_state(), 0)

    def test_cannot_move_up_while_using_power(self):
        """
        If you choose multiple ground moves, they must remain on level 0.
        So if the final move tries to go up to 1, that's invalid for multi-step.
        """
        blocks = [0]*25
        # let’s say squares 1=1 in height => that’s up
        blocks[1] = 1
        board = create_board(blocks=blocks, god_gray=God.HERMES)

        # Attempt multi-step squares=[1,2], but 1 is height=1 => fails
        # from 0->1 is an “up.” The code specifically checks each step is ground level (0).
        move = HermesMove(from_sq=0, build_sq=3, squares=[1,2])
        self.assertFalse(board.move_is_valid(move))

    def test_can_move_on_h1(self):
        blocks = [1]*25
        board = create_board(blocks=blocks, god_gray=God.HERMES)
        move = HermesMove(from_sq=0, build_sq=3, squares=[1,2])
        self.assertTrue(board.move_is_valid(move))

    def test_not_dead_on_h1(self):
        blocks = [1]*25
        blocks[2] = 3
        blocks[5] = 3
        blocks[6] = 3
        blocks[7] = 3
        board = create_board(blocks=blocks, god_gray=God.HERMES, gray_workers=(0, 1), blue_workers=(3, 4))

        state = board.check_state()
        self.assertEqual(state, 0)


###############################################################################
#                           TEST MINOTAUR
###############################################################################
class TestMinotaur(unittest.TestCase):

    def test_can_only_push_where_you_can_move(self):
        """
        If from_sq->to_sq is not a valid move (e.g. 2+ levels up or not adjacent),
        you can’t push the occupant even if occupant is an enemy.
        """
        blocks = [0]*25
        blocks[1] = 2  # too high to climb if from_sq=0 has height=0 => difference=2 => not allowed
        board = create_board(blocks=blocks,
                             gray_workers=(0,2), blue_workers=(1,3),
                             god_gray=God.MINOTAUR, god_blue=God.APOLLO)
        # Attempt push from 0->1 => that’s up 2 => invalid
        move = MinotaurMove(from_sq=0, to_sq=1, build_sq=5)
        self.assertFalse(board.move_is_valid(move))

    def test_cannot_push_off_edge(self):
        """
        If the opponent stands on the edge and we push them "off board",
        that is invalid.
        """
        # squares in the top-left corner, from=0 -> -5 is nonsense => we can’t do that.
        board = create_board(god_gray=God.MINOTAUR, god_blue=God.APOLLO)
        # Suppose Blue is at 5, Gray tries from 0->5 => pushing occupant from 5->10 is fine.
        # But if occupant is at a corner and the next push square is out of [0..24], invalid.
        move = MinotaurMove(from_sq=0, to_sq=5, build_sq=10)
        # But let's force occupant to be on 5? Actually let's do that:
        board.workers[2] = 5  # Blue worker is at index=2
        # 0->5 => occupant gets pushed to => 10? That’s inside board. This should be valid if heights allow.
        # Let’s see if it’s valid. By default blocks are all 0, so up difference = 0 => that’s fine.
        # We want to test the failure if push goes to e.g. -5.
        # So let's do from 5->0 => occupant on 0 => push to -5 => invalid.
        # We'll invert the positions for clarity:
        board.workers[0] = 5  # Gray
        board.workers[2] = 0  # Blue
        # Now Gray tries from 5->0 => occupant is on 0 => push square => -5 => out of range => invalid.
        move_fail = MinotaurMove(from_sq=5, to_sq=0, build_sq=1)
        self.assertFalse(board.move_is_valid(move_fail))

    def test_cannot_build_where_you_push(self):
        board = create_board(gray_workers=(0,1), blue_workers=(2,4), god_gray=God.MINOTAUR, god_blue=God.APOLLO)
        move = MinotaurMove(from_sq=1, to_sq=2, build_sq=3)
        self.assertFalse(board.move_is_valid(move))

    def test_push_to_3_doesnt_win(self):
        blocks = [0]*25
        blocks[2] = 2
        blocks[3] = 2
        blocks[4] = 3
        board = create_board(blocks=blocks, gray_workers=(0, 2), blue_workers=(3, 5), god_gray=God.MINOTAUR)
        move = MinotaurMove(from_sq=2, to_sq=3, build_sq=2)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        self.assertEqual(board.check_state(), 0)

    def test_cant_push_offboard(self):
        blocks = [0]*25
        board = create_board(blocks=blocks, gray_workers=(1, 2), blue_workers=(5, 3), turn = 1, god_gray=God.MINOTAUR)
        move = MinotaurMove(from_sq=1, to_sq=5, build_sq=1)
        self.assertFalse(board.move_is_valid(move))

###############################################################################
#                           TEST PAN
###############################################################################
class TestPan(unittest.TestCase):

    def test_pan_win_by_moving_down_two(self):
        """
        If Pan steps down 2+ levels, that triggers an immediate win.
        """
        # squares 0=3 (top), squares 1=1
        blocks = [0]*25
        blocks[0] = 2
        # Gray=Pan
        board = create_board(blocks=blocks, gray_workers=(0,2), turn=1, god_gray=God.PAN)

        # Move from 0 (height=2) down to 1 (height=0) => difference= -2 => Pan wins instantly
        move = PanMove(from_sq=0, to_sq=1, build_sq=5)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        # Now check the board’s check_state => Pan is Gray => returns 1 if Pan wins
        self.assertEqual(board.check_state(), 1)

    def test_pan_win_as_blue(self):
        blocks = [0] * 25
        blocks[0] = 2
        # Gray=Pan
        board = create_board(blocks=blocks,gray_workers=(22, 23),  blue_workers=(0, 2), turn=-1, god_blue=God.PAN)

        # Move from 0 (height=2) down to 1 (height=0) => difference= -2 => Pan wins instantly
        move = PanMove(from_sq=0, to_sq=1, build_sq=5)
        self.assertTrue(board.move_is_valid(move))
        board.make_move(move)
        # Now check the board’s check_state => Pan is Gray => returns 1 if Pan wins
        self.assertEqual(board.check_state(), -1)

###############################################################################
#                           TEST PROMETHEUS
###############################################################################
class TestPrometheus(unittest.TestCase):

    def test_can_move_normally_if_you_want(self):
        """
        If Prometheus does not do the optional build first,
        then it’s effectively a normal single-step move + build.
        """
        board = create_board(god_gray=God.PROMETHEUS)
        # from 0->1, then build at 2, with no optional build => valid
        move = PrometheusMove(from_sq=0, to_sq=1, build_sq=2)
        self.assertTrue(board.move_is_valid(move))

    def test_second_build_must_be_before_moving(self):
        """
        If 'optional_build' is not None, it is done before the move.
        Then we do a normal build after the move. That’s the sequence.
        """
        # We'll just verify that the code requires from_sq to be adjacent to optional_build
        # (which it does: `_build_ok_sq(from_sq, move.optional_build)`).
        # Then we do from_sq->to_sq, build_sq => final building.
        board = create_board(god_gray=God.PROMETHEUS)
        # Suppose from=0, optional_build=5 => must be adjacent to 0,
        # then move to 1 => must be valid single step, then build at 2 => must be adjacent to 1
        move = PrometheusMove(from_sq=0, to_sq=1, build_sq=2, optional_build=5)
        self.assertTrue(board.move_is_valid(move))

    def test_cannot_move_up_if_built_before_moving(self):
        """
        If you do the optional build, you cannot move UP afterwards.
        i.e. blocks[to_sq] <= blocks[from_sq].
        """
        blocks = [0]*25
        blocks[1] = 1  # going from 0=0 -> 1=1 => that's an up
        board = create_board(blocks=blocks, god_gray=God.PROMETHEUS)

        # If we set optional_build=5 => that means we built first => cannot go up
        move = PrometheusMove(from_sq=0, to_sq=1, build_sq=2, optional_build=5)
        # Should fail
        self.assertFalse(board.move_is_valid(move))

    def test_cannot_move_up_to_newly_built(self):
        blocks = [0] * 25
        board = create_board(gray_workers=(0,1), blocks=blocks, god_gray=God.PROMETHEUS)

        # If we set optional_build=5 => that means we built first => cannot go up
        move = PrometheusMove(from_sq=0, to_sq=5, build_sq=10, optional_build=5)
        self.assertFalse(board.move_is_valid(move))


###############################################################################
#                                RUN TESTS
###############################################################################
if __name__ == '__main__':
    unittest.main()