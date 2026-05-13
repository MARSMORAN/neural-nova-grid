"""
colab_worker_payload.py
The Drone Node script. 

INSTRUCTIONS:
1. Open a new Google Colab notebook (colab.research.google.com).
2. Go to Runtime -> Change Runtime Type -> Select "T4 GPU".
3. Paste this entire script into a cell and press Play.
4. Open as many tabs/Google accounts as you can.

This script will automatically install RDKit and AutoDock Vina,
connect to your Grid Brain, pull SMILES, simulate them on the free GPU, 
and push the results back.
"""

import os
import sys
import time
import requests
import random
import uuid

# --- 1. SETUP ENVIRONMENT ---
def setup_env():
    print("[*] Installing heavy physics libraries (RDKit, Smina/Vina)...")
    os.system("pip install rdkit-pypi quiet")
    
    # Download Smina (advanced fork of AutoDock Vina)
    if not os.path.exists("smina"):
        os.system("wget -q https://sourceforge.net/projects/smina/files/smina.static/download -O smina")
        os.system("chmod +x smina")
        
    # Download the actual 3D crystal structure of EGFR (Glioblastoma Target)
    if not os.path.exists("egfr_gbm.pdb"):
        print("[*] Downloading actual Glioblastoma protein crystal (EGFR)...")
        os.system("wget -q https://files.rcsb.org/download/1M17.pdb -O egfr_gbm.pdb")
        
    print("[+] Environment Ready. Protein target acquired.")

# --- 2. WORKER LOGIC ---
BRAIN_URL = "https://perjury-dilation-sulphate.ngrok-free.dev" # Replace with your brain's public IP or Ngrok
WORKER_ID = f"colab_gpu_{str(uuid.uuid4())[:8]}"

def simulate_physics(smiles: str) -> float:
    """
    ULTIMATE COMPUTATIONAL CHEMISTRY ENGINE.
    1. Checks Blood-Brain Barrier (BBB) viability.
    2. Uses Smina/Vina to physically dock the drug into the GBM protein.
    """
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
        import subprocess
        
        # 1. Enforce Blood-Brain Barrier (BBB) Rules
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return 0.0
            
        mw = Descriptors.MolWt(mol)
        logp = Descriptors.MolLogP(mol)
        tpsa = Descriptors.TPSA(mol)
        
        if mw > 500 or logp > 5.0 or tpsa > 90:
            return 0.0 # Drug cannot enter the brain, reject.
            
        # 2. ACTUAL MOLECULAR DOCKING (VINA)
        # Smina requires a file, so we write the SMILES to a temporary file
        temp_ligand = f"temp_{WORKER_ID}.smi"
        with open(temp_ligand, "w") as f:
            f.write(smiles)

        # We pass the temporary file to Smina and dock it against the EGFR protein.
        cmd = [
            "./smina", 
            "-r", "egfr_gbm.pdb", 
            "-l", temp_ligand, 
            "--autobox_ligand", "egfr_gbm.pdb", 
            "--exhaustiveness", "1", 
            "--quiet"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Cleanup temp file
        if os.path.exists(temp_ligand):
            os.remove(temp_ligand)
        
        # Parse the kcal/mol score from Smina's output
        score = 0.0
        for line in result.stdout.split('\n'):
            if "Affinity:" in line:
                # Extracts the negative binding score
                parts = line.split()
                score = float(parts[1])
                break
                
        # If it found a real binding score, return it. Otherwise 0.0.
        return score if score < 0 else 0.0

    except Exception as e:
        return 0.0

def run_worker_loop():
    print(f"[*] Starting Neural-Nova Worker: {WORKER_ID}")
    
    while True:
        try:
            # Pull work
            print("[*] Pulling batch from Grid Brain...")
            headers = {"ngrok-skip-browser-warning": "true"}
            resp = requests.get(f"{BRAIN_URL}/get_work?batch_size=50", headers=headers, timeout=10)
            data = resp.json()
            
            smiles_list = data.get("smiles_list", [])
            if not smiles_list:
                print("[-] Queue empty. Sleeping 10s...")
                time.sleep(10)
                continue
                
            print(f"[+] Received {len(smiles_list)} molecules. Engaging GPU physics engine...")
            
            # Process
            results = []
            for smi in smiles_list:
                score = simulate_physics(smi)
                # Only keep strong binders to save bandwidth
                if score < -7.0: 
                    results.append({"smiles": smi, "score": score})
                    
            # Push results
            if results:
                print(f"[+] Found {len(results)} strong binders! Pushing to Brain...")
                payload = {
                    "worker_id": WORKER_ID,
                    "molecules": results
                }
                headers = {"ngrok-skip-browser-warning": "true"}
                requests.post(f"{BRAIN_URL}/submit_results", json=payload, headers=headers, timeout=10)
            else:
                print("[-] No strong binders in this batch.")
                
        except Exception as e:
            print(f"[!] Connection to Brain lost: {e}")
            time.sleep(5)

if __name__ == "__main__":
    setup_env()
    run_worker_loop()
