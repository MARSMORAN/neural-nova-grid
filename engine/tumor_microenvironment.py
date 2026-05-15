"""
engine/tumor_microenvironment.py
Simulates the unique physiological stress of Glioblastoma (GBM).
Models Hypoxia, pH Gradients, and BBB Heterogeneity.
"""

import numpy as np
import random
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class TumorMicroenvironmentSimulator:
    """
    Multi-scale simulation of the GBM Tumor Microenvironment (TME).
    Models physiological stress that impacts drug efficacy.
    """
    
    def simulate_tme_conditions(self, region: str = "core") -> Dict[str, float]:
        """
        Simulates physiological conditions based on tumor region.
        Regions: 'core' (hypoxic/acidic/leaky BBTB), 'margin' (normoxic/physiological pH/intact BBB).
        """
        if region == "core":
            # Core: Highly hypoxic, acidic, leaky barrier
            oxygen_saturation = random.uniform(0.5, 3.0) # mmHg (Hypoxia)
            ph = random.uniform(6.0, 6.7)               # Acidic
            bbb_integrity = random.uniform(0.1, 0.4)    # Leaky (BBTB)
        else:
            # Margin: Normoxic, physiological pH, intact barrier
            oxygen_saturation = random.uniform(30.0, 45.0) # mmHg (Normoxia)
            ph = random.uniform(7.3, 7.4)                  # Physiological
            bbb_integrity = random.uniform(0.8, 1.0)       # Intact
            
        return {
            "oxygen_mmhg": round(oxygen_saturation, 1),
            "ph": round(ph, 2),
            "bbb_integrity_index": round(bbb_integrity, 2),
            "hif1a_activity": round(1.0 if oxygen_saturation < 5.0 else 0.1, 2)
        }
    
    def calculate_ph_adjusted_potency(self, base_potency: float, mol_pka: float, tme_ph: float) -> float:
        """
        Adjusts potency based on pH-dependent ionization (Henderson-Hasselbalch).
        Trapping acidic drugs in acidic TME, or basic drugs excluded.
        """
        # Simplified shift: basic drugs (high pKa) are protonated in acidic TME
        # and may have reduced membrane permeability.
        ph_delta = abs(mol_pka - tme_ph)
        permeability_penalty = 1.0 / (1.0 + np.exp(ph_delta - 2.0))
        
        return base_potency * permeability_penalty
