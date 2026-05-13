"""
harvester/tcga_client.py
Pull real GBM patient genomics from the NCI Genomic Data Commons (GDC).

Data: TCGA-GBM project — 617 patients with:
  - Somatic mutations (MAF files)
  - Gene expression (RNA-seq counts)
  - Clinical data (survival, treatment, demographics)
  - Methylation (MGMT promoter status)

All data is de-identified and publicly available under dbGaP open-access tier.
"""

import os
import json
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Any

logger = logging.getLogger(__name__)

GDC_API = "https://api.gdc.cancer.gov"
PROJECT = "TCGA-GBM"


class TCGAClient:
    """Client for pulling GBM data from the GDC API."""

    def __init__(self, cache_dir: str = "./data/tcga"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
        })

    # ── Clinical data ─────────────────────────────────────────

    def fetch_clinical(self, max_cases: int = 700) -> pd.DataFrame:
        """
        Fetch clinical data for all TCGA-GBM patients.
        Returns DataFrame with demographics, survival, treatment history.
        """
        cache_file = self.cache_dir / "clinical.parquet"
        if cache_file.exists():
            logger.info(f"Loading cached clinical data from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Fetching clinical data for {PROJECT} from GDC API...")

        endpoint = f"{GDC_API}/cases"
        filters = {
            "op": "and",
            "content": [
                {"op": "=", "content": {"field": "project.project_id", "value": PROJECT}},
                {"op": "=", "content": {"field": "cases.primary_site", "value": "Brain"}},
            ]
        }
        fields = [
            "case_id",
            "submitter_id",
            "demographic.gender",
            "demographic.year_of_birth",
            "demographic.race",
            "demographic.vital_status",
            "demographic.days_to_death",
            "diagnoses.age_at_diagnosis",
            "diagnoses.primary_diagnosis",
            "diagnoses.tumor_grade",
            "diagnoses.tumor_stage",
            "diagnoses.days_to_last_follow_up",
            "diagnoses.treatments.therapeutic_agents",
            "diagnoses.treatments.treatment_type",
        ]

        all_cases = []
        offset = 0
        page_size = 100

        while offset < max_cases:
            params = {
                "filters": json.dumps(filters),
                "fields": ",".join(fields),
                "format": "JSON",
                "size": min(page_size, max_cases - offset),
                "from": offset,
            }
            try:
                resp = self.session.get(endpoint, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                hits = data.get("data", {}).get("hits", [])
                if not hits:
                    break
                all_cases.extend(hits)
                offset += len(hits)
                logger.info(f"  Fetched {len(all_cases)} / {max_cases} cases")
                time.sleep(0.3)  # rate limit courtesy
            except requests.RequestException as e:
                logger.warning(f"GDC API request failed: {e}. Retrying in 5s...")
                time.sleep(5)
                continue

        # Flatten into DataFrame
        records = []
        for case in all_cases:
            demo = case.get("demographic", {}) or {}
            diags = case.get("diagnoses", []) or []
            diag = diags[0] if diags else {}
            treatments = diag.get("treatments", []) or []

            days_death = demo.get("days_to_death")
            days_follow = diag.get("days_to_last_follow_up")
            survival_days = days_death or days_follow

            record = {
                "case_id": case.get("case_id", ""),
                "submitter_id": case.get("submitter_id", ""),
                "gender": demo.get("gender", "unknown"),
                "vital_status": demo.get("vital_status", "unknown"),
                "age_at_diagnosis": diag.get("age_at_diagnosis"),
                "primary_diagnosis": diag.get("primary_diagnosis", ""),
                "tumor_grade": diag.get("tumor_grade", ""),
                "survival_days": survival_days,
                "survival_months": round(survival_days / 30.44, 1) if survival_days else None,
                "censored": 1 if demo.get("vital_status") == "Alive" else 0,
                "treatments": "; ".join(
                    t.get("therapeutic_agents", "unknown")
                    for t in treatments
                    if t.get("therapeutic_agents")
                ),
                "treatment_types": "; ".join(
                    t.get("treatment_type", "unknown")
                    for t in treatments
                    if t.get("treatment_type")
                ),
            }
            records.append(record)

        df = pd.DataFrame(records)
        df.to_parquet(cache_file, index=False)
        logger.info(f"Saved {len(df)} clinical records to {cache_file}")
        return df

    # ── Somatic mutations ─────────────────────────────────────

    def fetch_mutations(self, max_cases: int = 700) -> pd.DataFrame:
        """
        Fetch somatic mutations (SNVs, indels) for TCGA-GBM patients.
        Returns DataFrame with gene, mutation type, variant classification.
        """
        cache_file = self.cache_dir / "mutations.parquet"
        if cache_file.exists():
            logger.info(f"Loading cached mutation data from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info(f"Fetching somatic mutation data for {PROJECT}...")

        endpoint = f"{GDC_API}/ssms"
        filters = {
            "op": "=",
            "content": {
                "field": "cases.project.project_id",
                "value": PROJECT,
            }
        }
        fields = [
            "ssm_id",
            "consequence.transcript.gene.symbol",
            "consequence.transcript.annotation.vep_impact",
            "mutation_subtype",
            "genomic_dna_change",
            "consequence.transcript.aa_change",
        ]

        all_mutations = []
        offset = 0
        page_size = 500

        while True:
            params = {
                "filters": json.dumps(filters),
                "fields": ",".join(fields),
                "format": "JSON",
                "size": page_size,
                "from": offset,
            }
            try:
                resp = self.session.get(endpoint, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()
                hits = data.get("data", {}).get("hits", [])
                if not hits:
                    break
                all_mutations.extend(hits)
                offset += len(hits)
                total = data.get("data", {}).get("pagination", {}).get("total", "?")
                logger.info(f"  Fetched {len(all_mutations)} / {total} mutations")
                time.sleep(0.3)
                if offset >= 5000:  # cap for initial run
                    break
            except requests.RequestException as e:
                logger.warning(f"GDC mutation request failed: {e}")
                time.sleep(5)
                continue

        # Flatten
        records = []
        for mut in all_mutations:
            consequences = mut.get("consequence", []) or []
            for csq in consequences:
                transcript = csq.get("transcript", {}) or {}
                gene_info = transcript.get("gene", {}) or {}
                annotation = transcript.get("annotation", {}) or {}
                records.append({
                    "ssm_id": mut.get("ssm_id", ""),
                    "gene": gene_info.get("symbol", ""),
                    "aa_change": transcript.get("aa_change", ""),
                    "vep_impact": annotation.get("vep_impact", ""),
                    "mutation_subtype": mut.get("mutation_subtype", ""),
                    "dna_change": mut.get("genomic_dna_change", ""),
                })

        df = pd.DataFrame(records)
        df.to_parquet(cache_file, index=False)
        logger.info(f"Saved {len(df)} mutation records to {cache_file}")
        return df

    # ── Gene expression ───────────────────────────────────────

    def fetch_expression_manifest(self, max_files: int = 200) -> List[Dict]:
        """
        Get manifest of RNA-seq gene expression files for TCGA-GBM.
        Returns list of file metadata (file_id, file_name, case_id).
        """
        cache_file = self.cache_dir / "expression_manifest.json"
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)

        logger.info("Fetching RNA-seq expression file manifest...")

        endpoint = f"{GDC_API}/files"
        filters = {
            "op": "and",
            "content": [
                {"op": "=", "content": {
                    "field": "cases.project.project_id", "value": PROJECT
                }},
                {"op": "=", "content": {
                    "field": "data_type", "value": "Gene Expression Quantification"
                }},
                {"op": "=", "content": {
                    "field": "analysis.workflow_type", "value": "STAR - Counts"
                }},
            ]
        }
        fields = [
            "file_id", "file_name", "file_size",
            "cases.case_id", "cases.submitter_id",
        ]

        params = {
            "filters": json.dumps(filters),
            "fields": ",".join(fields),
            "format": "JSON",
            "size": max_files,
        }

        try:
            resp = self.session.get(endpoint, params=params, timeout=30)
            resp.raise_for_status()
            hits = resp.json().get("data", {}).get("hits", [])
        except requests.RequestException as e:
            logger.error(f"Failed to fetch expression manifest: {e}")
            hits = []

        manifest = []
        for hit in hits:
            cases = hit.get("cases", [])
            case_id = cases[0].get("case_id", "") if cases else ""
            manifest.append({
                "file_id": hit.get("file_id", ""),
                "file_name": hit.get("file_name", ""),
                "file_size": hit.get("file_size", 0),
                "case_id": case_id,
            })

        with open(cache_file, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.info(f"Found {len(manifest)} expression files")
        return manifest

    # ── Known GBM driver genes ────────────────────────────────

    @staticmethod
    def get_gbm_driver_genes() -> Dict[str, Dict]:
        """
        Curated list of known GBM driver genes with clinical relevance.
        Source: WHO 2021 CNS tumor classification + TCGA landmark papers.
        """
        return {
            "EGFR":   {"role": "oncogene",   "freq": 0.57, "druggable": True,
                       "mutations": ["vIII deletion", "amplification", "A289V"]},
            "IDH1":   {"role": "oncogene",   "freq": 0.12, "druggable": True,
                       "mutations": ["R132H", "R132C"]},
            "TP53":   {"role": "tumor_supp", "freq": 0.31, "druggable": False,
                       "mutations": ["R175H", "R248W", "R273H"]},
            "PTEN":   {"role": "tumor_supp", "freq": 0.36, "druggable": False,
                       "mutations": ["deletion", "R130*"]},
            "NF1":    {"role": "tumor_supp", "freq": 0.14, "druggable": False,
                       "mutations": ["truncating"]},
            "PDGFRA": {"role": "oncogene",   "freq": 0.13, "druggable": True,
                       "mutations": ["amplification", "D842V"]},
            "CDK4":   {"role": "oncogene",   "freq": 0.14, "druggable": True,
                       "mutations": ["amplification"]},
            "CDKN2A": {"role": "tumor_supp", "freq": 0.61, "druggable": False,
                       "mutations": ["homozygous deletion"]},
            "RB1":    {"role": "tumor_supp", "freq": 0.08, "druggable": False,
                       "mutations": ["deletion", "truncating"]},
            "PIK3CA": {"role": "oncogene",   "freq": 0.10, "druggable": True,
                       "mutations": ["E545K", "H1047R"]},
            "PIK3R1": {"role": "tumor_supp", "freq": 0.10, "druggable": False,
                       "mutations": ["truncating"]},
            "MDM2":   {"role": "oncogene",   "freq": 0.08, "druggable": True,
                       "mutations": ["amplification"]},
            "TERT":   {"role": "oncogene",   "freq": 0.83, "druggable": False,
                       "mutations": ["C228T", "C250T"]},
            "MGMT":   {"role": "repair",     "freq": 0.45, "druggable": True,
                       "mutations": ["promoter methylation (beneficial)"]},
            "ATRX":   {"role": "chromatin",  "freq": 0.07, "druggable": False,
                       "mutations": ["loss of function"]},
        }

    # ── Convenience summary ───────────────────────────────────

    def summarize(self) -> Dict[str, Any]:
        """
        Pull all available data and return a summary dict.
        """
        clinical = self.fetch_clinical()
        mutations = self.fetch_mutations()
        manifest = self.fetch_expression_manifest()
        drivers = self.get_gbm_driver_genes()

        # Top mutated genes in our dataset
        gene_counts = mutations["gene"].value_counts().head(20)

        summary = {
            "total_patients": len(clinical),
            "median_survival_months": clinical["survival_months"].median(),
            "gender_distribution": clinical["gender"].value_counts().to_dict(),
            "vital_status": clinical["vital_status"].value_counts().to_dict(),
            "expression_files_available": len(manifest),
            "total_mutations_fetched": len(mutations),
            "top_mutated_genes": gene_counts.to_dict(),
            "known_driver_genes": list(drivers.keys()),
            "druggable_targets": [g for g, info in drivers.items() if info["druggable"]],
        }
        return summary


# ── CLI entry point ──────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    client = TCGAClient()
    summary = client.summarize()
    print("\n=== TCGA-GBM DATA SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
