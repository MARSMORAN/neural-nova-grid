"""
remote_generator_payload.py
NEURAL-NOVA Sovereign v8.5 — Million-Scale Payload Injector.

High-velocity RDKit mutation engine designed to fill the Sovereign Brain 
with 1,000,000+ unique Trojan metabolites. Optimized for memory 
efficiency and long-duration execution.
"""

import os
import requests
import time
import random
import sys

# --- CONFIGURATION ---
BRAIN_URL = "https://perjury-dilation-sulphate.ngrok-free.dev"
TARGET_COUNT = 1000000  # 1 MILLION CANDIDATES
BATCH_SIZE = 1000       # Larger batch for high-velocity injection

print("[*] Initializing Million-Scale RDKit Engine...")
os.system("pip install rdkit -q")
from rdkit import Chem
from rdkit.Chem import AllChem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# --- 1. TROJAN SEED SET ---
SEED_MOLECULES = [
    "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@H]1O",            # Glucose
    "N[C@@H](CCC(=O)N)C(=O)O",                        # Glutamine
    "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",                  # Vitamin C
    "N[C@@H](Cc1ccccc1)C(=O)O",                        # Phenylalanine
    "OC[C@H]1OC(NC(=O)c2ccccn2)[C@H](O)[C@@H](O)[C@H]1O", # Glucose-Pyridine
    "NC(CCC(=O)Nc1ccncc1)C(=O)O"                       # Glutamine-Pyridine
]

def chem_mutate(smi):
    """
    High-diversity mutation for massive-scale generation.
    """
    try:
        mol = Chem.MolFromSmiles(smi)
        if not mol: return None
        
        # Add Hs for substitution
        mol = Chem.AddHs(mol)
        
        # Stochastic Complexity: 1 to 5 mutations
        for _ in range(random.randint(1, 5)):
            # Random substitution
            subs = ["F", "Cl", "Br", "C", "N", "O", "C#N", "CF3", "OC", "C(=O)N", "S(=O)(=O)N"]
            sub = random.choice(subs)
            h_indices = [a.GetIdx() for a in mol.GetAtoms() if a.GetSymbol() == "H"]
            if h_indices:
                target_h = random.choice(h_indices)
                new_mol = Chem.RWMol(mol)
                new_mol.ReplaceAtom(target_h, Chem.Atom(random.choice([6, 7, 8, 9, 17])))
                temp_mol = new_mol.GetMol()
                if Chem.MolToSmiles(temp_mol): mol = temp_mol

            # Ring deco (C->N, C->S)
            if random.random() > 0.5:
                patt = Chem.MolFromSmarts("[c,C]")
                repl = Chem.MolFromSmiles(random.choice(["n", "o", "s"]))
                res = AllChem.ReplaceSubstructs(mol, patt, repl, replaceAll=False)
                if res: mol = res[0]

        mol = Chem.RemoveHs(mol)
        final_smi = Chem.MolToSmiles(mol, isomericSmiles=True)
        
        if 20 < len(final_smi) < 250:
            return final_smi
    except: pass
    return None

def run_remote_injector():
    print(f"[*] MILLION-SCALE INJECTOR ONLINE. Target: {TARGET_COUNT}")
    print(f"[*] Target Brain: {BRAIN_URL}")
    
    total_success = 0
    # Use a rolling set to manage memory for 1M+ SMILES
    seen_this_session = set(SEED_MOLECULES)
    
    while total_success < TARGET_COUNT:
        batch = set()
        while len(batch) < BATCH_SIZE:
            # Pick from session memory (80%) or original seeds (20%) to evolve
            source = list(seen_this_session) if random.random() > 0.2 else SEED_MOLECULES
            parent = random.choice(source)
            
            child = chem_mutate(parent)
            if child and child not in seen_this_session:
                batch.add(child)
                seen_this_session.add(child)
                
                # Prune memory if it gets too large (Keep last 200k for collision check)
                if len(seen_this_session) > 200000:
                    # Not perfect, but keeps RAM usage stable in Colab
                    list_v = list(seen_this_session)
                    seen_this_session = set(list_v[-150000:]) 
            
        # High-Velocity POST to Sovereign Brain
        try:
            start_batch = time.time()
            resp = requests.post(f"{BRAIN_URL}/push_to_queue", json={"smiles_list": list(batch)}, timeout=60)
            if resp.status_code == 200:
                inserted = resp.json().get("inserted", 0)
                total_success += inserted
                latency = time.time() - start_batch
                print(f"[+] Injected {inserted} unique v8.5 Trojans. Total: {total_success} | Latency: {latency:.1f}s")
            else:
                print(f"[!] Brain Overload: {resp.status_code}")
                time.sleep(10)
        except Exception as e:
            print(f"[!] Bridge Instability: {e}")
            time.sleep(20)

    print(f"\n[bold green]MILLION-SCALE MISSION COMPLETE[/bold green]")

if __name__ == "__main__":
    run_remote_injector()
