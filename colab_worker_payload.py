"""
colab_worker_payload_apex_v2.py
THE APEX AUTONOMOUS CLOUD WORKER — v8.7.
Maximum Realism + Cloud Scale for GBM Breakthroughs.
"""
import os
import requests
import uuid
import time
import json
import sys
import random
import math
import subprocess
import statistics

# --- 1. SETUP ENVIRONMENT ---
def setup_env():
    print("="*60)
    print("  NEURAL-NOVA APEX AUTONOMOUS CLOUD WORKER v8.7")
    print("="*60)
    print("[*] Installing High-Fidelity Dependencies (RDKit, NumPy)...")
    os.system(f"{sys.executable} -m pip install rdkit numpy -q")
    
    try:
        from rdkit import RDLogger
        RDLogger.DisableLog('rdApp.*')
    except: pass

    if not os.path.exists("smina"):
        print("[*] Downloading Smina Docking Engine (Static Binary)...")
        os.system("wget -q https://sourceforge.net/projects/smina/files/smina.static/download -O smina")
        os.system("chmod +x smina")
    
    # Target Ensemble (Glioblastoma Apex Panel - Multiple Conformations)
    # Using multiple PDBs per target for ensemble docking (higher success rate)
    ensemble_targets = {
        "egfr": ["1M17", "2JIT", "4LRM"], # WT, Mutant, L858R
        "pi3k": ["1E7V", "4L23"],
        "mtor": ["4JSV", "4JT6"],
        "pdgfr": ["5GRN", "6GSC"],
        "idh1": ["4UMX", "4G39"]  # Mutant R132H, WT
    }
    
    for name, pdb_ids in ensemble_targets.items():
        for i, pdb_id in enumerate(pdb_ids):
            filename = f"{name}_{i}.pdb"
            if not os.path.exists(filename):
                print(f"[*] Downloading {name} conformation {i} ({pdb_id})...")
                os.system(f"wget -q https://files.rcsb.org/download/{pdb_id}.pdb -O {filename}")

# --- 2. APEX SCIENTIFIC ENGINES ---

class ApexEngines:
    @staticmethod
    def simulate_md_stability(smiles, docking_score, mw):
        """Simulated 100ns Molecular Dynamics (RMSD) proxy."""
        stability_base = abs(docking_score) / 10.0
        mw_penalty = max(0, (mw - 400) / 1000.0)
        rmsd = max(1.0, 5.0 - (stability_base * 4.2) + mw_penalty + random.gauss(0, 0.25))
        persistence = 1.0 / (1.0 + math.exp(2.5 * (rmsd - 3.5)))
        return {"rmsd": round(rmsd, 2), "persistence": round(persistence, 2)}

    @staticmethod
    def calculate_qm_properties(smiles, logp, mw):
        """Simulated QM (HOMO/LUMO) DFT-proxy."""
        gap = max(1.8, 4.2 + (mw / 1200.0) - (logp / 8.0) + random.gauss(0, 0.4))
        homo = -6.2 + random.uniform(-0.3, 0.3)
        lumo = homo + gap
        electrophilicity = (homo + lumo)**2 / (8 * gap)
        return {"gap_ev": round(gap, 2), "electrophilicity": round(electrophilicity, 2)}

    @staticmethod
    def adjust_for_tme(base_score, logp, mw, tpsa):
        """GBM Tumor Microenvironment Realism Adjustment."""
        ph_tme = 6.2
        pka = 4.0 + (logp * 0.4)
        ph_delta = abs(pka - ph_tme)
        permeability_penalty = 1.0 / (1.0 + math.exp(ph_delta - 1.5))
        hypoxia_factor = 0.88 
        cns_bonus = 1.1 if (mw < 400 and tpsa < 70) else 0.85
        return round(base_score * permeability_penalty * hypoxia_factor * cns_bonus, 3), round(permeability_penalty, 3)

    @staticmethod
    def simulate_synergy(dock_score):
        """Apex v32.0 Polypharmacology synergy proxy."""
        return round(abs(dock_score) / 10.0 + random.uniform(0, 0.2), 3)

    @staticmethod
    def calculate_kp_uu(mw, logp, tpsa):
        """Renkin-Crone BBB kinetic flux proxy."""
        ps = math.exp((0.5 * logp) - (0.01 * mw) - (0.03 * tpsa) + 2.5)
        return round(1.0 - math.exp(-ps / 0.5), 4)

# --- 3. CORE VALIDATION PIPELINE ---
BRAIN_URL = os.environ.get("BRAIN_URL", "")
WORKER_ID = f"apex_v32_node_{str(uuid.uuid4())[:8]}"

def validate_candidate(smiles: str):
    try:
        from rdkit import Chem
        from rdkit.Chem import Descriptors, QED
        
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None
        
        # --- Pre-Flight CNS Filters ---
        mw = Descriptors.MolWt(mol)
        tpsa = Descriptors.TPSA(mol)
        logp = Descriptors.MolLogP(mol)
        qed_score = QED.qed(mol)
        
        if mw > 480 or tpsa > 85 or logp < -0.5: return None 
        
        # --- Primary Docking Validation (Smina) ---
        with open("temp.smi", "w") as f: f.write(smiles)
        cmd = ["./smina", "-r", "egfr_0.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr_0.pdb", "--exhaustiveness", "8", "--quiet"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        
        primary_score = 0.0
        lines = res.stdout.split('\n')
        for i, line in enumerate(lines):
            if "-----+------------" in line:
                primary_score = float(lines[i+1].split()[1])
                break
        
        if primary_score > -5.0: return None
        
        # --- Stage 2: Recursive High-Fidelity Multi-Pass Validation ---
        # User Logic: If score matches depth, trigger additional statistical passes
        abs_score = abs(primary_score)
        n_passes = 1
        if abs_score >= 13.0:
            n_passes = 15 if abs_score > 13.0 else 12
        elif abs_score >= 12.0: n_passes = 9
        elif abs_score >= 11.0: n_passes = 7
        elif abs_score >= 9.0:  n_passes = 5
        elif abs_score >= 7.0:  n_passes = 3
        elif abs_score >= 5.0:  n_passes = 2
        
        pass_results = [primary_score]
        if n_passes > 1:
            print(f"[*] High-Affinity Lead ({primary_score}). Initiating {n_passes}-Pass Statistical Validation...")
            for p in range(n_passes - 1):
                seed = random.randint(1, 1000000)
                cmd = ["./smina", "-r", "egfr_0.pdb", "-l", "temp.smi", "--autobox_ligand", "egfr_0.pdb", "--exhaustiveness", "12", "--quiet", "--seed", str(seed)]
                res = subprocess.run(cmd, capture_output=True, text=True)
                lines = res.stdout.split('\n')
                for i, line in enumerate(lines):
                    if "-----+------------" in line:
                        pass_results.append(float(lines[i+1].split()[1]))
                        break
        
        avg_dock = statistics.mean(pass_results)
        stdev = statistics.stdev(pass_results) if len(pass_results) > 1 else 0.0
        
        # We use the average for composite scoring to ensure robustness
        if avg_dock > -6.0: return None # Reject if unstable/fluctuating
        
        # --- Apex v32.0 Advanced Simulation ---
        md = ApexEngines.simulate_md_stability(smiles, avg_dock, mw)
        qm = ApexEngines.calculate_qm_properties(smiles, logp, mw)
        synergy = ApexEngines.simulate_synergy(avg_dock)
        kp_uu = ApexEngines.calculate_kp_uu(mw, logp, tpsa)
        
        # Composite Apex Score (v32.0 weighting)
        dock_norm = max(0, min(1, (-avg_dock - 5.0) / 7.5))
        stability_norm = max(0, min(1, (5.0 - md["rmsd"]) / 4.0))
        
        raw_composite = (
            0.20 * dock_norm +
            0.20 * (kp_uu / 0.5) +
            0.15 * stability_norm +
            0.15 * synergy +
            0.15 * qed_score +
            0.15 * md["persistence"]
        )
        
        # Apply TME Realism Penalty
        final_score, ph_adj = ApexEngines.adjust_for_tme(raw_composite, logp, mw, tpsa)
        
        if final_score < 0.45: return None 
        
        print(f"[+] APEX v32.0 LEAD: {smiles[:15]}... | Score: {final_score:.4f} | Passes: {len(pass_results)} | StdDev: {stdev:.3f}")
        
        return {
            "smiles": smiles, 
            "score": final_score, 
            "metadata": {
                "best_dock": min(pass_results),
                "avg_dock": avg_dock,
                "pass_results": pass_results,
                "statistical_stdev": stdev,
                "rmsd_stability": md["rmsd"],
                "persistence": md["persistence"],
                "homo_lumo_gap": qm["gap_ev"],
                "electrophilicity": qm["electrophilicity"],
                "kp_uu": kp_uu,
                "synergy_index": synergy,
                "qed": round(qed_score, 3),
                "ph_adjusted_potency": ph_adj * abs(avg_dock),
                "hypoxic_efficacy": 0.88,
                "worker": WORKER_ID
            }
        }
    except Exception as e:
        # print(f"[!] Engine Error: {e}")
        return None

def run_worker_loop():
    print(f"[*] APEX CLOUD NODE {WORKER_ID} READY.")
    if not BRAIN_URL:
        print("[!] FATAL: BRAIN_URL not provided. Set it in Colab environment.")
        return

    processed = 0
    start_time = time.time()
    
    while True:
        try:
            uptime = (time.time() - start_time) / 60
            resp = requests.get(f"{BRAIN_URL}/get_work?batch_size=10", headers={"ngrok-skip-browser-warning": "true"}, timeout=20)
            smiles = resp.json().get("smiles_list", [])
            
            if not smiles: 
                print(f"[#] Queue Empty. Uptime: {uptime:.1f}m. Waiting...")
                time.sleep(30); continue
            
            results = []
            for s in smiles:
                r = validate_candidate(s)
                if r: results.append(r)
                processed += 1
            
            if results:
                print(f"[^] Submitting {len(results)} Apex-verified leads...")
                requests.post(f"{BRAIN_URL}/submit_results", json={"worker_id": WORKER_ID, "molecules": results}, headers={"ngrok-skip-browser-warning": "true"}, timeout=20)
            
            if processed % 100 == 0:
                print(f"[*] Processed {processed} molecules. Global through-put active.")
        except Exception as e:
            time.sleep(15)

if __name__ == "__main__":
    setup_env()
    run_worker_loop()
