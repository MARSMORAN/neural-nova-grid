"""
harvester/pdb_client.py
Download real 3D protein structures from RCSB Protein Data Bank.

These are the actual crystal/cryo-EM structures of GBM target proteins
(EGFR, IDH1, VEGFR2, PD-L1, TfR1, etc.) used for molecular docking.
"""

import os
import logging
import requests
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

RCSB_DOWNLOAD = "https://files.rcsb.org/download"
RCSB_API = "https://data.rcsb.org/rest/v1/core/entry"


# All GBM-relevant target proteins with their PDB structures
GBM_TARGETS = {
    "EGFR_wt": {
        "uniprot": "P00533",
        "pdb_ids": ["1NQL", "3POZ", "4HJO"],
        "binding_site": "ATP-binding pocket",
        "relevance": "Amplified in 57% of GBM. RTK signaling.",
    },
    "EGFR_vIII": {
        "uniprot": "P00533",
        "pdb_ids": ["2JIT"],
        "binding_site": "ATP-binding pocket (constitutively active)",
        "relevance": "Deletion variant in 25-30% of GBM. Always ON.",
    },
    "IDH1_R132H": {
        "uniprot": "O75874",
        "pdb_ids": ["3INM", "3MAP", "4KZO"],
        "binding_site": "Isocitrate binding cleft",
        "relevance": "Neomorphic mutation. Produces D-2HG oncometabolite.",
    },
    "MGMT": {
        "uniprot": "P16455",
        "pdb_ids": ["1EH6", "1QNT"],
        "binding_site": "Active site cysteine (C145)",
        "relevance": "Repairs TMZ damage. Methylation = better prognosis.",
    },
    "VEGFR2": {
        "uniprot": "P35968",
        "pdb_ids": ["4AGD", "3VHE", "1Y6A"],
        "binding_site": "Kinase domain ATP pocket",
        "relevance": "Drives tumor angiogenesis. Bevacizumab target.",
    },
    "PDL1": {
        "uniprot": "Q9NZQ7",
        "pdb_ids": ["5C3T", "5JDR", "4ZQK"],
        "binding_site": "PD-1 interaction interface",
        "relevance": "Immune checkpoint. Blocks T-cell attack on tumor.",
    },
    "TfR1": {
        "uniprot": "P02786",
        "pdb_ids": ["1CX8", "3KAS"],
        "binding_site": "Apical domain (transferrin binding)",
        "relevance": "BBB gateway. Target for drug delivery vehicles.",
    },
    "BCL2": {
        "uniprot": "P10415",
        "pdb_ids": ["1G5M", "2XA0", "4LVT"],
        "binding_site": "BH3-binding groove",
        "relevance": "Anti-apoptotic. Keeps tumor cells alive.",
    },
    "mTOR": {
        "uniprot": "P42345",
        "pdb_ids": ["4DRH", "4JSP"],
        "binding_site": "Kinase domain (rapamycin-FKBP12 site)",
        "relevance": "Master growth regulator. PI3K/AKT/mTOR pathway.",
    },
    "CDK4": {
        "uniprot": "P11802",
        "pdb_ids": ["2W96", "3G33"],
        "binding_site": "ATP-binding pocket",
        "relevance": "Cell cycle driver. Amplified in 14% of GBM.",
    },
    "MDM2": {
        "uniprot": "Q00987",
        "pdb_ids": ["1YCR", "4HG7"],
        "binding_site": "p53 binding pocket",
        "relevance": "Degrades p53 tumor suppressor. Amplified in 8% of GBM.",
    },
}


class PDBClient:
    """Download and cache protein structures from RCSB PDB."""

    def __init__(self, cache_dir: str = "./data/pdb_structures"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_structure(self, pdb_id: str, fmt: str = "pdb") -> Optional[Path]:
        """
        Download a single PDB structure file.
        Returns path to downloaded file, or None on failure.
        """
        pdb_id = pdb_id.upper()
        filename = f"{pdb_id}.{fmt}"
        filepath = self.cache_dir / filename

        if filepath.exists():
            logger.debug(f"Using cached structure: {filepath}")
            return filepath

        url = f"{RCSB_DOWNLOAD}/{pdb_id}.{fmt}"
        logger.info(f"Downloading {pdb_id} from RCSB PDB...")

        try:
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            filepath.write_text(resp.text, encoding="utf-8")
            logger.info(f"  Saved: {filepath} ({len(resp.text)} bytes)")
            return filepath
        except requests.RequestException as e:
            logger.error(f"  Failed to download {pdb_id}: {e}")
            return None

    def download_all_targets(self) -> Dict[str, List[Path]]:
        """
        Download all PDB structures for all GBM targets.
        Returns dict of target_name -> list of downloaded file paths.
        """
        results = {}
        for target_name, info in GBM_TARGETS.items():
            paths = []
            for pdb_id in info["pdb_ids"]:
                path = self.download_structure(pdb_id)
                if path:
                    paths.append(path)
            results[target_name] = paths
            logger.info(f"  {target_name}: {len(paths)}/{len(info['pdb_ids'])} structures")
        return results

    def get_target_info(self, target_name: str) -> Optional[Dict]:
        """Get metadata about a specific GBM target."""
        return GBM_TARGETS.get(target_name)

    def list_all_targets(self) -> List[str]:
        """List all available GBM drug targets."""
        return list(GBM_TARGETS.keys())

    def summarize(self) -> Dict:
        """
        Download everything and return a summary.
        """
        downloaded = self.download_all_targets()
        total_files = sum(len(v) for v in downloaded.values())
        return {
            "targets": len(GBM_TARGETS),
            "total_pdb_files": total_files,
            "per_target": {k: len(v) for k, v in downloaded.items()},
            "druggable_targets": [
                name for name, info in GBM_TARGETS.items()
                if "ATP" in info["binding_site"] or "pocket" in info["binding_site"].lower()
                or "groove" in info["binding_site"].lower()
            ],
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    client = PDBClient()
    summary = client.summarize()
    print("\n=== PDB STRUCTURES SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
