import sqlite3

def inject_benchmarks():
    print("[*] Injecting Clinical Benchmarks into the Swarm Queue...")
    benchmarks = [
        ("Erlotinib (Tarceva)", "COCc1cc2c(cc1OC)ncnc2Nc1cccc(c1)C#C"),
        ("Gefitinib (Iressa)", "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1"),
        ("Osimertinib (Tagrisso)", "CN(C)CCN(C)c1cc(Nc2nccc(n2)c2c(C)cn(C)c2c2ccccc2)c(OC)cc1NC(=O)C=C"),
        ("Temozolomide (Standard)", "Cn1cnc2c1c(=O)n(nc2N)C(=O)N")
    ]
    
    conn = sqlite3.connect('grid_memory.db')
    c = conn.cursor()
    
    for name, smiles in benchmarks:
        # We use a special marker in the queue or results to identify them later
        # For now, just push to queue
        c.execute("INSERT OR IGNORE INTO queue (smiles, status) VALUES (?, 'pending')", (smiles,))
        print(f"  -> Injected: {name}")
        
    conn.commit()
    conn.close()
    print("[+] Benchmarks are in the queue. The Swarm will now calibrate against them.")

if __name__ == "__main__":
    inject_benchmarks()
