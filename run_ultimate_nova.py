"""
run_ultimate_nova.py
Neural-Nova v3 Protocol: Limitless.

1. Uses Generative AI (LSTM fallback to simulate 3D diffusion) to build large, complex molecules.
2. Uses Multi-Target Polypharmacology screening (EGFR + CDK4 + PDGFR).
3. Evaluates PROTAC (Protein-Targeting Chimera) viability.
4. Designs customized Nano-lipidic delivery vehicles for the top candidates to crush the BBB.
"""

import sys
import io
import time
import logging

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from engine.molecule_generator import MoleculeGenerator
from engine.multi_target_screener import MultiTargetScreener
from engine.nanoparticle_designer import NanoparticleDesigner

console = Console()
logging.basicConfig(level=logging.WARNING)

def main():
    console.print(Panel.fit(
        "[bold magenta]NEURAL-NOVA V3: LIMITLESS PROTOCOL[/bold magenta]\n"
        "[dim]Multi-Target Polypharmacology | PROTAC Engineering | Nanoparticle Delivery[/dim]",
        border_style="magenta", box=box.DOUBLE_EDGE
    ))
    
    t0 = time.time()
    
    # 1. 3D Generative Simulation
    console.print("\n[cyan]1. Initializing Generative Chemistry Engine...[/cyan]")
    generator = MoleculeGenerator()
    console.print("  [dim]Generating complex molecular scaffolds (simulating 3D DiffDock)...[/dim]")
    # We ask for a massive amount to ensure we get a few complex ones
    smiles_list = generator.generate(n=2000)
    console.print(f"  [bold]Generated:[/bold] {len(smiles_list)} novel structures.")

    # 2. Multi-Target Screening
    console.print("\n[cyan]2. Running Polypharmacology & PROTAC Screen...[/cyan]")
    targets = ["EGFR", "CDK4", "PDGFRA"]
    console.print(f"  [bold]Simultaneous Targets:[/bold] {', '.join(targets)}")
    
    screener = MultiTargetScreener(primary_targets=targets)
    candidates = screener.screen(smiles_list)
    
    top_candidates = candidates[:5]

    # 3. Nanoparticle Design
    console.print("\n[cyan]3. Designing Nanoscale Delivery Vehicles...[/cyan]")
    nano_designer = NanoparticleDesigner()
    
    final_dossiers = []
    for cand in top_candidates:
        nano = nano_designer.design_delivery_vehicle(cand.smiles, cand.mw)
        final_dossiers.append({
            "molecule": cand,
            "nanoparticle": nano
        })

    # 4. Results
    console.print("\n[cyan]4. Finalizing Ultimate Dossiers...[/cyan]")
    
    t = Table(title="TOP POLYPHARMACOLOGY + NANO-DELIVERY CANDIDATES", box=box.DOUBLE_EDGE, title_style="bold bright_green")
    t.add_column("SMILES Structure", style="bright_yellow", max_width=40)
    t.add_column("Poly-Score", style="bright_green", justify="right")
    t.add_column("PROTAC?", style="magenta")
    t.add_column("EGFR / CDK4 / PDGFR (kcal/mol)", style="cyan")
    t.add_column("Nanoparticle Vector", style="dim")
    
    for dos in final_dossiers:
        mol = dos["molecule"]
        nano = dos["nanoparticle"]
        
        protac_str = f"[bold green]YES[/bold green] (Linker: {mol.linker_length})" if mol.has_e3_ligase_binder else "[dim]No[/dim]"
        affinities = f"{mol.binding_egfr:.1f} / {mol.binding_cdk4:.1f} / {mol.binding_pdgfr:.1f}"
        nano_str = f"{nano['vehicle_type']} ({nano['size_nm']}nm)"
        
        t.add_row(
            mol.smiles[:38] + ".." if len(mol.smiles) > 40 else mol.smiles,
            f"{mol.poly_score:.2f}",
            protac_str,
            affinities,
            nano_str
        )

    console.print(t)
    
    # Detailed Nano breakdown for the absolute best
    best = final_dossiers[0]
    console.print("\n[bold]Optimal Delivery Architecture (Top Candidate):[/bold]")
    console.print(f"  [dim]Vector:[/dim] {best['nanoparticle']['vehicle_type']}")
    console.print(f"  [dim]Size/Zeta:[/dim] {best['nanoparticle']['size_nm']}nm / {best['nanoparticle']['zeta_potential_mV']}mV")
    for mod in best['nanoparticle']['surface_modifications']:
        console.print(f"  [dim]Surface Peptide:[/dim] [cyan]{mod['peptide']}[/cyan] -> {mod['mechanism']}")
    console.print(f"  [dim]Result:[/dim] Expected [bold green]{best['nanoparticle']['bbb_penetration_multiplier']}x increase[/bold green] in Blood-Brain Barrier penetrance vs naked drug.")

    elapsed = time.time() - t0
    console.print(f"\n[bold green]LIMITLESS PROTOCOL COMPLETE[/bold green] in {elapsed:.1f} seconds.")

if __name__ == "__main__":
    main()
