"""
harvester/chembl_client.py
Pull known bioactive compounds against GBM targets from ChEMBL.

ChEMBL contains measured binding affinities (IC50, Ki, Kd) for millions
of compounds against thousands of targets — real experimental data.
"""

import json
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"

# ChEMBL target IDs for GBM-relevant proteins
CHEMBL_TARGETS = {
    "EGFR":    {"chembl_id": "CHEMBL203",  "name": "Epidermal growth factor receptor"},
    "IDH1":    {"chembl_id": "CHEMBL3712", "name": "Isocitrate dehydrogenase 1"},
    "VEGFR2":  {"chembl_id": "CHEMBL1957", "name": "VEGF receptor 2"},
    "PDL1":    {"chembl_id": "CHEMBL5102", "name": "Programmed death-ligand 1"},
    "mTOR":    {"chembl_id": "CHEMBL2842", "name": "Serine/threonine-protein kinase mTOR"},
    "CDK4":    {"chembl_id": "CHEMBL461",  "name": "Cyclin-dependent kinase 4"},
    "BCL2":    {"chembl_id": "CHEMBL4860", "name": "Apoptosis regulator Bcl-2"},
    "MDM2":    {"chembl_id": "CHEMBL4361", "name": "E3 ubiquitin-protein ligase Mdm2"},
    "PIK3CA":  {"chembl_id": "CHEMBL4282", "name": "PI3-kinase p110-alpha subunit"},
    "PDGFRA":  {"chembl_id": "CHEMBL2007", "name": "PDGF receptor alpha"},
}


class ChEMBLClient:
    """Pull known bioactive compounds from ChEMBL database."""

    def __init__(self, cache_dir: str = "./data/chembl"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()

    def fetch_bioactivities(self, target_name: str,
                             max_compounds: int = 2000) -> pd.DataFrame:
        """
        Fetch measured bioactivities for a specific target.
        Returns compounds with IC50/Ki/Kd values.
        """
        target_info = CHEMBL_TARGETS.get(target_name)
        if not target_info:
            logger.warning(f"Unknown target: {target_name}")
            return pd.DataFrame()

        cache_file = self.cache_dir / f"{target_name}_bioactivities.parquet"
        if cache_file.exists():
            logger.info(f"Loading cached bioactivities for {target_name}")
            return pd.read_parquet(cache_file)

        chembl_id = target_info["chembl_id"]
        logger.info(f"Fetching bioactivities for {target_name} ({chembl_id})...")

        url = f"{CHEMBL_API}/activity.json"
        all_records = []
        offset = 0

        while len(all_records) < max_compounds:
            params = {
                "target_chembl_id": chembl_id,
                "standard_type__in": "IC50,Ki,Kd,EC50",
                "limit": min(500, max_compounds - len(all_records)),
                "offset": offset,
            }
            try:
                resp = self.session.get(url, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                activities = data.get("activities", [])
                if not activities:
                    break

                for act in activities:
                    all_records.append({
                        "molecule_chembl_id": act.get("molecule_chembl_id", ""),
                        "canonical_smiles": act.get("canonical_smiles", ""),
                        "standard_type": act.get("standard_type", ""),
                        "standard_value": act.get("standard_value"),
                        "standard_units": act.get("standard_units", ""),
                        "pchembl_value": act.get("pchembl_value"),
                        "assay_type": act.get("assay_type", ""),
                        "target": target_name,
                    })

                offset += len(activities)
                logger.info(f"  {target_name}: fetched {len(all_records)} activities")
                time.sleep(0.5)  # rate limit
            except requests.RequestException as e:
                logger.warning(f"ChEMBL request failed: {e}")
                time.sleep(3)
                continue

        df = pd.DataFrame(all_records)
        # Filter to valid SMILES only
        df = df[df["canonical_smiles"].notna() & (df["canonical_smiles"] != "")]
        if len(df) > 0:
            df.to_parquet(cache_file, index=False)
        logger.info(f"  {target_name}: saved {len(df)} compounds")
        return df

    def fetch_all_targets(self, max_per_target: int = 2000) -> pd.DataFrame:
        """Fetch bioactivities for all GBM targets and combine."""
        all_dfs = []
        for target_name in CHEMBL_TARGETS:
            df = self.fetch_bioactivities(target_name, max_per_target)
            all_dfs.append(df)
            time.sleep(1)

        combined = pd.concat(all_dfs, ignore_index=True)
        # Deduplicate by SMILES
        combined = combined.drop_duplicates(subset=["canonical_smiles", "target"])
        logger.info(f"Total unique compound-target pairs: {len(combined)}")
        return combined

    def get_known_drugs(self) -> List[Dict]:
        """
        Return list of FDA-approved or clinical-stage drugs tried against GBM.
        Manually curated from ClinicalTrials.gov and FDA records.
        """
        return [
            {"name": "Temozolomide", "smiles": "Cn1nnc2c(=O)n(cnc12)C(=O)N",
             "target": "DNA", "status": "approved", "mechanism": "DNA alkylation",
             "result": "Standard of care. 2-3 month survival benefit."},
            {"name": "Bevacizumab", "smiles": None,
             "target": "VEGF-A", "status": "approved", "mechanism": "Anti-angiogenic mAb",
             "result": "No OS benefit. PFS improvement only."},
            {"name": "Erlotinib", "smiles": "COc1cc2ncnc(Nc3ccc(OC)c(c3)OC)c2cc1OCCOCC",
             "target": "EGFR", "status": "failed_phase3", "mechanism": "EGFR TKI",
             "result": "No benefit in unselected GBM."},
            {"name": "Ivosidenib", "smiles": None,
             "target": "IDH1", "status": "approved_other", "mechanism": "IDH1 inhibitor",
             "result": "Approved for AML/cholangiocarcinoma. GBM trials ongoing."},
            {"name": "Palbociclib", "smiles": None,
             "target": "CDK4/6", "status": "failed_phase2", "mechanism": "CDK4/6 inhibitor",
             "result": "Limited BBB penetration. No monotherapy benefit."},
            {"name": "Nivolumab", "smiles": None,
             "target": "PD-1", "status": "failed_phase3", "mechanism": "Checkpoint inhibitor",
             "result": "CheckMate 143: no OS benefit in recurrent GBM."},
            {"name": "Depatuxizumab mafodotin", "smiles": None,
             "target": "EGFR/EGFRvIII", "status": "failed_phase3", "mechanism": "ADC",
             "result": "INTELLANCE-1: no OS benefit. Ocular toxicity issues."},
        ]

    def summarize(self) -> Dict:
        all_data = self.fetch_all_targets(max_per_target=500)
        known = self.get_known_drugs()
        return {
            "total_compounds": len(all_data),
            "targets_covered": all_data["target"].nunique(),
            "per_target": all_data["target"].value_counts().to_dict(),
            "known_drugs_tried": len(known),
            "drugs_that_failed": sum(1 for d in known if "failed" in d["status"]),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    client = ChEMBLClient()
    summary = client.summarize()
    print("\n=== ChEMBL BIOACTIVITY SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
