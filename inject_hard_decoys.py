import sqlite3

def inject_hard_decoys():
    print("[*] Injecting Hard Decoys (Kinase-Inactive Drugs) for Quantitative Calibration...")
    hard_decoys = [
        ("Penicillin G (Antibiotic)", "CC1(C(N2C(S1)C(C2=O)NC(=O)Cc3ccccc3)C(=O)O)C"),
        ("Propranolol (Beta-Blocker)", "CC(C)NCC(COc1cccc2ccccc12)O"),
        ("Aspirin (NSAID)", "CC(=O)Oc1ccccc1C(=O)O"),
        ("Metformin (Diabetes)", "CN(C)C(=N)N=C(N)N"),
        ("Paracetamol (Analgesic)", "CC(=O)Nc1ccc(O)cc1")
    ]
    conn = sqlite3.connect('grid_memory.db')
    c = conn.cursor()
    for name, smiles in hard_decoys:
        c.execute("INSERT OR IGNORE INTO queue (smiles, status) VALUES (?, 'pending')", (smiles,))
        print(f"  -> Injected Hard Decoy: {name}")
    conn.commit()
    conn.close()
    print("[+] Hard Decoys are live in the swarm.")

if __name__ == "__main__":
    inject_hard_decoys()
