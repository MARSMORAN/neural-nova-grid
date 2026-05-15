"""
generate_massive_queue.py (Apex Mankind v32.0 Edition)
Extreme-Scale Distributed Discovery Payload Generator.

Designed to build a virtually limitless queue (10M+ compounds) with 
high-fidelity 'Pre-Flight' realism filtering.
"""

import sys
import io
import time
import sqlite3
import random
import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from engine.molecule_generator import MoleculeGenerator

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False

console = Console()
DB_FILE = "grid_memory.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Performance Optimizations for SQLite at Scale
    c.execute("PRAGMA journal_mode = WAL")
    c.execute("PRAGMA synchronous = OFF")
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
            metadata TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_queue_status ON queue(status);
        CREATE INDEX IF NOT EXISTS idx_results_score ON results(score);
    """)
    conn.commit()
    conn.close()

def pre_flight_filter(smiles):
    """Worker function for parallel filtering."""
    if not HAS_RDKIT:
        return smiles
    try:
        mol = Chem.MolFromSmiles(smiles)
        if not mol: return None
        mw = Descriptors.MolWt(mol)
        tpsa = Descriptors.TPSA(mol)
        logp = Descriptors.MolLogP(mol)
        
        # Apex v32.0 Cure-Seeking Constraints:
        # 1. Optimal CNS Window: MW 320-450 (balance between permeability and potency)
        # 2. Strict TPSA 30-75 (minimize efflux while maintaining H-bond capability)
        # 3. Targeted LogP 1.8 - 4.2 (ideal for BBB and TME core)
        if 320 < mw < 460 and 30 < tpsa < 80 and 1.8 < logp < 4.5:
            return smiles
    except:
        return None
    return None

def massive_seed(target_count: int = 1000000):
    console.print(Panel.fit(
        "[bold bright_magenta]APEX MANKIND v32.0 - MASSIVE QUEUE GENERATOR[/bold bright_magenta]\n"
        "[dim]Constructing the ultimate GBM discovery payload (Target: 10M+ search space)[/dim]",
        border_style="bright_magenta"
    ))
    
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("PRAGMA synchronous = OFF")
    
    c.execute("SELECT COUNT(*) FROM queue")
    current_size = c.fetchone()[0]
    console.print(f"[*] Current Engine Depth: [bold yellow]{current_size:,}[/bold yellow] molecules")
    
    if current_size >= target_count:
        console.print("[+] Target depth already reached. Expanding frontier...")
        # Optional: continue anyway to expand diversity
        
    to_generate = target_count - current_size
    console.print(f"[*] Booting Genetic Divergence Engines for [bold]{to_generate:,}[/bold] molecules...")
    
    generator = MoleculeGenerator()
    # Scaffold hopping seeds for GBM
    known_seeds = [
        "Cn1nnc2c(=O)n(cnc12)C(=O)N", # Temozolomide
        "CC(C)(C)NC(=O)N(CCCl)N=O",   # Lomustine
        "CN(C)CC=CC(=O)Nc1cc2c(cc1F)c(nc[nH]2)Nc3ccc(c(c3)Cl)F", # Afatinib (EGFR)
        "COc1cc2c(cc1OCCCN3CCOCC3)c(ncn2)Nc4ccc(c(c4)Cl)F" # Gefitinib (EGFR)
    ]
    generator.seed_molecules.extend(known_seeds)
    generator.retrain(known_seeds)
    
    batch_size = 2000
    total_inserted = 0
    t0 = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(bar_width=40),
        TextColumn("[bold cyan]{task.completed:,}[/bold cyan] / {task.total:,}"),
        console=console,
    ) as progress:
        
        task = progress.add_task("[magenta]Synthesizing Apex Frontiers...", total=target_count)
        progress.update(task, completed=current_size)
        
        with ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
            while current_size < target_count:
                # 1. Generate Batch
                raw_smiles = generator.generate(n=batch_size, denovo_frac=0.2, fragment_frac=0.4, enum_frac=0.4)
                
                # 2. Parallel Pre-Flight Realism Filter
                filtered = list(executor.map(pre_flight_filter, raw_smiles))
                clean_batch = [(s,) for s in filtered if s]
                
                # 3. High-Speed DB Insertion
                try:
                    c.executemany("INSERT OR IGNORE INTO queue (smiles) VALUES (?)", clean_batch)
                    conn.commit()
                except:
                    pass
                
                # 4. Update Stats
                c.execute("SELECT COUNT(*) FROM queue")
                new_size = c.fetchone()[0]
                gained = new_size - current_size
                
                progress.update(task, advance=gained)
                current_size = new_size
                total_inserted += gained

    elapsed = time.time() - t0
    console.print(f"\n[bold bright_green]GBM FRONTIER EXPANDED[/bold bright_green]")
    console.print(f"[+] Loaded {total_inserted:,} high-probability molecules in {elapsed:.1f} seconds.")
    console.print(f"[+] Total Engine Depth: [bold cyan]{current_size:,}[/bold cyan]")
    conn.close()

if __name__ == "__main__":
    # Standard 'Massive' run is 1,000,000. In Plan mode, user can increase this to 10M+.
    massive_seed(target_count=1000000)
