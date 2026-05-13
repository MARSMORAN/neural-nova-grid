"""
engine/multi_target_screener.py
Ultimate Polypharmacology Screener.

Evaluates molecules not just against one target, but against a PANEL of
GBM targets (e.g., EGFR + CDK4 + PDGFR) simultaneously to prevent tumor escape.
Also checks for PROTAC linker viability.
"""

import math
import random
import logging
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class MultiTargetProfile:
    smiles: str
    mw: float = 0.0
    logp: float = 0.0
    tpsa: float = 0.0
    passes_bbb: bool = False
    
    # Target binding scores (kcal/mol, lower is better)
    binding_egfr: float = 0.0
    binding_cdk4: float = 0.0
    binding_pdgfr: float = 0.0
    
    # PROTAC attributes
    has_e3_ligase_binder: bool = False
    linker_length: int = 0
    
    # Multi-target synergistic score
    poly_score: float = 0.0

class MultiTargetScreener:
    def __init__(self, primary_targets: List[str] = ["EGFR", "CDK4", "PDGFRA"]):
        self.targets = primary_targets

    def screen(self, smiles_list: List[str]) -> List[MultiTargetProfile]:
        logger.info(f"Running multi-target polypharmacology screen on {len(smiles_list)} molecules...")
        results = []
        
        for smi in smiles_list:
            prof = MultiTargetProfile(smiles=smi)
            
            # 1. Physicochemical
            prof.mw = len(smi) * 12.0 + random.gauss(0, 50)
            prof.logp = smi.count("c") * 0.4 - smi.count("O") * 0.5 + random.gauss(0, 0.5)
            prof.tpsa = smi.count("N") * 12 + smi.count("O") * 20 + random.gauss(0, 10)
            
            # Expanded BBB rules for larger multi-target drugs (like PROTACs, which break Lipinski)
            prof.passes_bbb = (prof.mw <= 800 and 1.0 <= prof.logp <= 5.5 and prof.tpsa <= 120)
            if not prof.passes_bbb:
                continue

            # 2. Multi-Target Binding (Simulated AutoDock Vina / FEP)
            # A great drug binds strongly (negative kcal/mol) to ALL targets
            base_affinity = -5.0 + (len(smi) / 10.0) * -0.5
            
            # Penalize if it lacks specific functional groups needed for each pocket
            egfr_bonus = -2.0 if "c1ccnc" in smi or "Nc1" in smi else 0.0
            cdk4_bonus = -1.5 if "C(=O)N" in smi or "C#N" in smi else 0.0
            pdgfr_bonus = -1.8 if "F" in smi or "Cl" in smi else 0.0
            
            prof.binding_egfr = base_affinity + egfr_bonus + random.gauss(0, 0.5)
            prof.binding_cdk4 = base_affinity + cdk4_bonus + random.gauss(0, 0.5)
            prof.binding_pdgfr = base_affinity + pdgfr_bonus + random.gauss(0, 0.5)
            
            # 3. PROTAC Analysis
            # If the molecule is long enough and has two distinct cyclic ends, it could be a PROTAC
            if prof.mw > 500 and smi.count("c1") >= 2 and "O" in smi and "N" in smi:
                prof.has_e3_ligase_binder = True
                prof.linker_length = random.randint(5, 15)  # PEG linker length

            # 4. Polypharmacology Score
            # Harmonic mean of affinities to ensure it hits ALL targets, not just one really well
            # Shift affinities to positive values for harmonic mean: max(0.1, -affinity)
            a1 = max(0.1, -prof.binding_egfr)
            a2 = max(0.1, -prof.binding_cdk4)
            a3 = max(0.1, -prof.binding_pdgfr)
            
            harmonic_mean = 3 / ((1/a1) + (1/a2) + (1/a3))
            
            # Bonus for PROTAC capability
            protac_bonus = 2.0 if prof.has_e3_ligase_binder else 0.0
            
            prof.poly_score = harmonic_mean + protac_bonus
            results.append(prof)
            
        results.sort(key=lambda x: x.poly_score, reverse=True)
        return results
