import os
import json
import sqlite3
import uvicorn
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import List, Dict

from fastapi.staticfiles import StaticFiles

app = FastAPI(title="Neural-Nova Sovereign Brain v8.0")

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
        <title>Neural-Nova Sovereign v8.0</title>
        <style>
            body { background-color: #050510; color: #00ffcc; font-family: 'Courier New', monospace; text-align: center; margin-top: 50px; }
            h1 { text-shadow: 0 0 10px #00ffcc; font-size: 3.2em; font-weight: bold; }
            .panel { background: rgba(0, 255, 204, 0.05); border: 1px solid #00ffcc; padding: 20px; width: 70%; margin: 0 auto; box-shadow: 0 0 30px rgba(0, 255, 204, 0.2); }
            table { width: 100%; border-collapse: collapse; margin-top: 20px; }
            th, td { border-bottom: 1px solid #00ffcc; padding: 12px; text-align: left; }
            th { background: rgba(0, 255, 204, 0.2); text-transform: uppercase; letter-spacing: 2px; }
            .glow { animation: pulse 2s infinite; }
            @keyframes pulse { 0% { opacity: 0.8; } 50% { opacity: 1; text-shadow: 0 0 20px #00ffcc; } 100% { opacity: 0.8; } }
            .v8-tag { color: #ff0066; font-weight: bold; border: 1px solid #ff0066; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; vertical-align: middle; }
        </style>
    </head>
    <body>
        <h1 class="glow">SOVEREIGN MISSION CONTROL <span class="v8-tag">v8.0</span></h1>
        <div class="panel">
            <h2>GLOBAL DISCOVERY TELEMETRY</h2>
            <p>Awaiting high-rigor data from Sovereign Swarm nodes...</p>
            <table>
                <thead><tr><th>Candidate Signature (SMILES)</th><th>Binding Score (\u0394G)</th><th>Drone ID</th></tr></thead>
                <tbody id="board"><tr><td colspan="3">Synchronizing with swarm...</td></tr></tbody>
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
                            html += `<tr><td><code>${d.smiles.substring(0, 45)}...</code></td><td><b>${d.score.toFixed(3)}</b> kcal/mol</td><td>${d.worker_id}</td></tr>`;
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

class SMILESBatch(BaseModel):
    smiles_list: List[str]

@app.post("/push_to_queue")
def push_to_queue(batch: SMILESBatch):
    """Remote generator pushes new SMILES into the Mothership queue."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    inserted = 0
    for smiles in batch.smiles_list:
        try:
            c.execute("INSERT OR IGNORE INTO queue (smiles) VALUES (?)", (smiles,))
            if c.rowcount > 0:
                inserted += 1
        except:
            pass
    conn.commit()
    conn.close()
    return {"status": "success", "inserted": inserted}

from engine.report_generator import ReportGenerator

# Setup PDF Reporters
local_reporter = ReportGenerator(output_dir="./reports/gen_2_discoveries")
swarm_reporter = ReportGenerator(output_dir="./reports/swarm_discoveries")

@app.post("/submit_results")
def submit_results(batch: MoleculeBatch):
    """Worker submits the top docking scores back to the Brain."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Determine which reporter to use
    is_swarm = batch.worker_id.startswith("swarm_")
    reporter = swarm_reporter if is_swarm else local_reporter
    
    for mol in batch.molecules:
        score = mol.get("score", 0.0)
        smiles = mol.get("smiles", "")
        candidate_data = mol.get("metadata", {})
        
        try:
            # Store result
            c.execute("""
                INSERT OR REPLACE INTO results (smiles, score, worker_id, target_profile)
                VALUES (?, ?, ?, ?)
            """, (smiles, score, batch.worker_id, json.dumps(candidate_data.get("target_profile", {}))))
            
            # Remove from queue
            c.execute("DELETE FROM queue WHERE smiles = ?", (smiles,))
            
            # Trigger Sovereign v8.0 Report Generation for High-Potency Hits
            if score <= -8.0:
                print(f"[+] SOVEREIGN HIT DETECTED: {score}. Generating Clinical Dossier...")
                
                # Pass all gathered metadata to the reporter
                candidate = {
                    "smiles": smiles,
                    "docking_score": score,
                    "target_profile": candidate_data.get("target_profile", {}),
                    "stochastic_variance": candidate_data.get("stochastic_variance", 0.0)
                }
                try:
                    reporter.generate_candidate_report(candidate, cycle_id=800)
                except Exception as e:
                    print(f"[!] REPORT GEN FAILURE: {e}")

        except Exception as e:
            print(f"[!] SUBMISSION ERROR: {e}")

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

@app.get("/reports", response_class=HTMLResponse)
def list_reports():
    """Browser-based dashboard to view all discovery dossiers."""
    reports_base = Path("./reports")
    if not reports_base.exists():
        return "<html><body><h1>No reports generated yet.</h1></body></html>"
    
    # Glob for both local and swarm reports
    files = list(reports_base.rglob("*.pdf")) + list(reports_base.rglob("*.txt"))
    # Filter out summaries and only keep candidate dossiers
    files = [f for f in files if "cycle_summary" not in f.name]
    files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
    
    html = "<html><head><title>Neural-Nova Discovery Dossiers</title></head><body>"
    html += "<h1>Neural-Nova Discovery Dossiers (Calibrated)</h1><ul>"
    for f in files:
        rel_path = f.relative_to(reports_base)
        html += f'<li><a href="/reports/download/{rel_path}">{rel_path}</a> ({datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")})</li>'
    html += "</ul></body></html>"
    return html

@app.get("/reports/download/{subpath:path}")
def download_report(subpath: str):
    """Download a specific report dossier."""
    report_file = Path("./reports") / subpath
    if not report_file.exists():
        raise HTTPException(status_code=404, detail="Report not found")
    return FileResponse(report_file)

if __name__ == "__main__":
    print("STARTING NEURAL-NOVA GRID BRAIN ON PORT 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
