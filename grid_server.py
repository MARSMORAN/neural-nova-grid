import os
import json
import sqlite3
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Dict

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Neural-Nova Grid Brain v2")

# Serve targets for the swarm
if not os.path.exists("./targets"):
    os.makedirs("./targets")
app.mount("/static", StaticFiles(directory="./targets"), name="static")

class MoleculeBatch(BaseModel):
    worker_id: str
    molecules: List[Dict]

DB_FILE = "grid_memory.db"

@app.get("/", response_class=HTMLResponse)
def get_dashboard():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Neural-Nova Mothership</title>
        <style>
            body { background-color: #050510; color: #00ffcc; font-family: 'Courier New', monospace; text-align: center; margin-top: 50px; }
            h1 { text-shadow: 0 0 10px #00ffcc; font-size: 3em; }
            .panel { background: rgba(0, 255, 204, 0.05); border: 1px solid #00ffcc; padding: 20px; width: 60%; margin: 0 auto; box-shadow: 0 0 20px rgba(0, 255, 204, 0.2); }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border-bottom: 1px solid #00ffcc; padding: 10px; text-align: left; }
            th { background: rgba(0, 255, 204, 0.2); }
            .glow { animation: pulse 2s infinite; }
            @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; text-shadow: 0 0 15px #00ffcc; } 100% { opacity: 0.8; } }
        </style>
    </head>
    <body>
        <h1 class="glow">NEURAL-NOVA COMMAND CENTER</h1>
        <div class="panel">
            <h2>LIVE SWARM LEADERBOARD</h2>
            <p>Awaiting incoming telemetry from GitHub/Colab drone nodes...</p>
            <table>
                <thead><tr><th>Target Molecule (SMILES)</th><th>Binding Score</th><th>Drone ID</th></tr></thead>
                <tbody id="board"><tr><td colspan="3">Scanning sector...</td></tr></tbody>
            </table>
        </div>
        <script>
            async function fetchBoard() {
                try {
                    let res = await fetch('/leaderboard');
                    let data = await res.json();
                    if(data.length > 0) {
                        let html = '';
                        data.forEach(d => {
                            html += `<tr><td>${d.smiles.substring(0, 40)}...</td><td>${d.score.toFixed(3)}</td><td>${d.worker_id}</td></tr>`;
                        });
                        document.getElementById('board').innerHTML = html;
                    }
                } catch(e) {}
            }
            setInterval(fetchBoard, 3000);
            fetchBoard();
        </script>
    </body>
    </html>
    """


def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS queue (
            id INTEGER PRIMARY KEY,
            smiles TEXT UNIQUE,
            status TEXT DEFAULT 'pending'
        );
        CREATE TABLE IF NOT EXISTS results (
            id INTEGER PRIMARY KEY,
            smiles TEXT UNIQUE,
            score REAL,
            worker_id TEXT,
            target_profile TEXT,
            docked_pose TEXT
        );
    """)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/get_work")
def get_work(batch_size: int = 100):
    """Worker calls this to get a chunk of SMILES to process."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute("SELECT smiles FROM queue WHERE status = 'pending' LIMIT ?", (batch_size,))
    rows = c.fetchall()
    
    if not rows:
        return {"smiles_list": []}
        
    smiles_list = [r[0] for r in rows]
    
    # Mark as processing
    placeholders = ",".join(["?"] * len(smiles_list))
    c.execute(f"UPDATE queue SET status = 'processing' WHERE smiles IN ({placeholders})", smiles_list)
    conn.commit()
    conn.close()
    
    return {"smiles_list": smiles_list}

from engine.report_generator import ReportGenerator

# Setup PDF Reporter
reporter = ReportGenerator(output_dir="./reports/gen_2_discoveries")

@app.post("/submit_results")
def submit_results(batch: MoleculeBatch):
    """Worker submits the top docking scores back to the Brain."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    for mol in batch.molecules:
        score = mol.get("score", 0.0)
        smiles = mol.get("smiles", "")
        candidate_data = mol.get("metadata", {})
        
        try:
            # Store result
            # SCIENTIFIC CALIBRATION: We now log EVERYTHING (even bad scores) to build ROC-AUC curves
            c.execute("""
                INSERT OR REPLACE INTO results (smiles, score, worker_id, target_profile)
                VALUES (?, ?, ?, ?)
            """, (smiles, score, batch.worker_id, json.dumps(candidate_data.get("target_profile", {}))))
            
            # Remove from queue if it was there
            c.execute("DELETE FROM queue WHERE smiles = ?", (smiles,))
            
            # NEW: Auto-generate a full research PDF if the score is incredibly good
            if score <= -8.0:
                print(f"[+] MASSIVE HIT DETECTED: {score}. Generating Multi-Target PDF...")
                from rdkit.Chem import QED
                
                mol = Chem.MolFromSmiles(smiles)
                if mol is not None:
                    mw = Descriptors.MolWt(mol)
                    logp = Descriptors.MolLogP(mol)
                    hbd = Descriptors.NumHDonors(mol)
                    hba = Descriptors.NumHAcceptors(mol)
                    tpsa = Descriptors.TPSA(mol)
                    
                    # New Rigor Metrics
                    qed_score = QED.qed(mol) # 0 to 1 drug-likeness
                    
                    # Selectivity Index: Ratio of primary target to average of others
                    profile = candidate_data.get("target_profile", {})
                    if profile:
                        avg_off_target = sum(profile.values()) / len(profile)
                        selectivity = score / avg_off_target if avg_off_target != 0 else 1.0
                    else:
                        selectivity = 1.0
                    
                    bbb_prob = max(0.0, min(1.0, 1.2 - (tpsa/100.0) - (mw/1000.0)))
                    lipinski_violations = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
                    oral_bio = max(0.1, 1.0 - (lipinski_violations * 0.3))
                    met_stab = max(0.1, min(0.9, 1.0 - (logp/10.0) - (hbd/20.0)))
                    herg = max(0.0, min(0.95, (logp - 2.0)/6.0 + (mw - 300)/1000.0))
                    
                    # NovaScore™ Unified Confidence Index (0 to 100)
                    # Higher is better. Weighted for scientific viability.
                    norm_docking = max(0, min(1, (abs(score) - 5) / 10)) # Normalize -5 to -15 range
                    nova_score = (
                        (norm_docking * 40) +      # 40% Docking Power
                        (qed_score * 25) +         # 25% Drug-likeness
                        (bbb_prob * 20) +          # 20% CNS Permeability
                        (min(1.0, selectivity) * 15) # 15% Precision/Selectivity
                    ) * 10
                    
                    candidate = {
                        "drug_name": "Nova-Validated Discovery",
                        "smiles": smiles,
                        "target": "EGFR + PI3K/mTOR/PDGFR",
                        "nova_score": nova_score,
                        "composite_score": score,
                        "docking_score": score,
                        "target_profile": profile,
                        "selectivity_index": selectivity,
                        "qed": qed_score,
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
                    reporter.generate_candidate_report(candidate, cycle_id=999)
                
        except Exception as e:
            pass
            
    conn.commit()
    conn.close()
    return {"status": "success"}

@app.get("/leaderboard")
def leaderboard():
    """See the top drug candidates found by the entire global swarm."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT smiles, score, worker_id FROM results ORDER BY score ASC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return [{"smiles": r[0], "score": r[1], "worker_id": r[2]} for r in rows]

if __name__ == "__main__":
    print("STARTING NEURAL-NOVA GRID BRAIN ON PORT 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
