"""
learner/memory_db.py
Persistent SQLite database for all molecules ever tried, targets explored,
and cycle history. This is the engine's long-term memory.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryDB:
    """Persistent memory for the autonomous discovery loop."""

    def __init__(self, db_path: str = "./logs/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS molecules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                smiles TEXT NOT NULL,
                target TEXT,
                cycle_id INTEGER,
                -- Chemistry
                mw REAL, logp REAL, hbd INTEGER, hba INTEGER, tpsa REAL,
                -- Screening
                passes_bbb INTEGER,
                docking_score REAL,
                composite_score REAL,
                -- ADMET
                bbb_penetration REAL,
                herg_risk REAL,
                metabolic_stability REAL,
                -- GBM Realism
                rmsd_stability REAL,
                persistence REAL,
                homo_lumo_gap REAL,
                electrophilicity REAL,
                ph_adjusted_potency REAL,
                hypoxic_efficacy REAL,
                -- Twin
                twin_efficacy REAL,
                twin_volume_reduction REAL,
                -- Status
                stage_reached TEXT,
                rejection_reason TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(smiles, target)
            );

            CREATE TABLE IF NOT EXISTS targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                gene TEXT NOT NULL UNIQUE,
                target_score REAL,
                role TEXT,
                n_molecules_tried INTEGER DEFAULT 0,
                best_composite_score REAL DEFAULT 0,
                best_smiles TEXT,
                tried_in_trial INTEGER DEFAULT 0,
                current_priority REAL DEFAULT 0.5,
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS cycles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cycle_id INTEGER NOT NULL UNIQUE,
                molecules_generated INTEGER,
                molecules_passed_screen INTEGER,
                molecules_simulated INTEGER,
                best_composite_score REAL,
                best_twin_efficacy REAL,
                best_smiles TEXT,
                target_used TEXT,
                strategy TEXT,
                elapsed_seconds REAL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS failures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                smiles TEXT,
                target TEXT,
                failure_reason TEXT,
                lesson TEXT,
                cycle_id INTEGER,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_mol_smiles ON molecules(smiles);
            CREATE INDEX IF NOT EXISTS idx_mol_target ON molecules(target);
            CREATE INDEX IF NOT EXISTS idx_mol_score ON molecules(composite_score);
            CREATE INDEX IF NOT EXISTS idx_mol_cycle ON molecules(cycle_id);
        """)
        self.conn.commit()

    # ── Molecule operations ───────────────────────────────────

    def save_molecule(self, mol_dict: Dict) -> int:
        """Save a screened molecule to the database."""
        try:
            c = self.conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO molecules (
                    smiles, target, cycle_id,
                    mw, logp, hbd, hba, tpsa,
                    passes_bbb, docking_score, composite_score,
                    bbb_penetration, herg_risk, metabolic_stability,
                    rmsd_stability, persistence, homo_lumo_gap,
                    electrophilicity, ph_adjusted_potency, hypoxic_efficacy,
                    twin_efficacy, twin_volume_reduction,
                    stage_reached, rejection_reason
                ) VALUES (
                    :smiles, :target, :cycle_id,
                    :mw, :logp, :hbd, :hba, :tpsa,
                    :passes_bbb, :docking_score, :composite_score,
                    :bbb_penetration, :herg_risk, :metabolic_stability,
                    :rmsd_stability, :persistence, :homo_lumo_gap,
                    :electrophilicity, :ph_adjusted_potency, :hypoxic_efficacy,
                    :twin_efficacy, :twin_volume_reduction,
                    :stage_reached, :rejection_reason
                )
            """, mol_dict)
            self.conn.commit()
            return c.lastrowid
        except sqlite3.Error as e:
            logger.warning(f"Failed to save molecule: {e}")
            return -1

    def save_molecules_batch(self, mol_dicts: List[Dict]):
        """Batch save molecules."""
        for md in mol_dicts:
            self.save_molecule(md)

    def get_top_molecules(self, n: int = 50, target: str = None) -> List[Dict]:
        """Get the top-scoring molecules ever generated."""
        c = self.conn.cursor()
        if target:
            c.execute("""
                SELECT * FROM molecules
                WHERE target = ? AND composite_score > 0
                ORDER BY composite_score DESC LIMIT ?
            """, (target, n))
        else:
            c.execute("""
                SELECT * FROM molecules
                WHERE composite_score > 0
                ORDER BY composite_score DESC LIMIT ?
            """, (n,))
        return [dict(row) for row in c.fetchall()]

    def was_tried(self, smiles: str) -> bool:
        """Check if a SMILES was already tried."""
        c = self.conn.cursor()
        c.execute("SELECT 1 FROM molecules WHERE smiles = ? LIMIT 1", (smiles,))
        return c.fetchone() is not None

    def total_molecules(self) -> int:
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM molecules")
        return c.fetchone()[0]

    # ── Target operations ─────────────────────────────────────

    def save_target(self, target_dict: Dict):
        try:
            c = self.conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO targets (
                    gene, target_score, role, n_molecules_tried,
                    best_composite_score, best_smiles,
                    tried_in_trial, current_priority
                ) VALUES (
                    :gene, :target_score, :role, :n_molecules_tried,
                    :best_composite_score, :best_smiles,
                    :tried_in_trial, :current_priority
                )
            """, target_dict)
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Failed to save target: {e}")

    def get_targets_by_priority(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM targets ORDER BY current_priority DESC")
        return [dict(row) for row in c.fetchall()]

    # ── Cycle operations ──────────────────────────────────────

    def save_cycle(self, cycle_dict: Dict):
        try:
            c = self.conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO cycles (
                    cycle_id, molecules_generated, molecules_passed_screen,
                    molecules_simulated, best_composite_score,
                    best_twin_efficacy, best_smiles, target_used,
                    strategy, elapsed_seconds
                ) VALUES (
                    :cycle_id, :molecules_generated, :molecules_passed_screen,
                    :molecules_simulated, :best_composite_score,
                    :best_twin_efficacy, :best_smiles, :target_used,
                    :strategy, :elapsed_seconds
                )
            """, cycle_dict)
            self.conn.commit()
        except sqlite3.Error as e:
            logger.warning(f"Failed to save cycle: {e}")

    def get_cycle_history(self) -> List[Dict]:
        c = self.conn.cursor()
        c.execute("SELECT * FROM cycles ORDER BY cycle_id ASC")
        return [dict(row) for row in c.fetchall()]

    # ── Failure log ───────────────────────────────────────────

    def log_failure(self, smiles: str, target: str, reason: str,
                    lesson: str, cycle_id: int):
        try:
            c = self.conn.cursor()
            c.execute("""
                INSERT INTO failures (smiles, target, failure_reason, lesson, cycle_id)
                VALUES (?, ?, ?, ?, ?)
            """, (smiles, target, reason, lesson, cycle_id))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.debug(f"Failed to log failure: {e}")

    def get_failure_patterns(self) -> Dict[str, int]:
        """Count failure reasons to learn what to avoid."""
        c = self.conn.cursor()
        c.execute("""
            SELECT failure_reason, COUNT(*) as cnt
            FROM failures
            GROUP BY failure_reason
            ORDER BY cnt DESC
        """)
        return {row["failure_reason"]: row["cnt"] for row in c.fetchall()}

    # ── Statistics ────────────────────────────────────────────

    def stats(self) -> Dict:
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM molecules")
        total_mol = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM cycles")
        total_cyc = c.fetchone()[0]
        c.execute("SELECT MAX(composite_score) FROM molecules")
        best_row = c.fetchone()
        best_score = best_row[0] if best_row and best_row[0] else 0
        c.execute("SELECT COUNT(DISTINCT target) FROM molecules")
        targets_explored = c.fetchone()[0]

        return {
            "total_molecules_tried": total_mol,
            "total_cycles": total_cyc,
            "best_composite_score": best_score,
            "targets_explored": targets_explored,
        }

    def close(self):
        self.conn.close()
