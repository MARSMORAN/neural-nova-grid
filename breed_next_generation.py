import sqlite3
import random
from rdkit import Chem

def mutate_smiles(smiles):
    """
    Genetic Algorithm Mutation Engine.
    Takes a parent SMILES and structurally mutates it by adding functional groups
    or altering ring structures, verifying chemical validity with RDKit.
    """
    mutations = [
        ("c", "c(F)"),          # Add Fluorine
        ("c", "c(Cl)"),         # Add Chlorine
        ("c", "c(C)"),          # Add Methyl
        ("c", "c(OC)"),         # Add Methoxy
        ("c", "c(C(F)(F)F)"),   # Add CF3 (Trifluoromethyl)
        ("C", "CC"),            # Extend carbon chain
        ("C", "C(O)"),          # Add Hydroxyl
        ("c", "n"),             # Carbon to Nitrogen in ring
    ]
    
    # Try 10 random mutations until we get a valid one
    for _ in range(10):
        mut_type = random.choice(mutations)
        # Find all occurrences
        target, replacement = mut_type
        if target in smiles:
            # Replace one random occurrence
            parts = smiles.split(target)
            if len(parts) > 1:
                idx = random.randint(1, len(parts)-1)
                # Reconstruct
                new_smiles = target.join(parts[:idx]) + replacement + target.join(parts[idx:])
                
                # Verify structural validity with RDKit
                mol = Chem.MolFromSmiles(new_smiles)
                if mol is not None:
                    # Successfully bred a valid child molecule!
                    return Chem.MolToSmiles(mol)
    return None

def breed_next_generation(target_population=5000):
    print("[*] Accessing Grid Memory...")
    c = sqlite3.connect('grid_memory.db')
    
    # Extract the top 10 valid parents from the last cycle
    rows = c.execute("SELECT smiles FROM results ORDER BY score ASC").fetchall()
    
    parents = []
    for (smiles,) in rows:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            parents.append(smiles)
            if len(parents) >= 10:
                break
                
    if not parents:
        print("[!] No valid parents found.")
        return
        
    print(f"[*] Found {len(parents)} elite Parent molecules.")
    print("[*] Breeding next generation via structural mutation...")
    
    children = set()
    attempts = 0
    while len(children) < target_population and attempts < target_population * 5:
        parent = random.choice(parents)
        child = mutate_smiles(parent)
        if child and child not in parents:
            children.add(child)
        attempts += 1
        
        if len(children) % 500 == 0 and len(children) > 0:
            print(f"  -> Bred {len(children)} chemically valid descendants...")

    print(f"[+] Successfully bred {len(children)} new ultra-optimized candidates.")
    
    print("[*] Flushing old queue and pushing descendants to the Swarm...")
    c.execute('DELETE FROM queue')
    
    for child in children:
        c.execute('INSERT OR IGNORE INTO queue (smiles) VALUES (?)', (child,))
        
    c.commit()
    print("[+] Swarm Queue is loaded. The Drones will now test Generation 2.")

if __name__ == "__main__":
    breed_next_generation(5000)
