"""
engine/repurposer.py
Drug Repurposing Engine for Neural-Nova v2.

Instead of generating unproven molecules, this module pulls thousands of 
FDA-approved (Phase 4) drugs from ChEMBL and screens them against our 
TCGA-identified GBM targets. 

If we find a hit here, it can theoretically be prescribed off-label immediately.
"""

import time
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"

class RepurposingEngine:
    def __init__(self, cache_dir: str = "./data/approved_drugs"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def fetch_approved_drugs(self) -> pd.DataFrame:
        """
        Pull all Phase 4 (FDA Approved) drugs from ChEMBL that have a defined 
        SMILES structure (small molecules).
        """
        cache_file = self.cache_dir / "fda_approved_drugs.parquet"
        if cache_file.exists():
            logger.info(f"Loading cached FDA-approved drugs from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info("Fetching FDA-approved (Phase 4) drugs from ChEMBL...")
        
        all_drugs = []
        offset = 0
        limit = 1000

        while True:
            params = {
                "max_phase": 4,           # 4 = Approved drug
                "molecule_type": "Small molecule",
                "limit": limit,
                "offset": offset,
                "format": "json"
            }
            try:
                resp = self.session.get(f"{CHEMBL_API}/molecule", params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                molecules = data.get("molecules", [])
                
                if not molecules:
                    break
                    
                for mol in molecules:
                    structures = mol.get("molecule_structures") or {}
                    smiles = structures.get("canonical_smiles")
                    if smiles:
                        all_drugs.append({
                            "chembl_id": mol.get("molecule_chembl_id"),
                            "pref_name": mol.get("pref_name", "Unknown Name"),
                            "smiles": smiles,
                            "indication_class": mol.get("indication_class", "Unknown"),
                            "max_phase": mol.get("max_phase")
                        })
                
                offset += limit
                logger.info(f"  Fetched {len(all_drugs)} approved drugs...")
                time.sleep(0.5)
                
            except requests.RequestException as e:
                logger.warning(f"ChEMBL request failed: {e}")
                time.sleep(3)
                continue

        df = pd.DataFrame(all_drugs).drop_duplicates(subset=["smiles"])
        df.to_parquet(cache_file, index=False)
        logger.info(f"Saved {len(df)} unique FDA-approved small molecules.")
        return df

    def match_candidates(self, screened_profiles: List[Dict], drug_df: pd.DataFrame) -> List[Dict]:
        """
        Match the screened SMILES profiles back to their real FDA drug names.
        """
        drug_map = dict(zip(drug_df.smiles, drug_df.pref_name))
        
        for profile in screened_profiles:
            smiles = profile.get("smiles")
            profile["drug_name"] = drug_map.get(smiles, "Unknown Drug")
            profile["is_repurposed"] = True
            
        return screened_profiles
