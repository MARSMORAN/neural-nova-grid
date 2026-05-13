"""
learner/cycle_manager.py
Autonomous Discovery Loop — the brain of Neural-Nova v2.

Orchestrates: Data Harvest → Target ID → Generate → Screen → Report → Learn → Repeat
"""

import sys
import io
import os
import time
import logging
import random
import numpy as np
from typing import List, Dict, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich import box

from harvester.tcga_client import TCGAClient
from harvester.pdb_client import PDBClient
from harvester.chembl_client import ChEMBLClient
from harvester.pubmed_miner import PubMedMiner
from harvester.clintrials_client import ClinicalTrialsClient
from engine.target_identifier import TargetIdentifier
from engine.molecule_generator import MoleculeGenerator
from engine.virtual_screener import VirtualScreener, MoleculeProfile
from engine.report_generator import ReportGenerator
from learner.memory_db import MemoryDB

logger = logging.getLogger(__name__)
console = Console()

# ── Configuration ────────────────────────────────────────────

MAX_CYCLES = 50
MOLECULES_PER_CYCLE = 200
TOP_K_SCREEN = 30
TOP_K_REPORT = 5
RETRAIN_EVERY = 3
CONVERGENCE_PATIENCE = 15
CONVERGENCE_DELTA = 0.005


# ── Autonomous Discovery Loop ───────────────────────────────

class DiscoveryEngine:
    """
    The autonomous GBM drug discovery engine.
    Runs in a continuous loop: generate → screen → learn → repeat.
    """

    def __init__(self):
        console.print(Panel.fit(
            "[bold cyan]NEURAL-NOVA v2[/bold cyan]\n"
            "[dim]Autonomous GBM Drug Discovery Engine[/dim]\n"
            "[dim]Real data. Real chemistry. Self-improving.[/dim]",
            border_style="bright_blue", box=box.DOUBLE_EDGE
        ))

        # Initialize all subsystems
        console.print("\n[dim]Initializing subsystems...[/dim]")
        self.tcga = TCGAClient()
        self.pdb = PDBClient()
        self.chembl = ChEMBLClient()
        self.pubmed = PubMedMiner()
        self.clintrials = ClinicalTrialsClient()
        self.reporter = ReportGenerator()
        self.memory = MemoryDB()

        # These get initialized during data harvest
        self.target_id: Optional[TargetIdentifier] = None
        self.generator: Optional[MoleculeGenerator] = None
        self.screener: Optional[VirtualScreener] = None
        self.targets: List[Dict] = []

        # Tracking
        self.best_score = 0.0
        self.no_improve = 0
        self.score_history: List[float] = []

    # ── Phase 1: Data Harvest ─────────────────────────────────

    def harvest_data(self):
        """Pull all available real data from public APIs."""
        console.rule("[bold yellow]PHASE 1: DATA HARVEST[/bold yellow]")

        with Progress(SpinnerColumn(), TextColumn("{task.description}"),
                       console=console, transient=True) as progress:
            task = progress.add_task("Harvesting...", total=None)

            # TCGA genomics
            progress.update(task, description="[cyan]Pulling TCGA-GBM patient data...")
            clinical = self.tcga.fetch_clinical()
            mutations = self.tcga.fetch_mutations()
            drivers = self.tcga.get_gbm_driver_genes()

            # PDB structures
            progress.update(task, description="[cyan]Downloading protein structures...")
            self.pdb.download_all_targets()

            # Clinical trial failures
            progress.update(task, description="[cyan]Fetching clinical trial data...")
            trials = self.clintrials.fetch_gbm_trials(max_studies=300)
            failures = self.clintrials.analyze_failures(trials)

            # PubMed literature
            progress.update(task, description="[cyan]Mining PubMed research papers...")
            papers = self.pubmed.mine_all(max_per_query=30)

            # ChEMBL known actives (for similarity scoring)
            progress.update(task, description="[cyan]Pulling known bioactive compounds...")
            known_actives = []
            try:
                chembl_data = self.chembl.fetch_all_targets(max_per_target=200)
                known_actives = chembl_data["canonical_smiles"].dropna().tolist()[:500]
            except Exception as e:
                logger.warning(f"ChEMBL fetch failed: {e}")

        # Initialize engine components with real data
        self.target_id = TargetIdentifier(drivers)
        mutation_analysis = self.target_id.analyze_mutations(mutations)
        self.targets = self.target_id.get_top_targets(
            mutation_analysis, failures, top_k=8
        )

        # Initialize generator with ChEMBL actives as seed data
        seed_smiles = known_actives[:50] if known_actives else None
        self.generator = MoleculeGenerator(seed_smiles=seed_smiles)

        # Initialize screener with known actives for similarity comparison
        self.screener = VirtualScreener(known_actives_smiles=known_actives[:100])

        # Print harvest summary
        self._print_harvest_summary(clinical, mutations, trials, papers, known_actives)

        # Save targets to memory
        for t in self.targets:
            self.memory.save_target({
                "gene": t["gene"],
                "target_score": t["target_score"],
                "role": t.get("role", "unknown"),
                "n_molecules_tried": 0,
                "best_composite_score": 0,
                "best_smiles": "",
                "tried_in_trial": int(t.get("tried_in_trial", False)),
                "current_priority": t["target_score"],
            })

    def _print_harvest_summary(self, clinical, mutations, trials, papers, actives):
        t = Table(title="Data Harvest Complete", box=box.ROUNDED,
                  title_style="bold bright_green")
        t.add_column("Source", style="bright_yellow")
        t.add_column("Records", style="bright_green", justify="right")
        t.add_row("TCGA-GBM Patients", str(len(clinical)))
        t.add_row("Somatic Mutations", str(len(mutations)))
        t.add_row("PDB Structures", str(len(list(Path("./data/pdb_structures").glob("*.pdb")))))
        t.add_row("Clinical Trials", str(len(trials)))
        t.add_row("PubMed Papers", str(len(papers)))
        t.add_row("ChEMBL Active Compounds", str(len(actives)))
        console.print(t)

        # Print identified targets
        tt = Table(title="Identified Druggable GBM Targets", box=box.ROUNDED,
                   title_style="bold bright_cyan")
        tt.add_column("#", style="dim", width=3)
        tt.add_column("Gene", style="bright_yellow")
        tt.add_column("Score", style="bright_green", justify="right")
        tt.add_column("Role", style="dim")
        tt.add_column("Source", style="dim")
        for i, targ in enumerate(self.targets[:8], 1):
            tt.add_row(
                str(i), targ["gene"],
                f"{targ['target_score']:.3f}",
                targ.get("role", "?"),
                targ.get("source", "?")[:20],
            )
        console.print(tt)

    # ── Phase 2: Discovery Cycle ──────────────────────────────

    def run_cycle(self, cycle_id: int) -> float:
        """Run a single discovery cycle. Returns best composite score."""
        t0 = time.time()

        # Pick target (priority-weighted random selection)
        target = self._select_target()
        console.print(f"\n  [bright_yellow]Target:[/bright_yellow] {target['gene']}  "
                       f"(score={target['target_score']:.3f})")

        # Generate molecules
        console.print(f"  [dim]Generating {MOLECULES_PER_CYCLE} candidate molecules...[/dim]")
        smiles_list = self.generator.generate(n=MOLECULES_PER_CYCLE)
        console.print(f"  [dim]Generated {len(smiles_list)} unique SMILES[/dim]")

        # Screen
        console.print(f"  [dim]Screening against {target['gene']}...[/dim]")
        screened = self.screener.screen(
            smiles_list, target=target["gene"], top_k=TOP_K_SCREEN
        )
        console.print(f"  [dim]Passed screening: {len(screened)} molecules[/dim]")

        # Save all results to memory
        for mol in screened:
            self.memory.save_molecule({
                "smiles": mol.smiles,
                "target": mol.target,
                "cycle_id": cycle_id,
                "mw": mol.mw, "logp": mol.logp,
                "hbd": mol.hbd, "hba": mol.hba, "tpsa": mol.tpsa,
                "passes_bbb": int(mol.passes_bbb),
                "docking_score": mol.docking_score,
                "composite_score": mol.composite_score,
                "bbb_penetration": mol.bbb_penetration,
                "herg_risk": mol.herg_risk,
                "metabolic_stability": mol.metabolic_stability,
                "twin_efficacy": 0.0,
                "twin_volume_reduction": 0.0,
                "stage_reached": mol.stage_reached,
                "rejection_reason": mol.rejection_reason,
            })

        # Generate reports for top candidates
        top_candidates = screened[:TOP_K_REPORT]
        report_paths = []
        for cand in top_candidates:
            cand_dict = {
                "smiles": cand.smiles, "target": cand.target,
                "mw": cand.mw, "logp": cand.logp,
                "hbd": cand.hbd, "hba": cand.hba, "tpsa": cand.tpsa,
                "passes_lipinski": cand.passes_lipinski,
                "passes_bbb": cand.passes_bbb,
                "is_pains": cand.is_pains,
                "docking_score": cand.docking_score,
                "similarity_to_known": cand.similarity_to_known,
                "composite_score": cand.composite_score,
                "bbb_penetration": cand.bbb_penetration,
                "oral_bioavailability": cand.oral_bioavailability,
                "metabolic_stability": cand.metabolic_stability,
                "herg_risk": cand.herg_risk,
            }
            path = self.reporter.generate_candidate_report(cand_dict, cycle_id)
            report_paths.append(path)

        # Cycle stats
        best_score = screened[0].composite_score if screened else 0.0
        elapsed = time.time() - t0

        cycle_stats = {
            "cycle_id": cycle_id,
            "molecules_generated": len(smiles_list),
            "molecules_passed_screen": len(screened),
            "molecules_simulated": 0,  # future: twin integration
            "best_composite_score": best_score,
            "best_twin_efficacy": 0.0,
            "best_smiles": screened[0].smiles if screened else "",
            "target_used": target["gene"],
            "strategy": "hybrid",
            "elapsed_seconds": elapsed,
            "reports_generated": len(report_paths),
        }
        self.memory.save_cycle(cycle_stats)
        self.reporter.generate_cycle_summary(cycle_id, cycle_stats,
                                              [{"smiles": s.smiles,
                                                "composite_score": s.composite_score,
                                                "bbb_penetration": s.bbb_penetration}
                                               for s in screened[:10]])

        # Print cycle results
        self._print_cycle_results(cycle_id, cycle_stats, screened[:5], elapsed)

        return best_score

    def _select_target(self) -> Dict:
        """Select target with probability proportional to priority score."""
        if not self.targets:
            return {"gene": "EGFR", "target_score": 0.5}
        scores = np.array([t["target_score"] for t in self.targets])
        scores = scores / scores.sum()
        idx = np.random.choice(len(self.targets), p=scores)
        return self.targets[idx]

    def _print_cycle_results(self, cycle_id, stats, top_mols, elapsed):
        t = Table(title=f"Cycle {cycle_id} Results", box=box.ROUNDED,
                  title_style="bold bright_green")
        t.add_column("SMILES", style="dim", max_width=35)
        t.add_column("Score", style="bright_green", justify="right")
        t.add_column("Dock", style="cyan", justify="right")
        t.add_column("BBB", style="magenta", justify="right")
        t.add_column("hERG", style="bright_red", justify="right")
        for mol in top_mols:
            t.add_row(
                mol.smiles[:33] + "...",
                f"{mol.composite_score:.4f}",
                f"{mol.docking_score:.2f}",
                f"{mol.bbb_penetration:.3f}",
                f"{mol.herg_risk:.3f}",
            )
        console.print(t)
        console.print(f"  [dim]Elapsed: {elapsed:.1f}s  |  "
                       f"Generated: {stats['molecules_generated']}  |  "
                       f"Passed: {stats['molecules_passed_screen']}  |  "
                       f"Reports: {stats['reports_generated']}[/dim]")

    # ── Phase 3: Self-Improvement ─────────────────────────────

    def learn_and_adapt(self, cycle_id: int):
        """
        Retrain the generator on winning molecules.
        Adjust target priorities based on what's working.
        """
        if cycle_id > 0 and cycle_id % RETRAIN_EVERY == 0:
            console.print(f"\n  [bright_yellow]Retraining generator "
                           f"on top molecules...[/bright_yellow]")

            # Get top molecules from memory
            top_mols = self.memory.get_top_molecules(n=50)
            good_smiles = [m["smiles"] for m in top_mols if m.get("smiles")]

            if len(good_smiles) >= 5:
                self.generator.retrain(good_smiles)
                console.print(f"  [dim]Retrained on {len(good_smiles)} "
                               f"winning molecules[/dim]")

            # Update target priorities
            for target in self.targets:
                gene = target["gene"]
                target_mols = self.memory.get_top_molecules(n=10, target=gene)
                if target_mols:
                    avg_score = np.mean([m["composite_score"] for m in target_mols])
                    # Boost targets that are producing good hits
                    target["target_score"] = float(
                        0.6 * target["target_score"] + 0.4 * avg_score
                    )

    # ── Main loop ─────────────────────────────────────────────

    def run(self, max_cycles: int = MAX_CYCLES):
        """Run the full autonomous discovery loop."""

        # Phase 1: Harvest data
        self.harvest_data()

        # Phase 2-3: Discovery loop
        console.print()
        console.rule("[bold yellow]PHASE 2-3: AUTONOMOUS DISCOVERY LOOP[/bold yellow]")

        for cycle_id in range(max_cycles):
            console.rule(
                f"[bold cyan]CYCLE {cycle_id + 1} / {max_cycles}[/bold cyan]"
            )

            # Run discovery cycle
            best_score = self.run_cycle(cycle_id)
            self.score_history.append(best_score)

            # Learn and adapt
            self.learn_and_adapt(cycle_id)

            # Convergence check
            if best_score > self.best_score + CONVERGENCE_DELTA:
                self.best_score = best_score
                self.no_improve = 0
            else:
                self.no_improve += 1

            if self.no_improve >= CONVERGENCE_PATIENCE:
                console.print(Panel(
                    f"[bold green]CONVERGENCE[/bold green] after cycle {cycle_id + 1}\n"
                    f"Best score: {self.best_score:.4f}",
                    border_style="green"
                ))
                break

        # Final report
        self._final_report()

    def _final_report(self):
        console.print()
        console.rule("[bold bright_cyan]FINAL DISCOVERY REPORT[/bold bright_cyan]")

        stats = self.memory.stats()
        top_all = self.memory.get_top_molecules(n=10)

        console.print(Panel(
            f"[bold]Total Molecules Evaluated:[/bold] {stats['total_molecules_tried']}\n"
            f"[bold]Total Cycles Completed:[/bold]    {stats['total_cycles']}\n"
            f"[bold]Targets Explored:[/bold]          {stats['targets_explored']}\n"
            f"[bold]Best Composite Score:[/bold]       "
            f"[bright_green]{stats['best_composite_score']:.4f}[/bright_green]",
            title="[bold cyan]ENGINE STATISTICS[/bold cyan]",
            border_style="bright_cyan"
        ))

        if top_all:
            t = Table(title="ALL-TIME TOP DRUG CANDIDATES", box=box.DOUBLE_EDGE,
                      title_style="bold bright_green")
            t.add_column("#", style="dim", width=3)
            t.add_column("SMILES", style="bright_yellow", max_width=35)
            t.add_column("Target", style="cyan")
            t.add_column("Score", style="bright_green", justify="right")
            t.add_column("BBB", style="magenta", justify="right")
            t.add_column("Dock", style="dim", justify="right")
            t.add_column("hERG", style="bright_red", justify="right")
            for i, mol in enumerate(top_all, 1):
                t.add_row(
                    str(i),
                    (mol["smiles"][:33] + "...") if len(mol.get("smiles","")) > 33 else mol.get("smiles",""),
                    mol.get("target", "?"),
                    f"{mol.get('composite_score', 0):.4f}",
                    f"{mol.get('bbb_penetration', 0):.3f}",
                    f"{mol.get('docking_score', 0):.2f}",
                    f"{mol.get('herg_risk', 0):.3f}",
                )
            console.print(t)

        # Score history visualization
        if len(self.score_history) > 1:
            console.print("\n[bold]Score progression:[/bold]")
            for i, score in enumerate(self.score_history):
                bar_len = int(score * 50)
                bar = "+" * bar_len + " " * (50 - bar_len)
                console.print(f"  Cycle {i+1:3d}  [{bar}]  {score:.4f}")

        console.print(f"\n[dim]Reports saved to: ./reports/[/dim]")
        console.print(f"[dim]Database: ./logs/memory.db[/dim]")
        console.print(f"[dim]Total reports generated: "
                       f"{len(list(Path('./reports').rglob('*.txt')))} text + "
                       f"{len(list(Path('./reports').rglob('*.pdf')))} PDF[/dim]")

        self.memory.close()


# ── Entry point ──────────────────────────────────────────────

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    engine = DiscoveryEngine()
    engine.run(max_cycles=MAX_CYCLES)


if __name__ == "__main__":
    main()
