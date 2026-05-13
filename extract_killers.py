import os
import sqlite3
import pandas as pd
from engine.report_generator import ReportGenerator
from engine.repurposer import RepurposingEngine
from rdkit import Chem
from rdkit.Chem import Descriptors


def main():
    out_dir = "./reports/top_tier_killer"
    os.makedirs(out_dir, exist_ok=True)
    
    print("[*] Connecting to Grid Memory...")
    c = sqlite3.connect('grid_memory.db')
    
    rows = c.execute("SELECT smiles, score FROM results ORDER BY score ASC").fetchall()
    
    repurposer = RepurposingEngine()
    drug_df = repurposer.fetch_approved_drugs()
    
    reporter = ReportGenerator(output_dir=out_dir)
    
    found = 0
    for smiles, score in rows:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue  # Skip unparseable grammar errors
            
        print(f"[*] Processing Valid Rank {found+1}: Score {score}")
        
        # Find the real FDA drug name
        match = drug_df[drug_df["smiles"] == smiles]
        drug_name = "Unknown Drug"
        if not match.empty:
            drug_name = match["pref_name"].values[0]
        # RDKit Descriptors
        mw = Descriptors.MolWt(mol) if mol else 0.0
        logp = Descriptors.MolLogP(mol) if mol else 0.0
        hbd = Descriptors.NumHDonors(mol) if mol else 0
        hba = Descriptors.NumHAcceptors(mol) if mol else 0
        tpsa = Descriptors.TPSA(mol) if mol else 0.0
        
        # Realistic ADMET Heuristics based on physical properties
        # BBB: Lower TPSA and MW = better penetration
        bbb_prob = max(0.0, min(1.0, 1.2 - (tpsa/100.0) - (mw/1000.0)))
        
        # Oral Bioavailability: Lipinski violations lower it
        lipinski_violations = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
        oral_bio = max(0.1, 1.0 - (lipinski_violations * 0.3))
        
        # Metabolic Stability: Higher logP and HBD often means faster clearance
        met_stab = max(0.1, min(0.9, 1.0 - (logp/10.0) - (hbd/20.0)))
        
        # hERG Risk: Highly lipophilic/heavy molecules risk cardiac toxicity
        herg = max(0.0, min(0.95, (logp - 2.0)/6.0 + (mw - 300)/1000.0))
        
        candidate = {
            "drug_name": drug_name,
            "smiles": smiles,
            "target": "EGFR/CDK4 (Swarm)",
            "composite_score": score,
            "docking_score": score,
            "bbb_penetration": bbb_prob,
            "oral_bioavailability": oral_bio,
            "metabolic_stability": met_stab,
            "herg_risk": herg,
            "mw": mw,
            "logp": logp,
            "hbd": hbd,
            "hba": hba,
            "tpsa": tpsa
        }
        
        # Generate the beautiful PDF dossier
        reporter.generate_candidate_report(candidate, cycle_id=1)
        found += 1
        if found >= 5:
            break
            
    print(f"[+] Top Tier Killers successfully extracted to {os.path.abspath(out_dir)}")

if __name__ == "__main__":
    main()
