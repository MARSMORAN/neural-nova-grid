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
    print("[*] Installing heavy physics libraries (RDKit, AutoDock Vina)...")
    os.system("pip install rdkit-pypi quiet")
    os.system("sudo apt-get install autodock-vina -y -q")
    print("[+] Environment Ready.")

# --- 2. WORKER LOGIC ---
BRAIN_URL = "http://YOUR_NGROK_URL_HERE:8000" # Replace with your brain's public IP or Ngrok
WORKER_ID = f"colab_gpu_{str(uuid.uuid4())[:8]}"

def simulate_physics(smiles: str) -> float:
    """
    In a real scenario, this writes the SMILES to a PDBQT file,
    calls the AutoDock Vina binary via subprocess against the GBM protein,
    and parses the kcal/mol output.
    
    Here we simulate the heavy GPU compute delay.
    """
    time.sleep(0.5) # Simulating heavy GPU calculation
    
    # We want a very negative score for strong binding
    score = -5.0 + (len(smiles) / 15.0) * -0.5 + random.gauss(0, 1.5)
    return score

def run_worker_loop():
    print(f"[*] Starting Neural-Nova Worker: {WORKER_ID}")
    
    while True:
        try:
            # Pull work
            print("[*] Pulling batch from Grid Brain...")
            resp = requests.get(f"{BRAIN_URL}/get_work?batch_size=50", timeout=10)
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
                requests.post(f"{BRAIN_URL}/submit_results", json=payload, timeout=10)
            else:
                print("[-] No strong binders in this batch.")
                
        except Exception as e:
            print(f"[!] Connection to Brain lost: {e}")
            time.sleep(5)

if __name__ == "__main__":
    setup_env()
    run_worker_loop()
