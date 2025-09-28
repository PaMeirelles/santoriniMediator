import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

# Define the name of your CSV file
filename = "../../data/pvs_stats.csv"

try:
    # --- 1. Read the Data ---
    df = pd.read_csv(filename)

    # --- 2. Calculate Average Rate per Depth ---
    # We group the data by 'Depth' and then select the 'ResearchRate(%)'
    # column to calculate its mean for each group.
    # .reset_index() converts the result back into a clean DataFrame.
    rate_per_depth = df.groupby('Depth')['ResearchRate(%)'].mean().reset_index()

    # --- 3. Display the Results Table ---
    print("--- Average PVS Re-Search Rate per Depth ---")
    # We format the percentage for better readability in the printout
    rate_per_depth_formatted = rate_per_depth.copy()
    rate_per_depth_formatted['ResearchRate(%)'] = rate_per_depth_formatted['ResearchRate(%)'].map('{:.4f}%'.format)
    print(rate_per_depth_formatted.to_string(index=False))

    # --- 4. Create and Save a Visualization ---
    plt.figure(figsize=(10, 6))
    sns.set_style("whitegrid")

    # Create the bar plot using the unformatted data
    ax = sns.barplot(data=rate_per_depth, x='Depth', y='ResearchRate(%)', palette='viridis')

    # Add title and labels
    ax.set_title('Average PVS Re-Search Rate per Depth', fontsize=16, weight='bold')
    ax.set_xlabel('Search Depth', fontsize=12)
    ax.set_ylabel('Average Re-Search Rate (%)', fontsize=12)

    # Add the percentage value on top of each bar for clarity
    for p in ax.patches:
        ax.annotate(f"{p.get_height():.2f}%",
                    (p.get_x() + p.get_width() / 2., p.get_height()),
                    ha='center', va='center',
                    xytext=(0, 9),
                    textcoords='offset points')

    # Save the chart to a file
    chart_filename = 'research_rate_per_depth.png'
    plt.tight_layout()
    plt.savefig(chart_filename)
    print(f"\n📊 Chart saved as '{chart_filename}'")


except FileNotFoundError:
    print(f"Error: The file '{filename}' was not found. Make sure it's in the same directory.")
except Exception as e:
    print(f"An error occurred: {e}")