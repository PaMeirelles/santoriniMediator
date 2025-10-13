# Santorini Game Protocol Documentation

This document provides a comprehensive explanation of the data formats used in this Santorini implementation, covering board state representation and the textual move protocol. It is intended for developers working with the game engine or any related tools.

## 1. Board Representation

The state of the game is primarily managed through two textual formats: the coordinate system for individual squares and a 54-character string that captures the entire board state.

### 1.1. Coordinate System

Each of the 25 squares on the 5x5 board is identified using algebraic notation.

#### String Notation

A square is represented by a two-character string:

* **Column**: A lower-case letter from `a` to `e`.
* **Row**: A digit from `1` to `5`.

The bottom-left corner is `a1`, and the top-right is `e5`.



#### Internal Representation (Integer)

For computational efficiency, square coordinates are converted to and from integers ranging from 0 to 24.

* `a1` = 0
* `b1` = 1
* `e1` = 4
* `a2` = 5
* `e5` = 24

The conversion logic is as follows:

* **`text_to_square(square_text)`**: `(col_number - 1) * 5 + (row_letter - 'a')`
* **`square_to_text(square_index)`**: The inverse of the above calculation.

### 1.2. Full Board State String

The entire game state is encapsulated in a 54-character string. This format is used to pass board positions to the game engine.

**Format:** `[Block/Worker Info (50 chars)][Turn (1 char)][God P1 (1 char)][God P2 (1 char)][Athena Effect (1 char)]`

| **Index** | **Length** | **Description** | **Example Values** |
| :--- | :--- | :--- | :--- |
| 0-49 | 50 | Heights and worker positions for all 25 squares. | `0N1G2N...` |
| 50 | 1 | Current player's turn. | `0` (Gray/P1), `1` (Blue/P2) |
| 51 | 1 | God ID for Player 1 (Gray). | `0` (Apollo), `1` (Artemis), etc. |
| 52 | 1 | God ID for Player 2 (Blue). | `7` (Minotaur), `9` (Prometheus), etc. |
| 53 | 1 | Athena's "prevent opponent moving up" status. | `0` (Inactive), `1` (Active) |

#### Block and Worker Section (Chars 0-49)

This section consists of 25 two-character pairs. Each pair describes a single square, starting from `a1` (index 0) up to `e5` (index 24).

For each square `i`:

* **`board_str[2*i]`**: A digit `0`-`4` representing the block height.
* **`board_str[2*i + 1]`**: A character indicating occupation:
    * `G`: Occupied by a Gray (Player 1) worker.
    * `B`: Occupied by a Blue (Player 2) worker.
    * `N`: No worker (`None`).

## 2. Engine Communication Protocol

Communication with the game engine follows a simple command-based protocol. The two primary commands are `position` and `go`.

### 2.1. The `position` Command

This command sets the current board state for the engine. It must be followed by the 54-character board state string.

**Format**: `position [board_state_string]`
**Example**: `position 0N1G2N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0N0B1B0N00790`

The format of the `[board_state_string]` is detailed in section 1.2.

### 2.2. The `go` Command

This command instructs the engine to start calculating the best move from the current position. The engine's response will be the best move it found.

**Format**: `go [time_options]`
**Response Format**: `bestmove [move_string]`

The `[move_string]` is a textual representation of the move, which varies depending on the active god power. The specific formats are detailed below.

## 3. Move String Formats

Each god has a unique power that influences how its moves are structured and encoded in the `[move_string]`.

### 3.1. Standard Move (`Apollo`, `Athena`, `Minotaur`, `Pan`)

These gods perform a standard "move then build" turn.

* **Text Representation**: 6 characters: `[from_sq][to_sq][build_sq]`
* **Example**: `a1b2c3` (Move from `a1` to `b2`, then build on `c3`).

### 3.2. **Artemis**

Artemis can move one additional time.

* **Text Representation**:
    * **6 chars**: `[from_sq][to_sq][build_sq]` (Standard one-step move)
    * **8 chars**: `[from_sq][mid_sq][to_sq][build_sq]` (Two-step move)
* **Example**: `a1b2c2d2` (Move from `a1` to `c2` via `b2`, then build on `d2`).

### 3.3. **Atlas**

Atlas can build a dome on any level.

* **Text Representation**:
    * **6 chars**: `[from_sq][to_sq][build_sq]` (Standard build)
    * **7 chars**: `[from_sq][to_sq][build_sq]D` (Build a dome)
* **Example**: `a1b2c3D` (Move from `a1` to `b2`, build a dome on `c3`).

### 3.4. **Demeter**

Demeter can build a second time on a different square.

* **Text Representation**:
    * **6 chars**: `[from_sq][to_sq][build_sq_1]` (Standard single build)
    * **8 chars**: `[from_sq][to_sq][build_sq_1][build_sq_2]` (Two builds)
* **Example**: `a1b2c3d4` (Move from `a1` to `b2`, build on `c3`, then build on `d4`).

### 3.5. **Hephaestus**

Hephaestus can build a second block on top of the first, but not to create a dome.

* **Text Representation**:
    * **6 chars**: `[from_sq][to_sq][build_sq_1]` (Standard single build)
    * **8 chars**: `[from_sq][to_sq][build_sq_1][build_sq_2]` (where `build_sq_1` must equal `build_sq_2`)
* **Example**: `a1b2c3c3` (Move from `a1` to `b2`, build two blocks on `c3`).

### 3.6. **Hermes**

Hermes can move any number of spaces at the same level.

* **Text Representation**: Variable length (even, >= 4 chars): `[from_sq][step_1]...[step_n][build_sq]`
* **Example**: `a1b1c1d1d2` (Move from `a1` across `b1`, `c1`, `d1`, then build on `d2`).

### 3.7. **Prometheus**

Prometheus can build before and after moving, but cannot move up if they built before moving.

* **Text Representation**:
    * **6 chars**: `[from_sq][to_sq][build_sq]` (Standard build-after-move)
    * **8 chars**: `[from_sq][to_sq][build_sq][optional_build_sq]` (Build on `optional_build_sq` before moving)
* **Example**: `a1b2c3d1` (Build on `d1`, move from `a1` to `b2`, then build on `c3`).

## 4. Summary Table of Move Formats

| **God Power** | **Lengths** | **Pattern** | **Example(s)** |
| :--- | :--- | :--- | :--- |
| Standard | 6 | `f(2)+t(2)+b(2)` | `a1b2c3` |
| Artemis | 6 or 8 | 6: `f+t+b` <br> 8: `f+m+t+b` | `a1b2c3`, `a1b2c2d2` |
| Atlas | 6 or 7 | 6: `f+t+b` <br> 7: `f+t+b+"D"` | `a1b2c3`, `a1b2c3D` |
| Demeter | 6 or 8 | 6: `f+t+b1` <br> 8: `f+t+b1+b2` | `a1b2c3`, `a1b2c3d4` |
| Hephaestus | 6 or 8 | 6: `f+t+b1` <br> 8: `f+t+b1+b1` | `a1b2c3`, `a1b2c3c3` |
| Hermes | >=4 (even) | `f(2)+[steps(2*n)]+b(2)` | `a1b2c3`, `a1b1c1d2` |
| Prometheus | 6 or 8 | 6: `f+t+b` <br> 8: `f+t+b+opt_b` | `a1b2c3`, `a1b2c3d1` |

**Legend:**

* `f`: `from_sq`
* `t`: `to_sq`
* `b`: `build_sq`
* `m`: `mid_sq`
* `b1`/`b2`: First/second build squares
* `opt_b`: Optional pre-move build square
* `(2)`: a 2-character square notation (e.g., `a1`)