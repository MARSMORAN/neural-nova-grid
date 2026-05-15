"""
engine/bbb_kinetics.py
Apex Mankind v32.0 - BBB/BBTB Kinetic Simulation.
Solves the Renkin-Crone equation for regional brain partitioning.
"""

import math
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class BBBKineticEngine:
    """
    Advanced simulation of Blood-Brain Barrier (BBB) and Blood-Brain Tumor Barrier (BBTB).
    Models the flux between plasma, tumor core, and invading margin.
    """
    
    def simulate_flux(self, mw: float, logp: float, tpsa: float) -> Dict[str, float]:
        """
        Calculates Kp,uu (unbound brain-to-plasma ratio).
        Uses Renkin-Crone approximation: Kp,uu = (1 - exp(-PS/Q))
        """
        # PS (Permeability-Surface area product) proxy
        # Based on physicochemical CNS-MPO drivers
        ps_base = (0.5 * logp) - (0.01 * mw) - (0.03 * tpsa) + 2.5
        ps = math.exp(ps_base)
        
        # Q (Cerebral Blood Flow) ~ 0.5 mL/min/g
        q = 0.5 
        
        # Kp,uu extraction ratio
        kp_uu = 1.0 - math.exp(-ps / q)
        
        # Region-specific partitioning
        # Core has leaky BBTB (higher flux but lower trapping)
        # Margin has intact BBB (strict gatekeeper)
        return {
            "kp_uu_overall": round(max(0.01, min(1.0, kp_uu)), 4),
            "tumor_core_flux": round(kp_uu * 1.5, 4), # Leaky
            "invading_margin_flux": round(kp_uu * 0.8, 4), # Restrictive Front
            "efflux_risk": 1.0 if tpsa > 80 else 0.2
        }
