import networkx as nx
import matplotlib.pyplot as plt
import math

# -------------------------------
# Visualization (Faceted by Engine)
# -------------------------------

# 1. Configuration for the Graph
MATCH_THRESHOLD = 500  # Only include pairs with at least this many matches

# Filter the DataFrame based on the threshold
df_graph = ranking_df[ranking_df["Matches"] >= MATCH_THRESHOLD].copy()
df_graph['item'] = list(zip(df_graph['God'], df_graph['Engine']))

if df_graph.empty:
    print(f"\nNo God-Engine pairs found with at least {MATCH_THRESHOLD} matches. Cannot generate graph.")
else:
    # 2. Create the full graph first (as a base)
    G = nx.Graph()

    # Add all nodes and edges from the filtered data
    for _, row in df_graph.iterrows():
        G.add_node(row['item'], rating=row['Rating'], engine=row['Engine'])

    graph_items = list(df_graph['item'])
    for i in range(len(graph_items)):
        for j in range(i + 1, len(graph_items)):
            item1 = graph_items[i]
            item2 = graph_items[j]
            num_matches = matches_ij.get((item1, item2), 0)
            if num_matches > 0:
                G.add_edge(item1, item2, weight=num_matches)

    # 3. Prepare Subplots for each Engine
    unique_engines = sorted(df_graph['Engine'].unique())
    num_engines = len(unique_engines)

    # Calculate an appropriate grid size for the subplots
    cols = math.ceil(math.sqrt(num_engines))
    rows = math.ceil(num_engines / cols)

    fig, axes = plt.subplots(rows, cols, figsize=(8 * cols, 8 * rows))
    # Flatten axes array for easy iteration, handling the case of a single plot
    axes = axes.flatten() if num_engines > 1 else [axes]

    # 4. Create and Draw a Subplot for Each Engine
    for i, engine_name in enumerate(unique_engines):
        ax = axes[i]

        # a. Isolate nodes for the current engine and their direct neighbors
        engine_nodes = [n for n, d in G.nodes(data=True) if d['engine'] == engine_name]
        neighbors = set()
        for node in engine_nodes:
            neighbors.update(G.neighbors(node))

        # Combine the engine's nodes and their neighbors for the subgraph
        subgraph_nodes = set(engine_nodes).union(neighbors)
        subG = G.subgraph(subgraph_nodes)

        # b. Set node colors: gold for the featured engine, lightblue for others
        node_colors = ['gold' if d['engine'] == engine_name else 'skyblue' for n, d in subG.nodes(data=True)]

        # c. Draw the subgraph
        pos = nx.spring_layout(subG, seed=42)
        node_sizes = [d['rating'] * 1.5 for n, d in subG.nodes(data=True)]
        edge_widths = [d['weight'] * 0.01 for u, v, d in subG.edges(data=True)]
        labels = {n: f"{n[0]}_{n[1].split('_')[1]}" for n in subG.nodes()}

        nx.draw_networkx_nodes(subG, pos, ax=ax, node_size=node_sizes, node_color=node_colors, alpha=0.9)
        nx.draw_networkx_edges(subG, pos, ax=ax, width=edge_widths, edge_color='lightgray', alpha=0.7)
        nx.draw_networkx_labels(subG, pos, ax=ax, labels=labels, font_size=9)

        ax.set_title(f"Network for: {engine_name}", fontsize=16)
        ax.set_box(False)

    # Hide any unused subplots
    for j in range(num_engines, len(axes)):
        axes[j].set_visible(False)

    plt.tight_layout()
    plt.savefig("faceted_engine_networks.png", dpi=150)
    print("\nFaceted graph saved to faceted_engine_networks.png")
    plt.show()