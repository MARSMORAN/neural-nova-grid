import sqlite3
from engine.repurposer import RepurposingEngine

def load_fda_drugs():
    print("[*] Fetching FDA Approved Drugs from ChEMBL...")
    repurposer = RepurposingEngine()
    drug_df = repurposer.fetch_approved_drugs()
    
    if drug_df.empty:
        print("[!] Failed to fetch FDA drugs.")
        return
        
    smiles_list = drug_df["smiles"].tolist()
    print(f"[*] Found {len(smiles_list)} FDA drugs. Pushing to Grid Swarm Queue...")
    
    # Push to SQLite
    c = sqlite3.connect('grid_memory.db')
    c.execute('DELETE FROM queue') # Clear the random noise
    
    for smi in smiles_list:
        c.execute('INSERT OR IGNORE INTO queue (smiles) VALUES (?)', (smi,))
        
    c.commit()
    print("[+] Swarm Queue is now loaded with 100% REAL FDA Approved Drugs!")

if __name__ == "__main__":
    load_fda_drugs()
