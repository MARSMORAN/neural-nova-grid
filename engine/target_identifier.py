"""
engine/target_identifier.py
Identify druggable GBM vulnerabilities from real genomic data.

Takes TCGA mutation + expression data and outputs a ranked list
of protein targets to design drugs against, cross-referenced
against what has already been tried in clinical trials.
"""

import logging
import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class TargetIdentifier:
    """
    Identifies and ranks druggable GBM targets using real genomic data.

    Pipeline:
      1. Count mutation frequency across TCGA-GBM cohort
      2. Identify genes with high-impact mutations (VEP: HIGH/MODERATE)
      3. Cross-reference with known druggable targets
      4. Check clinical trial history (what has been tried)
      5. Score and rank: mutation_freq * druggability * novelty
    """

    def __init__(self, driver_genes: Dict[str, Dict]):
        self.driver_genes = driver_genes

    def analyze_mutations(self, mutations_df: pd.DataFrame) -> pd.DataFrame:
        """
        Analyze mutation landscape from TCGA-GBM data.
        Returns DataFrame of genes ranked by mutation burden.
        """
        if mutations_df.empty:
            logger.warning("No mutation data available")
            return pd.DataFrame()

        # Count mutations per gene
        gene_counts = mutations_df["gene"].value_counts().reset_index()
        gene_counts.columns = ["gene", "mutation_count"]

        # Count high-impact mutations
        high_impact = mutations_df[
            mutations_df["vep_impact"].isin(["HIGH", "MODERATE"])
        ]["gene"].value_counts().reset_index()
        high_impact.columns = ["gene", "high_impact_count"]

        # Merge
        result = gene_counts.merge(high_impact, on="gene", how="left")
        result["high_impact_count"] = result["high_impact_count"].fillna(0).astype(int)
        result["high_impact_fraction"] = (
            result["high_impact_count"] / result["mutation_count"].clip(lower=1)
        )

        # Flag known driver genes
        result["is_driver"] = result["gene"].isin(self.driver_genes)
        result["druggable"] = result["gene"].apply(
            lambda g: self.driver_genes.get(g, {}).get("druggable", False)
        )
        result["role"] = result["gene"].apply(
            lambda g: self.driver_genes.get(g, {}).get("role", "unknown")
        )

        return result.sort_values("mutation_count", ascending=False)

    def score_targets(self, mutation_analysis: pd.DataFrame,
                      clinical_failures: List[Dict] = None) -> pd.DataFrame:
        """
        Score each potential target on a multi-factor basis:
          - Mutation frequency (is it commonly altered?)
          - High-impact fraction (are mutations functional?)
          - Druggability (does it have a known binding pocket?)
          - Novelty (has it NOT been tried in clinical trials?)
          - Role (oncogene > tumor_suppressor for inhibition)
        """
        if mutation_analysis.empty:
            return pd.DataFrame()

        df = mutation_analysis.copy()

        # Normalize mutation count to 0-1
        max_mut = df["mutation_count"].max()
        df["freq_score"] = df["mutation_count"] / max(max_mut, 1)

        # High-impact score
        df["impact_score"] = df["high_impact_fraction"]

        # Druggability score
        df["drug_score"] = df["druggable"].astype(float)

        # Role score: oncogenes are easier to inhibit than to restore tumor suppressors
        role_map = {"oncogene": 1.0, "tumor_supp": 0.3, "repair": 0.7,
                    "chromatin": 0.4, "unknown": 0.2}
        df["role_score"] = df["role"].map(role_map).fillna(0.2)

        # Novelty score: penalize targets that already failed in trials
        failed_targets = set()
        if clinical_failures:
            for trial in clinical_failures:
                interv = trial.get("interventions", "").lower()
                for gene in self.driver_genes:
                    if gene.lower() in interv:
                        failed_targets.add(gene)

        df["tried_in_trial"] = df["gene"].isin(failed_targets)
        df["novelty_score"] = (~df["tried_in_trial"]).astype(float) * 0.5 + 0.5

        # Composite score
        df["target_score"] = (
            0.25 * df["freq_score"] +
            0.20 * df["impact_score"] +
            0.20 * df["drug_score"] +
            0.15 * df["role_score"] +
            0.20 * df["novelty_score"]
        )

        return df.sort_values("target_score", ascending=False)

    def get_top_targets(self, mutation_analysis: pd.DataFrame,
                        clinical_failures: List[Dict] = None,
                        top_k: int = 10) -> List[Dict]:
        """
        Return the top-k druggable targets with full context.
        """
        scored = self.score_targets(mutation_analysis, clinical_failures)
        if scored.empty:
            # Fallback to known driver genes
            logger.warning("No mutation data — using known driver genes as targets")
            targets = []
            for gene, info in self.driver_genes.items():
                if info.get("druggable"):
                    targets.append({
                        "gene": gene,
                        "target_score": info.get("freq", 0.5),
                        "role": info.get("role", "unknown"),
                        "mutations": info.get("mutations", []),
                        "druggable": True,
                        "source": "known_driver_gene",
                    })
            return sorted(targets, key=lambda t: -t["target_score"])[:top_k]

        # Filter to druggable targets only
        druggable = scored[scored["druggable"]].head(top_k)
        targets = []
        for _, row in druggable.iterrows():
            gene = row["gene"]
            info = self.driver_genes.get(gene, {})
            targets.append({
                "gene": gene,
                "target_score": round(float(row["target_score"]), 4),
                "mutation_count": int(row["mutation_count"]),
                "high_impact_count": int(row["high_impact_count"]),
                "role": row["role"],
                "mutations": info.get("mutations", []),
                "druggable": True,
                "tried_in_trial": bool(row["tried_in_trial"]),
                "source": "tcga_genomics",
            })

        # If we got fewer than top_k, supplement with known drivers
        if len(targets) < top_k:
            existing_genes = {t["gene"] for t in targets}
            for gene, info in self.driver_genes.items():
                if gene not in existing_genes and info.get("druggable"):
                    targets.append({
                        "gene": gene,
                        "target_score": info.get("freq", 0.3),
                        "role": info.get("role", "unknown"),
                        "mutations": info.get("mutations", []),
                        "druggable": True,
                        "source": "known_driver_gene",
                    })
                if len(targets) >= top_k:
                    break

        return targets


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from harvester.tcga_client import TCGAClient

    tcga = TCGAClient()
    drivers = tcga.get_gbm_driver_genes()
    mutations = tcga.fetch_mutations()

    identifier = TargetIdentifier(drivers)
    analysis = identifier.analyze_mutations(mutations)
    targets = identifier.get_top_targets(analysis, top_k=8)

    print("\n=== TOP DRUGGABLE GBM TARGETS ===")
    for i, t in enumerate(targets, 1):
        print(f"  {i}. {t['gene']:<10s}  score={t['target_score']:.3f}  "
              f"role={t['role']}  mutations={t.get('mutations', [])}")
