"""
generate_massive_queue.py
Pre-loads the Neural-Nova Grid Brain with a massive payload of candidate molecules.

Uses our local Generator to blast out combinatorial chemistry variations
and saves them directly to the SQLite queue for the global swarm to consume.
"""

import sys
import io
import time
import sqlite3
import random
import logging

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn
from engine.molecule_generator import MoleculeGenerator

console = Console()

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

def massive_seed(target_count: int = 10000):
    console.print(Panel.fit(
        "[bold cyan]GRID PAYLOAD GENERATOR[/bold cyan]\n"
        "[dim]Pre-computing chemical space and pushing to Swarm Database...[/dim]",
        border_style="cyan"
    ))
    
    init_db()
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Check current queue size
    c.execute("SELECT COUNT(*) FROM queue")
    current_size = c.fetchone()[0]
    console.print(f"[*] Current Queue Size: [bold yellow]{current_size}[/bold yellow] molecules")
    
    if current_size >= target_count:
        console.print("[+] Queue is already massive. Exiting.")
        return
        
    to_generate = target_count - current_size
    console.print(f"[*] Booting Generator to create [bold]{to_generate}[/bold] new molecules...")
    
    generator = MoleculeGenerator()
    
    batch_size = 500
    inserted = 0
    
    t0 = time.time()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        console=console,
    ) as progress:
        
        task = progress.add_task("[cyan]Generating payload...", total=to_generate)
        
        while inserted < to_generate:
            # We use the fast enumeration and fragment strategies to rapidly scale up
            smiles_batch = generator.generate(n=batch_size, denovo_frac=0.1, fragment_frac=0.5, enum_frac=0.4)
            
            # Insert into SQLite
            db_batch = [(smi,) for smi in smiles_batch]
            try:
                c.executemany("INSERT OR IGNORE INTO queue (smiles) VALUES (?)", db_batch)
                conn.commit()
            except Exception as e:
                pass
                
            # Check how many were actually new and inserted
            c.execute("SELECT COUNT(*) FROM queue")
            new_size = c.fetchone()[0]
            gained = new_size - current_size
            
            progress.update(task, advance=gained - inserted)
            inserted = gained
            current_size = new_size

    elapsed = time.time() - t0
    console.print(f"\n[bold green]PAYLOAD COMPLETE[/bold green]")
    console.print(f"[+] Loaded {inserted} molecules into the Brain in {elapsed:.1f} seconds.")
    console.print("[+] The Swarm is ready to be unleashed.")
    conn.close()

if __name__ == "__main__":
    # For demonstration, we target 10,000. In reality, you'd set this to 10,000,000
    massive_seed(target_count=10000)
