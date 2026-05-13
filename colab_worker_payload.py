"""
colab_worker_payload_v2_5.py
The 'Scientifically Rigorous' Drone Node for GitHub/Colab.
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
    os.system("pip install rdkit-pypi -q")
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
WORKER_ID = f"github_swarm_{str(uuid.uuid4())[:8]}"

def simulate_multi_target(smiles: str):
    try:
        from rdkit import Chem
        import subprocess
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None
        
        # Dock Primary (EGFR) + Capture Pose
        with open("temp.smi", "w") as f: f.write(smiles)
        cmd = ["./smina", "-r", "egfr.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr.pdb", "--exhaustiveness", "1", "--quiet", "--out", "pose.pdbqt"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        primary_score = 0.0
        lines = res.stdout.split('\n')
        for i, line in enumerate(lines):
            if "-----+------------" in line:
                primary_score = float(lines[i+1].split()[1])
                break
        if primary_score > -7.0: return None
        
        # Cross-Dock
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
            
        return {"smiles": smiles, "score": primary_score, "metadata": {"target_profile": profile, "docked_pose": pose}}
    except: return None

def run_worker_loop():
    print(f"[*] SWARM NODE {WORKER_ID} ONLINE.")
    while True:
        try:
            resp = requests.get(f"{BRAIN_URL}/get_work?batch_size=10", headers={"ngrok-skip-browser-warning": "true"}, timeout=15)
            smiles = resp.json().get("smiles_list", [])
            if not smiles: time.sleep(15); continue
            
            results = []
            for s in smiles:
                r = simulate_multi_target(s)
                if r: results.append(r)
            
            if results:
                requests.post(f"{BRAIN_URL}/submit_results", json={"worker_id": WORKER_ID, "molecules": results}, headers={"ngrok-skip-browser-warning": "true"}, timeout=15)
        except Exception as e:
            print(f"Loop Error: {e}"); time.sleep(5)

if __name__ == "__main__":
    setup_env()
    run_worker_loop()
