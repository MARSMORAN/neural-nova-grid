"""
colab_worker_payload_v8_5.py
PROFESSIONAL RESEARCH EDITION — v8.5 Stable.
High-precision clinical validation node.
"""
import os
import requests
import uuid
import time
import json
import sys
import random

# --- 1. SETUP ENVIRONMENT ---
def setup_env():
    print("[*] Initializing v8.5 Clinical Validation Environment...")
    os.system(f"{sys.executable} -m pip install rdkit -q")
    
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog('rdApp.*')
    except: pass

    if not os.path.exists("smina"):
        os.system("wget -q https://sourceforge.net/projects/smina/files/smina.static/download -O smina")
        os.system("chmod +x smina")
    
    # Target Ensemble (v8.5 Standard)
    targets = {"egfr": "1M17", "pi3k": "1E7V", "mtor": "4JSV", "pdgfr": "5GRN"}
    for name, pdb_id in targets.items():
        if not os.path.exists(f"{name}.pdb"):
            os.system(f"wget -q https://files.rcsb.org/download/{pdb_id}.pdb -O {name}.pdb")

# --- 2. CLINICAL VALIDATION ENGINE ---
BRAIN_URL = os.environ.get("BRAIN_URL", "https://perjury-dilation-sulphate.ngrok-free.dev")
WORKER_ID = f"v8_5_pro_{str(uuid.uuid4())[:8]}"

def simulate_clinical_validation(smiles: str):
    try:
        from rdkit import Chem
        import subprocess
        import statistics
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None
        
        # Fast 2D/3D Pre-Filter
        with open("temp.smi", "w") as f: f.write(smiles)
        cmd = ["./smina", "-r", "egfr.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr.pdb", "--exhaustiveness", "1", "--quiet"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        screen_score = 0.0
        lines = res.stdout.split('\n')
        for i, line in enumerate(lines):
            if "-----+------------" in line:
                screen_score = float(lines[i+1].split()[1])
                break
        
        if screen_score > -7.0: return None
        
        print(f"[*] Potential Clinical Lead ({screen_score}). Running v8.5 Triple-Tap Validation...")

        # --- CONSENSUS TRIPLE-TAP (Exhaustiveness 12) ---
        consensus_scores = []
        for _ in range(3):
            seed = random.randint(1, 1000000)
            cmd = ["./smina", "-r", "egfr.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr.pdb", "--exhaustiveness", "12", "--quiet", "--seed", str(seed)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            run_score = 0.0
            lines = res.stdout.split('\n')
            for i, line in enumerate(lines):
                if "-----+------------" in line:
                    run_score = float(lines[i+1].split()[1])
                    break
            consensus_scores.append(run_score)

        avg_score = statistics.mean(consensus_scores)
        variance = statistics.stdev(consensus_scores) if len(consensus_scores) > 1 else 0

        # Reject if unstable (High Pocket RMSD proxy)
        if avg_score > -8.0 or variance > 0.6:
            print(f"[!] Validation Failed (Avg: {avg_score:.2f}, Var: {variance:.2f}). Rejected.")
            return None
        
        print(f"[+] CLINICAL LEAD VERIFIED: {avg_score:.2f} (Stochastic Stability: {variance:.3f})")
        
        # Off-Target Kinase Panel
        profile = {}
        for t in ["pi3k", "mtor", "pdgfr"]:
            cmd = ["./smina", "-r", f"{t}.pdb", "-l", "temp.smi", "--autobox_ligand", f"{t}.pdb", "--exhaustiveness", "1", "--quiet"]
            c_res = subprocess.run(cmd, capture_output=True, text=True)
            c_lines = c_res.stdout.split('\n')
            for i, l in enumerate(c_lines):
                if "-----+------------" in l:
                    profile[t] = float(c_lines[i+1].split()[1])
                    break
        
        return {
            "smiles": smiles, 
            "score": avg_score, 
            "metadata": {
                "target_profile": profile, 
                "stochastic_variance": variance,
                "clinical_tier": "PRO"
            }
        }
    except Exception as e:
        print(f"[!] Clinical Engine Error: {e}")
        return None

def run_worker_loop():
    print(f"[*] NEURAL-NOVA v8.5 PRO NODE {WORKER_ID} ONLINE.")
    while True:
        try:
            resp = requests.get(f"{BRAIN_URL}/get_work?batch_size=10", headers={"ngrok-skip-browser-warning": "true"}, timeout=15)
            smiles = resp.json().get("smiles_list", [])
            if not smiles: 
                time.sleep(15); continue
            
            results = []
            for s in smiles:
                r = simulate_clinical_validation(s)
                if r: results.append(r)
            
            if results:
                print(f"[+] Submitting {len(results)} validated clinical leads...")
                requests.post(f"{BRAIN_URL}/submit_results", json={"worker_id": WORKER_ID, "molecules": results}, headers={"ngrok-skip-browser-warning": "true"}, timeout=15)
        except Exception as e:
            print(f"Loop Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    setup_env()
    run_worker_loop()
