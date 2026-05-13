"""
local_worker.py
Multi-threaded Local Drone Node.

Runs the Neural-Nova physics engine directly on your computer's CPU cores,
pulling from the local Brain database.
"""

import os
import sys
import time
import requests
import random
import uuid
import multiprocessing

# Direct local connection to the Brain (no Ngrok needed since it's on the same PC)
BRAIN_URL = "http://127.0.0.1:8000"

def simulate_physics(smiles: str) -> float:
    # Simulating the GPU compute delay
    time.sleep(0.5) 
    
    # We want a very negative score for strong binding
    score = -5.0 + (len(smiles) / 15.0) * -0.5 + random.gauss(0, 1.5)
    return score

def run_worker_thread(worker_id):
    print(f"[*] Starting Local Drone: {worker_id}")
    
    # We use a session for faster local API calls
    session = requests.Session()
    
    while True:
        try:
            # Pull work from the local brain
            resp = session.get(f"{BRAIN_URL}/get_work?batch_size=50", timeout=5)
            data = resp.json()
            
            smiles_list = data.get("smiles_list", [])
            if not smiles_list:
                time.sleep(5)
                continue
                
            # Process the molecules
            results = []
            for smi in smiles_list:
                score = simulate_physics(smi)
                if score < -7.0: 
                    results.append({"smiles": smi, "score": score})
                    
            # Push results back to the local brain
            if results:
                payload = {
                    "worker_id": worker_id,
                    "molecules": results
                }
                session.post(f"{BRAIN_URL}/submit_results", json=payload, timeout=5)
                
        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    print("=========================================")
    print(" NEURAL-NOVA LOCAL MULTI-CORE CLUSTER")
    print("=========================================")
    
    # Get the number of CPU cores on your laptop
    num_cores = multiprocessing.cpu_count()
    # Leave 1 core free so your laptop doesn't completely freeze
    cores_to_use = max(1, num_cores - 1)
    
    print(f"[*] Detected {num_cores} CPU Cores. Booting {cores_to_use} Local Drones...\n")
    
    # Spawn a drone on each CPU core
    processes = []
    for i in range(cores_to_use):
        worker_id = f"local_core_{i+1}_{str(uuid.uuid4())[:4]}"
        p = multiprocessing.Process(target=run_worker_thread, args=(worker_id,))
        p.start()
        processes.append(p)
        
    try:
        for p in processes:
            p.join()
    except KeyboardInterrupt:
        print("\n[*] Shutting down local drones...")
        for p in processes:
            p.terminate()
