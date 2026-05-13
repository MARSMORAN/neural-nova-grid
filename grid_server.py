"""
grid_server.py
The Central Brain of the Neural-Nova Decentralized Grid.

This lightweight server holds the queue of molecules to test and 
receives the docking results from the distributed worker swarm 
(Colab, Kaggle, old laptops, etc).
"""

import os
import json
import sqlite3
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict

app = FastAPI(title="Neural-Nova Grid Brain")

class MoleculeBatch(BaseModel):
    worker_id: str
    molecules: List[Dict]

DB_FILE = "grid_memory.db"

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
            worker_id TEXT
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

@app.post("/submit_results")
def submit_results(batch: MoleculeBatch):
    """Worker submits the top docking scores back to the Brain."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    for mol in batch.molecules:
        try:
            c.execute("""
                INSERT OR REPLACE INTO results (smiles, score, worker_id)
                VALUES (?, ?, ?)
            """, (mol["smiles"], mol["score"], batch.worker_id))
            
            # Remove from queue if it was there
            c.execute("DELETE FROM queue WHERE smiles = ?", (mol["smiles"],))
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
    c.execute("SELECT smiles, score, worker_id FROM results ORDER BY score DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return [{"smiles": r[0], "score": r[1], "worker_id": r[2]} for r in rows]

if __name__ == "__main__":
    print("STARTING NEURAL-NOVA GRID BRAIN ON PORT 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
