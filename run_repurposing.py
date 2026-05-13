"""
run_repurposing.py
Fast-Track Drug Repurposing Pipeline.
Screens 100% FDA-approved drugs against TCGA-identified GBM targets.
"""

import sys
import io
import time
import logging
from pathlib import Path

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from engine.repurposer import RepurposingEngine
from engine.virtual_screener import VirtualScreener
from engine.report_generator import ReportGenerator
from harvester.tcga_client import TCGAClient
from engine.target_identifier import TargetIdentifier

console = Console()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def main():
    console.print(Panel.fit(
        "[bold red]NEURAL-NOVA REPURPOSING PROTOCOL[/bold red]\n"
        "[dim]Bypassing de novo generation.\nScreening 100% FDA-Approved Small Molecules.[/dim]",
        border_style="red", box=box.DOUBLE_EDGE
    ))
    
    t0 = time.time()
    
    # 1. Get Targets
    console.print("\n[cyan]1. Extracting Targets from TCGA-GBM...[/cyan]")
    tcga = TCGAClient()
    mutations = tcga.fetch_mutations()
    drivers = tcga.get_gbm_driver_genes()
    target_id = TargetIdentifier(drivers)
    analysis = target_id.analyze_mutations(mutations)
    targets = target_id.get_top_targets(analysis, top_k=3)
    
    top_target = targets[0]["gene"]
    console.print(f"  [bold]Primary Target Selected:[/bold] {top_target} (Score: {targets[0]['target_score']:.3f})")

    # 2. Fetch FDA Approved Drugs
    console.print("\n[cyan]2. Fetching FDA-Approved Small Molecules...[/cyan]")
    repurposer = RepurposingEngine()
    drug_df = repurposer.fetch_approved_drugs()
    
    if drug_df.empty:
        console.print("[bold red]Failed to fetch drugs. Exiting.[/bold red]")
        return
        
    smiles_list = drug_df["smiles"].tolist()
    console.print(f"  [bold]Library Size:[/bold] {len(smiles_list)} approved drugs ready for screening.")

    # 3. Mass Screening
    console.print(f"\n[cyan]3. Mass GPU-Accelerated Screening against {top_target}...[/cyan]")
    screener = VirtualScreener()
    
    # Screen all drugs
    # To keep this fast for demonstration, we screen the entire list
    # and keep the top 20 candidates
    top_k = 20
    screened_profiles = screener.screen(smiles_list, target=top_target, top_k=top_k)
    
    # Convert profiles to dicts and map back to real drug names
    profile_dicts = []
    for cand in screened_profiles:
        profile_dicts.append({
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
        })
        
    final_candidates = repurposer.match_candidates(profile_dicts, drug_df)

    # 4. Results & Reporting
    console.print("\n[cyan]4. Generating Actionable Repurposing Dossiers...[/cyan]")
    reporter = ReportGenerator(output_dir="./reports/repurposing")
    
    t = Table(title=f"TOP REPURPOSING CANDIDATES FOR {top_target}", box=box.DOUBLE_EDGE, title_style="bold bright_green")
    t.add_column("FDA Drug Name", style="bright_yellow", max_width=30)
    t.add_column("Indication", style="dim", max_width=30)
    t.add_column("Score", style="bright_green", justify="right")
    t.add_column("BBB%", style="magenta", justify="right")
    t.add_column("Docking", style="cyan", justify="right")

    for i, cand in enumerate(final_candidates[:10]):
        # Get indication class from the dataframe
        drug_name = cand["drug_name"]
        match = drug_df[drug_df["pref_name"] == drug_name]
        indication = str(match["indication_class"].values[0]) if not match.empty else "Unknown"
        
        t.add_row(
            drug_name,
            indication[:28],
            f"{cand['composite_score']:.4f}",
            f"{cand['bbb_penetration']:.3f}",
            f"{cand['docking_score']:.2f}"
        )
        
        # Generate PDF report for top 5
        if i < 5:
            reporter.generate_candidate_report(cand, cycle_id=999)

    console.print(t)
    
    elapsed = time.time() - t0
    console.print(f"\n[bold green]PROTOCOL COMPLETE[/bold green] in {elapsed:.1f} seconds.")
    console.print("[dim]Top 5 actionable PDF dossiers saved to ./reports/repurposing/[/dim]")

if __name__ == "__main__":
    main()
