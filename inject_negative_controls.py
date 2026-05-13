import sqlite3

def inject_negative_controls():
    print("[*] Injecting Negative Controls (Decoy Set) for Statistical Calibration...")
    decoys = [
        ("Alpha-D-Glucose", "C(C1C(C(C(C(O1)O)O)O)O)O"),
        ("Sucrose", "C(C1C(C(C(C(O1)OC2(C(C(C(O2)CO)O)O)CO)O)O)O)O"),
        ("Lactose", "C1C(C(C(C(O1)OC2C(OC(C(C2O)O)O)CO)O)O)O"),
        ("Water (Hydration Control)", "O"),
        ("Random Decoy (Inert Alkane)", "CCCCCCCCCCCCCCCCCCCC")
    ]
    
    conn = sqlite3.connect('grid_memory.db')
    c = conn.cursor()
    
    for name, smiles in decoys:
        c.execute("INSERT OR IGNORE INTO queue (smiles, status) VALUES (?, 'pending')", (smiles,))
        print(f"  -> Injected Decoy: {name}")
        
    conn.commit()
    conn.close()
    print("[+] Negative Controls are in the queue. Statistical calibration is underway.")

if __name__ == "__main__":
    inject_negative_controls()
