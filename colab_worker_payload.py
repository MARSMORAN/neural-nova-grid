"""
colab_worker_payload_v2_1_1.py
The 'Scientifically Rigorous' Drone Node for GitHub/Colab.
Version: v2.1.1-stable
"""
import os
import requests
import uuid
import time
import json
import sys

# --- 1. SETUP ENVIRONMENT ---
def setup_env():
    print("[*] Installing Physics Engines...")
    os.system(f"{sys.executable} -m pip install rdkit -q")
    if not os.path.exists("smina"):
        os.system("wget -q https://sourceforge.net/projects/smina/files/smina.static/download -O smina")
        os.system("chmod +x smina")
    
    # Full GBM Proteome
    targets = {"egfr": "1M17", "pi3k": "1E7V", "mtor": "4JSV", "pdgfr": "5GRN"}
    for name, pdb_id in targets.items():
        if not os.path.exists(f"{name}.pdb"):
            os.system(f"wget -q https://files.rcsb.org/download/{pdb_id}.pdb -O {name}.pdb")

# --- 2. MULTI-TARGET DOCKING ENGINE ---
BRAIN_URL = os.environ.get("BRAIN_URL", "https://perjury-dilation-sulphate.ngrok-free.dev")
WORKER_ID = f"swarm_v2_1_1_{str(uuid.uuid4())[:8]}"

def simulate_multi_target(smiles: str):
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors
        import subprocess
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None
        
        # --- STEP 1: FAST SCREEN (exhaustiveness=1) ---
        with open("temp.smi", "w") as f: f.write(smiles)
        cmd = ["./smina", "-r", "egfr.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr.pdb", "--exhaustiveness", "1", "--quiet"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        screen_score = 0.0
        lines = res.stdout.split('\n')
        for i, line in enumerate(lines):
            if "-----+------------" in line:
                screen_score = float(lines[i+1].split()[1])
                break
        
        # Screening Threshold
        if screen_score > -6.5: return None
        
        print(f"[*] Potential Hit Detected ({screen_score}). Running Rigorous Validation...")

        # --- STEP 2: RIGOROUS CHECK (exhaustiveness=8) ---
        cmd = ["./smina", "-r", "egfr.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr.pdb", "--exhaustiveness", "8", "--quiet", "--out", "pose.pdbqt"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        rigorous_score = 0.0
        lines = res.stdout.split('\n')
        for i, line in enumerate(lines):
            if "-----+------------" in line:
                rigorous_score = float(lines[i+1].split()[1])
                break
        
        # Final Scientific Rigor Threshold
        if rigorous_score > -7.0: 
            print(f"[!] Rigorous check failed ({rigorous_score}). Discarding.")
            return None
        
        print(f"[+] Confirmed Rigorous Score: {rigorous_score}")
        
        # Cross-Dock against off-targets
        profile = {}
        for t in ["pi3k", "mtor", "pdgfr"]:
            cmd = ["./smina", "-r", f"{t}.pdb", "-l", "temp.smi", "--autobox_ligand", f"{t}.pdb", "--exhaustiveness", "1", "--quiet"]
            c_res = subprocess.run(cmd, capture_output=True, text=True)
            c_lines = c_res.stdout.split('\n')
            for i, l in enumerate(c_lines):
                if "-----+------------" in l:
                    profile[t] = float(c_lines[i+1].split()[1])
                    break
        
        pose = ""
        if os.path.exists("pose.pdbqt"):
            with open("pose.pdbqt", "r") as f: pose = f.read()
            
        return {"smiles": smiles, "score": rigorous_score, "metadata": {"target_profile": profile, "docked_pose": pose}}
    except Exception as e:
        print(f"[!] Docking Error: {e}")
        return None

def run_worker_loop():
    print(f"[*] SWARM NODE {WORKER_ID} ONLINE (v2.1.1-stable).")
    while True:
        try:
            resp = requests.get(f"{BRAIN_URL}/get_work?batch_size=10", headers={"ngrok-skip-browser-warning": "true"}, timeout=15)
            smiles = resp.json().get("smiles_list", [])
            if not smiles: 
                print("[*] No work available. Sleeping...")
                time.sleep(15)
                continue
            
            results = []
            for s in smiles:
                r = simulate_multi_target(s)
                if r: results.append(r)
            
            if results:
                print(f"[+] Submitting {len(results)} high-potential discoveries...")
                requests.post(f"{BRAIN_URL}/submit_results", json={"worker_id": WORKER_ID, "molecules": results}, headers={"ngrok-skip-browser-warning": "true"}, timeout=15)
        except Exception as e:
            print(f"Loop Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    setup_env()
    run_worker_loop()
