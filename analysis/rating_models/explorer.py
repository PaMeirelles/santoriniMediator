import math

import pandas as pd
from flask import Flask, jsonify, render_template, request
from power_ranking import get_conn, load_data_list

# --- Configuration ---
ENGINES_TO_ANALYZE = [
    "Fitos_1.1_Ton", "Fitos_2.1_Scout", "Fitos_3.2_Life", "Fitos_4.6_Atium", "Fitos_5.1_Truthless",
    "Fitos_6.3_Trick", "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.5_Astro",
    "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Fitos_13.1_Legacy", "Fitos_14.8_Echo",
    "Paladini_1.4_Trigger", "Paladini_2.9_Apex", "Paladini_3.0_Summit", "Paladini_4.1.1_Mystic",
    "Paladini_5.5.40_Velocity", "Paladini_6.5.2_Prince", "Paladini_7.1.1_Lunar", "Paladini_8.1.8_Firefly"
]

# --- Flask App Initialization ---
app = Flask(__name__)


# --- NEW: Helper Function for DB Elo Loading ---
def load_global_elos_from_db(conn) -> dict:
    """
    Loads pre-calculated Elo ratings from the TB_ELO database table.
    """
    print("Loading global Elo ratings from the database...")
    try:
        # Check if the table exists to avoid errors on a fresh database
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='TB_ELO';")
        if not cursor.fetchone():
            print("⚠️ Warning: TB_ELO table not found. Global ratings will be empty.")
            return {}

        elo_df = pd.read_sql_query("SELECT God, Engine, Elo FROM TB_ELO", conn)
        if elo_df.empty:
            print("⚠️ Warning: TB_ELO table is empty. Global ratings will be empty.")
            return {}

        # Convert DataFrame to the required dictionary format: {(God, Engine): Elo}
        elo_ratings = elo_df.set_index(['God', 'Engine'])['Elo'].to_dict()
        print(f"✅ Loaded {len(elo_ratings)} ratings from TB_ELO.")
        return elo_ratings
    except Exception as e:
        print(f"❌ Error loading ratings from database: {e}")
        return {}


# --- Data Loading and Pre-calculation (run once at startup) ---
print("Loading match data into memory...")
conn = get_conn()
try:
    DF_MATCHES = load_data_list(ENGINES_TO_ANALYZE, conn)
    players_a = set(zip(DF_MATCHES["God_A"], DF_MATCHES["Engine_G"]))
    players_b = set(zip(DF_MATCHES["God_B"], DF_MATCHES["Engine_B"]))
    ALL_PLAYERS = sorted(list(players_a.union(players_b)))

    # --- REVISED: Load pre-calculated Elo ratings from the database ---
    GLOBAL_ELO_RATINGS = load_global_elos_from_db(conn)

    print(f"✅ Data loaded. Found {len(DF_MATCHES)} matches and {len(ALL_PLAYERS)} unique players.")
finally:
    conn.close()


# --- Web Page Route ---
@app.route('/')
def index():
    """Renders the main HTML page."""
    player_list = [f"{god}|{engine}" for god, engine in ALL_PLAYERS]
    return render_template('index.html', players=player_list)


# --- API Endpoint for Analysis (No changes needed here) ---
@app.route('/api/player_analysis')
def player_analysis():
    """
    Calculates a hypothetical Elo based on head-to-head performance
    anchored to the opponent's global Elo.
    """
    god = request.args.get('god')
    engine = request.args.get('engine')

    if not god or not engine:
        return jsonify({"error": "God and Engine parameters are required."}), 400

    selected_player = (god, engine)

    df_player_matches = DF_MATCHES[
        ((DF_MATCHES['God_A'] == god) & (DF_MATCHES['Engine_G'] == engine)) |
        ((DF_MATCHES['God_B'] == god) & (DF_MATCHES['Engine_B'] == engine))
        ].copy()

    # This part can be simplified using pandas for better performance
    df_player_matches['opponent'] = df_player_matches.apply(
        lambda row: (row['God_B'], row['Engine_B']) if (row['God_A'], row['Engine_G']) == selected_player
        else (row['God_A'], row['Engine_G']),
        axis=1
    )
    df_player_matches['player_won'] = df_player_matches.apply(
        lambda row: 1 if ((row['God_A'], row['Engine_G']) == selected_player and row['Result'] == 1) or
                         ((row['God_B'], row['Engine_B']) == selected_player and row['Result'] == -1) else 0,
        axis=1
    )

    # Group by opponent to get all stats in one go
    h2h_stats = df_player_matches.groupby('opponent').agg(
        player_wins=('player_won', 'sum'),
        total_matches=('player_won', 'count')
    ).reset_index()

    results = []
    for _, row in h2h_stats.iterrows():
        opponent = row['opponent']
        player_wins = row['player_wins']
        total_matches = row['total_matches']

        # --- REVISED: Performance Rating Calculation ---
        win_rate_percent = (player_wins / total_matches) * 100

        # 1. Handle edge cases for the logarithmic formula
        if player_wins == total_matches:
            # Undefeated performance is capped; +800 is a strong but reasonable value
            elo_difference = 800
        elif player_wins == 0:
            # Winless performance
            elo_difference = -800
        else:
            # 2. Use the correct logarithmic formula for mixed results
            p = player_wins / total_matches
            elo_difference = 400 * math.log10(p / (1 - p))

        # 3. Get opponent's global Elo and calculate hypothetical Elo
        opponent_global_elo = GLOBAL_ELO_RATINGS.get(opponent, 1500.0)
        hypothetical_elo = opponent_global_elo + elo_difference

        results.append({
            "opponent_god": opponent[0],
            "opponent_engine": opponent[1],
            "matches": int(total_matches),
            "win_rate": win_rate_percent,
            "hypothetical_elo": hypothetical_elo
        })

    sorted_results = sorted(results, key=lambda x: x['matches'], reverse=True)
    return jsonify(sorted_results)


if __name__ == '__main__':
    app.run(debug=True)