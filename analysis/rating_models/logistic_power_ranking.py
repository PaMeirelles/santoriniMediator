import torch
import torch.nn as nn
import torch.optim as optim
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple

# Import your DB connection function
from analysis.visualization.visualization import get_conn


# -------------------------------
# Data Loader
# -------------------------------
def load_data_list(include_engines: list, conn) -> pd.DataFrame:
    """
    Load match data for all matches where both engines are in the given include_engines list.
    """
    engine_list_sql = ", ".join(f"'{engine}'" for engine in include_engines)
    query = f"""
        SELECT Id,
               GOD_G AS God_A,
               GOD_B AS God_B,
               result AS Result,
               Engine_G,
               Engine_B
        FROM TB_MATCHES
        WHERE Engine_G IN ({engine_list_sql})
          AND Engine_B IN ({engine_list_sql})
          AND (Time_G = 60 OR Time_G IS NULL)
    """
    df = pd.read_sql_query(query, conn)
    df["Result"] = df["Result"].astype(int)
    return df


# -------------------------------
# Latent Factor Model
# -------------------------------
class LatentEloModel(nn.Module):
    def __init__(self, n_items: int, k_factors: int = 3):
        """
        n_items: Total number of unique God-Engine pairs.
        k_factors: The number of latent dimensions for playstyle/weaknesses.
        """
        super().__init__()
        # 1D Base Strength
        self.base_strength = nn.Embedding(n_items, 1)
        # K-Dimensional Offensive / Defensive factors
        self.offensive_style = nn.Embedding(n_items, k_factors)
        self.defensive_weakness = nn.Embedding(n_items, k_factors)

        # FIXED INITIALIZATION: Give the weights enough variance so gradients don't vanish
        nn.init.normal_(self.base_strength.weight, std=1.0)
        nn.init.normal_(self.offensive_style.weight, std=0.5)
        nn.init.normal_(self.defensive_weakness.weight, std=0.5)

    def forward(self, i, j):
        """Calculates the log-odds (logits) of i beating j."""
        s_i = self.base_strength(i).squeeze(1)
        s_j = self.base_strength(j).squeeze(1)

        off_i = self.offensive_style(i)
        def_j = self.defensive_weakness(j)
        off_j = self.offensive_style(j)
        def_i = self.defensive_weakness(i)

        # Interaction: How much i exploits j's weakness, minus how much j exploits i's.
        interaction = (off_i * def_j).sum(dim=1) - (off_j * def_i).sum(dim=1)

        return s_i - s_j + interaction


def train_and_simulate_round_robin(
        items: List[Tuple],
        df: pd.DataFrame,
        k_factors: int = 3,
        epochs: int = 1000,
        lr: float = 0.01,
        weight_decay: float = 1e-5
) -> pd.DataFrame:
    print(f"⚙️ Building Latent Factor Model (K={k_factors})...")
    item_to_idx = {item: idx for idx, item in enumerate(items)}
    n_items = len(items)

    # 1. Prepare Training Data
    decisive_matches = df[df['Result'] != 0].copy()

    player_i_list = []
    player_j_list = []
    labels_list = []

    for _, row in decisive_matches.iterrows():
        item1 = (row['God_A'], row['Engine_G'])
        item2 = (row['God_B'], row['Engine_B'])

        idx1 = item_to_idx[item1]
        idx2 = item_to_idx[item2]

        # We model the probability that item1 beats item2
        player_i_list.append(idx1)
        player_j_list.append(idx2)
        labels_list.append(1.0 if row['Result'] == 1 else 0.0)

    # Convert to PyTorch tensors
    i_tensor = torch.tensor(player_i_list, dtype=torch.long)
    j_tensor = torch.tensor(player_j_list, dtype=torch.long)
    y_tensor = torch.tensor(labels_list, dtype=torch.float32)

    # 2. Initialize Model and Optimizer
    model = LatentEloModel(n_items=n_items, k_factors=k_factors)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    # 3. Training Loop
    print(f"🧠 Training Embeddings (Epochs={epochs}, LR={lr}, WD={weight_decay})...")
    model.train()
    last_loss = 999.0

    for epoch in range(epochs):
        optimizer.zero_grad()
        logits = model(i_tensor, j_tensor)
        loss = criterion(logits, y_tensor)
        loss.backward()
        optimizer.step()

        if (epoch + 1) % 100 == 0:
            diff = last_loss - loss.item()
            print(f"   Epoch {epoch + 1}/{epochs} | Loss: {loss.item():.4f} | Change: {diff:.6f}")
            if abs(diff) < 1e-7 and epoch > 100:
                print("   ⚠️ Warning: Loss flatlined. Model has converged or is stuck.")
            last_loss = loss.item()

    # 4. Simulate the Massive Round Robin
    print("🏟️ Simulating Complete Round Robin Tournament...")
    model.eval()

    # Create an NxN matrix of all possible matchups
    all_i = torch.arange(n_items).repeat_interleave(n_items)
    all_j = torch.arange(n_items).repeat(n_items)

    with torch.no_grad():
        all_logits = model(all_i, all_j)
        # Convert log-odds to win probabilities
        all_probs = torch.sigmoid(all_logits)

        # Reshape into an N x N matrix
        prob_matrix = all_probs.view(n_items, n_items)

        # Calculate expected win rate against the field (ignoring self-play)
        prob_matrix.fill_diagonal_(0)
        expected_win_rates = prob_matrix.sum(dim=1) / (n_items - 1)
        expected_win_rates = expected_win_rates.numpy()

    # 5. Convert EWR to Elo
    ranking_records = []

    for idx, item in enumerate(items):
        ewr = expected_win_rates[idx]
        # Clip EWR to avoid mathematically breaking the Elo calculation
        ewr_clipped = np.clip(ewr, 0.001, 0.999)

        # Standard Elo mapping: +400 Elo = 10x higher odds of winning
        elo = 400 * np.log10(ewr_clipped / (1 - ewr_clipped))

        god, engine = item
        ranking_records.append({
            "God": god,
            "Engine": engine,
            "Expected Field WR (%)": ewr * 100,
            "Elo": elo
        })

    ranking_df = pd.DataFrame(ranking_records)

    # Normalize Elos so the lowest rating is exactly 0
    min_elo = ranking_df["Elo"].min()
    ranking_df["Elo"] = ranking_df["Elo"] - min_elo

    ranking_df.sort_values(by="Expected Field WR (%)", ascending=False, inplace=True)
    ranking_df.reset_index(drop=True, inplace=True)

    return ranking_df


# -------------------------------
# Main Calculation
# -------------------------------
def calculate_ratings(include_engines: List[str], display: bool = False) -> pd.DataFrame:
    conn = get_conn()
    try:
        df = load_data_list(include_engines, conn)
    finally:
        conn.close()

    items = sorted(list(set(zip(df["God_A"], df["Engine_G"])).union(set(zip(df["God_B"], df["Engine_B"])))))

    ranking_df = train_and_simulate_round_robin(
        items=items,
        df=df,
        k_factors=3,
        epochs=1000,  # Increased to allow the model time to find the minimum
        lr=0.01,  # Lowered so it doesn't overshoot
        weight_decay=1e-5  # Dropped from 1e-3 to stop it from strangling the weights
    )

    if display:
        print("\n" + "=" * 80)
        print("Latent Round Robin Rankings (Counter-Bias Removed)")
        print("=" * 80)
        display_df = ranking_df.copy()
        display_df['Expected Field WR (%)'] = display_df['Expected Field WR (%)'].map('{:.2f}'.format)
        display_df['Elo'] = display_df['Elo'].map('{:.0f}'.format)
        print(display_df.to_string())

    return ranking_df


if __name__ == "__main__":
    engines_to_analyze = [
        "Fitos_1.1_Ton", "Fitos_2.1_Scout", "Fitos_3.2_Life", "Fitos_4.6_Atium", "Fitos_5.1_Truthless",
        "Fitos_6.3_Trick", "Fitos_7.2_Time", "Fitos_8.1_Cursed", "Fitos_9.4_Moth", "Fitos_10.5_Astro",
        "Fitos_11.0_Hyperion", "Fitos_12.0_Never", "Fitos_13.1_Legacy", "Fitos_14.8_Echo",
        "Paladini_1.4_Trigger", "Paladini_2.9_Apex", "Paladini_3.0_Summit", "Paladini_4.1.1_Mystic",
        "Paladini_5.5.40_Velocity", "Paladini_6.5.2_Prince", "Paladini_7.1.1_Lunar", "Paladini_8.1.8_Firefly",
        "Davi_1.0_Phoenix", "Davi_2.3.8_Raven"
    ]

    calculate_ratings(engines_to_analyze, display=True)