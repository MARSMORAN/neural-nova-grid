"""
engine/molecular_dynamics.py
Simulated Molecular Dynamics (MD) Engine for Neural-Nova.
Approximates binding stability via RMSD and RMSF proxies.
"""

import numpy as np
import random
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class MolecularDynamicsEngine:
    """
    Simulates binding stability over a 100ns production run.
    Uses heuristic models to approximate RMSD/RMSF based on 
    docking geometry and physicochemical properties.
    """
    
    def simulate_binding_stability(self, smiles: str, docking_score: float, mw: float) -> Dict[str, float]:
        """
        Heuristic MD simulation of a protein-ligand complex.
        Returns:
            rmsd: Root Mean Square Deviation (Lower = more stable)
            rmsf_ligand: Fluctuation of the ligand (Lower = more stable)
            binding_persistence: % of time ligand remains in pocket
        """
        logger.info(f"Running simulated 100ns MD for: {smiles[:20]}...")
        
        # Stability is driven by docking score depth and molecular weight
        # Deep docking scores (-9.0+) usually correlate with better stability
        stability_base = abs(docking_score) / 10.0
        
        # MW penalty: larger molecules are harder to stabilize unless docking is deep
        mw_penalty = max(0, (mw - 400) / 1000.0)
        
        # RMSD calculation (simulated)
        # 1.0 - 2.5 A: Stable
        # 2.5 - 4.5 A: Moderate stability
        # > 5.0 A: Unbinding likely
        rmsd = max(1.0, 5.0 - (stability_base * 4.0) + mw_penalty + random.gauss(0, 0.3))
        
        # RMSF (Fluctuation)
        # Higher fluctuation = less specific binding
        rmsf = max(0.5, rmsd * 0.6 + random.uniform(0, 0.5))
        
        # Persistence (% of simulation ligand spent in pocket)
        persistence = 1.0 / (1.0 + np.exp(2.0 * (rmsd - 4.0)))
        
        return {
            "rmsd_angstrom": round(float(rmsd), 2),
            "rmsf_ligand_angstrom": round(float(rmsf), 2),
            "binding_persistence": round(float(persistence), 2)
        }
