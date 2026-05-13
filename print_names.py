import sqlite3
import pandas as pd
from engine.repurposer import RepurposingEngine

def get_real_names():
    c = sqlite3.connect('grid_memory.db')
    rows = c.execute("SELECT smiles, score FROM results ORDER BY score ASC").fetchall()
    
    repurposer = RepurposingEngine()
    drug_df = repurposer.fetch_approved_drugs()
    
    found = 0
    for smiles, score in rows:
        match = drug_df[drug_df["smiles"] == smiles]
        if not match.empty:
            name = match["pref_name"].values[0]
            print(f"Rank {found+1}: {name} (Score: {score}) | SMILES: {smiles[:10]}...")
            found += 1
            if found >= 5:
                break

if __name__ == "__main__":
    get_real_names()
