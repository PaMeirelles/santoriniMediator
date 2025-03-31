# Santorini Move Protocol

This document explains how moves in a Santorini-like game are encoded and decoded in a simple textual format. The code in question defines several **God Powers** (Apollo, Artemis, Hermes, Demeter, Hephaestus, Pan, Prometheus, Athena, Minotaur, Atlas) and the way each power’s move is represented.

All of these move classes implement or extend the `Move` interface, providing:

1. A constructor (or `__init__`) that stores the internal representation of a move (e.g., the squares involved in the move).
2. A `move_to_text()` method that converts the internal representation (e.g., integer board indices) to a short string of text.
3. A `from_text()` class method that **parses** a short string of text and returns an instance of the move class (decoding the text back into the numerical representation).

Below is a step-by-step explanation of how the coordinate system works, followed by details on each **God Power**.

---

## 1. Coordinate System

### String Notation

Each square on the board is denoted by two characters:

- **Row**: a lower-case letter from `a` to `e`.
- **Column**: a digit from `1` to `5`.

Hence, the top-left corner of the board is `a1`, the next square to the right is `b1`, and so on. The bottom-right corner is `e5`.

### Internal Representation (`text_to_square` and `square_to_text`)

Internally, these board coordinates are represented as an integer from 0 to 24. The mapping in the code is:

```
square_index = (column_index * 5) + row_index
```

Where:
- `row_index` = `ord(row_letter) - ord('a')`  (i.e., 0 for 'a', 1 for 'b', …, 4 for 'e')
- `column_index` = `(column_number - 1)`      (i.e., 0 for '1', 1 for '2', …, 4 for '5')

> **Important**: Note that the code multiplies the *column* by 5 and then adds the *row*, which means `a1` (row = 0, col = 0) becomes `0`, and `b1` (row = 1, col = 0) becomes `1`, … but `a2` would be `(1 * 5) + 0 = 5`.  
> 
> When converting back, `square_to_text` performs the inverse operation and reconstructs the `row_letter` and `column_number`.

---

## 2. Abstract `Move` Class

```python
class Move(ABC):
    @abstractmethod
    def move_to_text(self) -> str:
        pass

    @classmethod
    @abstractmethod
    def from_text(cls: Type[T], move_text: str) -> T:
        pass
```

All concrete move classes derive from `Move` and must implement:

- **`move_to_text()`** → returns a string representing the move (e.g., `"a1b2c3"`)
- **`from_text(move_text)`** → parses a string and returns an instance of the move class.

---

## 3. God Powers and Their Move Formats

The game uses different gods, each with special behaviors. In this code, each god has its own class that extends `Move` (directly or via another god’s class). Below is a list of each **God Power** class, along with how they encode/decode moves.

### 3.1. **ApolloMove**

```python
@dataclass
class ApolloMove(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    ...
```

- **Text Representation**: Exactly **6 characters**.
- The first 2 characters = `from_sq`.
- The next 2 characters = `to_sq`.
- The final 2 characters = `build_sq`.

An example string might be:  
```
a1b2c3
```
Which would parse to:
- `from_sq = a1`
- `to_sq   = b2`
- `build_sq= c3`

And vice versa when calling `move_to_text()`.

### 3.2. **ArtemisMove**

```python
@dataclass
class ArtemisMove(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    mid_sq: Optional[int] = None
    ...
```

Artemis can potentially move twice. Hence:

- **Text Representation**:
  - Either **6 characters**: `from_sq + to_sq + build_sq`  
    (e.g. `"a1b2c3"`)
  - Or **8 characters**: `from_sq + mid_sq + to_sq + build_sq`  
    (e.g. `"a1b2c3d4"`)

Where `mid_sq` is the square visited in between the first and second step (only present for the **8-character** version).

### 3.3. **HermesMove**

```python
@dataclass
class HermesMove(Move):
    from_sq: int
    squares: List[int]
    build: int
    ...
```

Hermes can move through **multiple** intermediate squares before building. The string layout is:

1. First **2 chars** → `from_sq`
2. Last **2 chars** → `build`
3. Everything in between (in 2-char chunks) → the list of squares visited in succession.

The code ensures the length is at least 4 characters (and even). Examples:

- `"a1c3"` → minimal valid text:  
  - `from_sq = a1`  
  - `squares = []` (no intermediate squares)  
  - `build = c3`
  
- `"a1b2c3d4"` →  
  - `from_sq = a1`  
  - `squares = [b2, c3]` (2 intermediate squares)  
  - `build = d4`

### 3.4. **DemeterMove**

```python
@dataclass
class DemeterMove(Move):
    from_sq: int
    to_sq: int
    build_sq_1: int
    build_sq_2: Optional[int] = None
    ...
```

Demeter can build twice on different squares.

- **Text Representation**:
  - **6 chars** → `from_sq + to_sq + build_sq_1`
  - **8 chars** → `from_sq + to_sq + build_sq_1 + build_sq_2`

For example:
- `"a1b2c3"` would parse as:
  - `from_sq=a1`, `to_sq=b2`, `build_sq_1=c3`, `build_sq_2=None`
- `"a1b2c3d4"` would parse as:
  - `from_sq=a1`, `to_sq=b2`, `build_sq_1=c3`, `build_sq_2=d4`

### 3.5. **Hephaestus**

```python
@dataclass
class Hephaestus(DemeterMove):
    pass
```

This is simply an alias or extension of **DemeterMove**. It inherits the same format.

### 3.6. **PanGod**

```python
@dataclass
class PanGod(ApolloMove):
    pass
```

This is simply an alias/extension of **ApolloMove**, thus follows the **6-character** format:  
`from_sq + to_sq + build_sq`

### 3.7. **Prometheus**

```python
@dataclass
class Prometheus(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    optional_build: Optional[int] = None
    ...
```

Prometheus can optionally build **before** moving in addition to the normal build (depending on the rules, but here it’s reflected in the text format).

- **Text Representation**:
  - **6 chars** = `from_sq + to_sq + build_sq`
  - **8 chars** = `from_sq + to_sq + build_sq + optional_build`

For example:
- `"a1b2c3"` → no optional build
- `"a1b2c3d4"` → yes optional build on `d4`

### 3.8. **Athena**

```python
@dataclass
class Athena(ApolloMove):
    pass
```

Same text format as **ApolloMove**: **6 characters** for `from_sq`, `to_sq`, `build_sq`.

### 3.9. **Minotaur**

```python
@dataclass
class Minotaur(ApolloMove):
    pass
```

Also identical to **ApolloMove** in terms of text encoding.

### 3.10. **Atlas**

```python
@dataclass
class Atlas(Move):
    from_sq: int
    to_sq: int
    build_sq: int
    dome: bool
    ...
```

Atlas can optionally build a **dome** instead of a standard block. So:

1. **6 characters** = Normal build (`from_sq + to_sq + build_sq`)
2. **7 characters** = Dome build (`from_sq + to_sq + build_sq + "D"`)

An example:
- `"a1b2c3"` → normal build at `c3`
- `"a1b2c3D"` → build a **dome** at `c3` (the `D` indicates dome)

---

## 4. Summary Table of Formats

Below is a quick reference:

| **Class**      | **Possible Lengths** | **Pattern**                                 | **Examples**           |
|----------------|-----------------------|---------------------------------------------|------------------------|
| ApolloMove     | 6 chars              | `f(2)+t(2)+b(2)`                            | `a1b2c3`              |
| ArtemisMove    | 6 or 8 chars         | 6: `f(2)+t(2)+b(2)`<br>8: `f(2)+m(2)+t(2)+b(2)` | `a1b2c3`<br>`a1b2c3d4` |
| HermesMove     | >=4, even length     | `f(2) + [any # of 2-char squares] + b(2)`   | `a1c3`, `a1b2c3d4`    |
| DemeterMove    | 6 or 8 chars         | 6: `f(2)+t(2)+b1(2)`<br>8: `f(2)+t(2)+b1(2)+b2(2)` | `a1b2c3`<br>`a1b2c3d4` |
| Hephaestus     | 6 or 8 chars         | Same as Demeter                             | `a1b2c3`<br>`a1b2c3d4` |
| PanGod         | 6 chars              | Same as Apollo                              | `a1b2c3`              |
| Prometheus     | 6 or 8 chars         | 6: `f(2)+t(2)+b(2)`<br>8: `f(2)+t(2)+b(2)+opt(2)` | `a1b2c3`<br>`a1b2c3d4` |
| Athena         | 6 chars              | Same as Apollo                              | `a1b2c3`              |
| Minotaur       | 6 chars              | Same as Apollo                              | `a1b2c3`              |
| Atlas          | 6 or 7 chars         | 6: `f(2)+t(2)+b(2)`<br>7: `f(2)+t(2)+b(2)+D` | `a1b2c3`<br>`a1b2c3D`  |

Where:
- `f(2)` = `from_sq`
- `t(2)` = `to_sq`
- `b(2)` = `build_sq`
- `m(2)` = `mid_sq` (extra move step)
- `b1(2)` / `b2(2)` = first and second build squares
- `opt(2)` = optional extra build
- `"D"` = literal character for dome-building

---

## 5. Common Parsing/Encoding Steps

1. **Parsing** (`from_text`):
   - Check length constraints (some moves allow multiple possible lengths).
   - Slice the string into 2-character chunks (or a single trailing `'D'` in the case of Atlas).
   - Convert the 2-character chunks to integer indices with `text_to_square()`.
   - Store them in the data class fields.

2. **Encoding** (`move_to_text`):
   - Convert the integer fields (e.g., `from_sq`, `to_sq`) back to string notation with `square_to_text()`.
   - Concatenate them in the correct order (optionally adding `'D'` for Atlas or ignoring absent squares if they are `None`).

---

## 6. Implementation Notes

- Each move class makes strict assumptions about the length of the string it parses. If a length doesn’t match the expected pattern, a `ValueError` (or `Exception`) is raised.
- The conversion functions `text_to_square` / `square_to_text` will raise or result in invalid indices if passed coordinates outside of `a1` … `e5`.
- Classes like `PanGod`, `Athena`, and `Minotaur` are effectively synonyms for **ApolloMove**, so they share the same 6-character format.

---

### Example Usage

```python
# 1) Construct an ApolloMove directly, then encode it:
apollo_move = ApolloMove(from_sq=0, to_sq=1, build_sq=2)
move_str = apollo_move.move_to_text()  # e.g. "a1b1c1" if the integers 0, 1, 2 map to a1, b1, c1
print(move_str)

# 2) Parse a HermesMove from string:
hermes_str = "a1b2c3d4"
hermes_move = HermesMove.from_text(hermes_str)
print(hermes_move.squares)  # Check intermediate squares
```

---

## 7. Conclusion

In summary, this protocol uses short strings of **2-character board coordinates** (with an optional `'D'` or optional extra pairs of coordinates in certain cases) to represent each God’s possible move sequence. Each God’s special ability is captured in how many squares can be visited/modified and whether extra builds or domes are allowed. The code is an elegant reflection of these rules and ensures each move’s textual format is both consistent and easily parsed.