import subprocess
import time
import sqlite3
import os


# --- Engine Communication Helpers ---

def start_engine(engine_path):
    """Launch engine process and handle immediate errors."""
    if not os.path.exists(engine_path):
        raise FileNotFoundError(f"Engine executable not found at: {engine_path}")
    try:
        process = subprocess.Popen(
            [engine_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1  # Line buffered
        )
        time.sleep(0.1)  # Give the process a moment to start or fail
        if process.poll() is not None:
            stderr_output = process.stderr.read()
            raise RuntimeError(f"Engine terminated early. Error: {stderr_output}")
        return process
    except Exception as e:
        print(f"Error starting engine: {e}")
        return None


def quit_engine(engine_process):
    """Gracefully quit the engine process."""
    if engine_process and engine_process.poll() is None:
        try:
            engine_process.stdin.write("quit\n")
            engine_process.stdin.flush()
            engine_process.wait(timeout=2)
        except (BrokenPipeError, subprocess.TimeoutExpired):
            pass  # Ignore if it's already closing or doesn't respond
        finally:
            if engine_process.poll() is None:
                engine_process.terminate()


# --- Database Helper ---

def get_positions_from_db(db_path):
    """
    Fetches all unique positions from the TB_POSITIONS table.
    Also ensures the table exists.
    """
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT position FROM TB_BENCHMARK_POSITIONS")
            # fetchall() returns a list of tuples, e.g., [('pos1',), ('pos2',)]
            # We need to extract the first element from each tuple.
            positions = [row[0] for row in cursor.fetchall()]
            return positions
    except sqlite3.Error as e:
        print(f"Database error while fetching positions: {e}")
        return []  # Return empty list on error


# --- Main Benchmark Function ---

def run_benchmark(db_path, engine_path, engine_name, position, depth, pos_id):
    """
    Runs a single benchmark test for a given position and depth,
    and stores the result in the database.
    """
    engine_process = None
    try:
        # 1. Start the engine
        engine_process = start_engine(engine_path)
        if not engine_process:
            return

        # 2. Send initial commands to set up the engine
        engine_process.stdin.write("isready\n")
        engine_process.stdin.flush()
        while engine_process.stdout.readline().strip() != "readyok":
            pass

        engine_process.stdin.write(f"position {position}\n")
        engine_process.stdin.flush()

        # 3. Run the search and time it
        go_command = f"go depth {depth} score nodes\n"
        start_time = time.perf_counter()
        engine_process.stdin.write(go_command)
        engine_process.stdin.flush()

        # 4. Parse the output from the engine
        best_move, score, nodes = "", 0, 0
        for line in iter(engine_process.stdout.readline, ''):
            line = line.strip()
            if not line: continue

            parts = line.split()
            if parts[0] == "info":
                if "score" in parts: score = int(parts[parts.index("score") + 1])
                if "nodes" in parts: nodes = int(parts[parts.index("nodes") + 1])
            elif parts[0] == "bestmove":
                best_move = parts[1]
                break  # This is the final output for a 'go' command

        end_time = time.perf_counter()
        execution_time_ms = int((end_time - start_time) * 1000)

        if not best_move:
            raise RuntimeError("Engine did not return a bestmove.")

        # 5. Store the results in the database
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO TB_BENCHMARK (position, depth, move, score, nodes, engine, execution_time_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (position, depth, best_move, score, nodes, engine_name, execution_time_ms))
            conn.commit()
            print(f"Stored benchmark for '{engine_name}' at depth {depth} for position: {pos_id}...")

    except Exception as e:
        print(f"An error occurred during benchmark: {e}")
    finally:
        # 6. Ensure the engine is always closed
        if engine_process:
            quit_engine(engine_process)


# --- Example Usage ---
if __name__ == '__main__':
    # --- CONFIGURATION ---
    DB_FILE_PATH = r"../../data/matches.db"

    DEPTH_TO_BENCHMARK = 7
    # --- SETUP AND RUN ---
    db_dir = os.path.dirname(DB_FILE_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)


    # --- Get positions from the database ---
    print(f"Fetching benchmark positions from {DB_FILE_PATH}...")
    positions_to_benchmark = get_positions_from_db(DB_FILE_PATH)

    engines = ["Paladini_9.2.3_Prophet"]
    for engine in engines:
        ENGINE_PATH = f"../../engines/Paladini/Prophet/{engine}.exe"
        ENGINE_ID = engine

        if not positions_to_benchmark:
            print("No positions found in TB_POSITIONS. Please populate the table first. Exiting.")
        else:
            print(f"Found {len(positions_to_benchmark)} positions to benchmark.")
            print("--- Starting Benchmark Run ---")
            for i, pos in enumerate(positions_to_benchmark):
                print(pos)
                run_benchmark(
                    db_path=DB_FILE_PATH,
                    engine_path=ENGINE_PATH,
                    engine_name=ENGINE_ID,
                    position=pos,
                    depth=DEPTH_TO_BENCHMARK,
                    pos_id = i
                )
            print("--- Benchmark Run Complete ---")

