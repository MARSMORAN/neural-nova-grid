"""
remote_generator_payload.py
NEURAL-NOVA Sovereign v8.0 — Remote Payload Injector.

This script runs in Google Colab to offload the molecule generation (and the heat!) 
from your laptop to Google's servers. It generates 100,000+ v8.0 Trojan Metabolites 
and pushes them directly to your Sovereign Brain.
"""

import os
import requests
import time
import random
import sys

# --- CONFIGURATION ---
BRAIN_URL = "https://perjury-dilation-sulphate.ngrok-free.dev" # YOUR NGROK URL
TARGET_COUNT = 100000 # Total molecules to inject
BATCH_SIZE = 500

# --- SETUP RDKIT ---
print("[*] Preparing Remote Generator...")
os.system("pip install rdkit torch --quiet")
from rdkit import Chem
from rdkit import RDLogger
RDLogger.DisableLog('rdApp.*')

# --- 1. TROJAN SEED SET ---
SEED_MOLECULES = [
    "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@H]1O",
    "OC[C@H]1OC(NC(=O)c2ccccn2)[C@H](O)[C@@H](O)[C@H]1O",
    "OC[C@H]1OC(NC(=O)Nc2ccc(F)cc2)[C@H](O)[C@@H](O)[C@H]1O",
    "N[C@@H](CCC(=O)N)C(=O)O",
    "NC(CCC(=O)Nc1ccncc1)C(=O)O",
    "NC(CCC(=O)Nc1ccc(Cl)cc1)C(=O)O",
    "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",
    "NC(=O)c1cccc(c1)OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",
    "N[C@@H](Cc1ccccc1)C(=O)O",
    "NC(Cc1ccc(NC(=O)c2ccncc2)cc1)C(=O)O",
]

FUNCTIONAL_GROUPS = [
    ("F", "Cl"), ("Cl", "F"), ("O", "S"), ("S", "O"), ("N", "O"),
    ("C(=O)O", "C(=O)N"), ("c1ccccc1", "c1ccncc1")
]

SUBSTITUENTS = ["F", "Cl", "Br", "O", "N", "C", "CC", "OC", "C(F)(F)F", "C#N", "C(=O)N"]

def mutate(smi):
    try:
        parent = smi
        # Strategy: Fragment mutation
        fg_old, fg_new = random.choice(FUNCTIONAL_GROUPS)
        if fg_old in parent:
            child = parent.replace(fg_old, fg_new, 1)
            if Chem.MolFromSmiles(child): return child
            
        # Strategy: Enumeration
        sub = random.choice(SUBSTITUENTS)
        if "c1" in parent:
            child = parent.replace("c1ccc", f"c1c({sub})cc", 1)
        else:
            child = parent + sub
        if Chem.MolFromSmiles(child): return child
    except: pass
    return None

def run_remote_injector():
    print(f"[*] REMOTE INJECTOR ONLINE. Targeting {TARGET_COUNT} molecules.")
    print(f"[*] Sending payloads to: {BRAIN_URL}")
    
    total_injected = 0
    
    while total_injected < TARGET_COUNT:
        batch = []
        while len(batch) < BATCH_SIZE:
            parent = random.choice(SEED_MOLECULES)
            child = mutate(parent)
            if child: batch.append(child)
            
        # Push to Mothership
        try:
            resp = requests.post(f"{BRAIN_URL}/push_to_queue", json={"smiles_list": batch}, timeout=20)
            if resp.status_code == 200:
                inserted = resp.json().get("inserted", 0)
                total_injected += inserted
                print(f"[+] Injected {inserted} new molecules. (Total: {total_injected})")
            else:
                print(f"[!] Server Error: {resp.status_code}")
                time.sleep(10)
        except Exception as e:
            print(f"[!] Connection Error: {e}")
            time.sleep(10)

    print(f"\n[bold green]MISSION COMPLETE[/bold green]")
    print(f"[+] 100,000+ Trojan Metabolites injected into the Brain.")

if __name__ == "__main__":
    run_remote_injector()
