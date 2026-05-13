"""
harvester/clintrials_client.py
Pull GBM clinical trial data from ClinicalTrials.gov API v2.

Builds a database of what has been tried, what worked, what failed,
and why — so the engine doesn't repeat failed approaches.
"""

import json
import time
import logging
import requests
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

CT_API = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsClient:
    """Pull GBM clinical trial data from ClinicalTrials.gov."""

    def __init__(self, cache_dir: str = "./data/literature"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_gbm_trials(self, max_studies: int = 500) -> pd.DataFrame:
        """
        Fetch all GBM clinical trials from ClinicalTrials.gov.
        Returns DataFrame with trial metadata, interventions, and outcomes.
        """
        cache_file = self.cache_dir / "clinical_trials_gbm.parquet"
        if cache_file.exists():
            logger.info(f"Loading cached clinical trials from {cache_file}")
            return pd.read_parquet(cache_file)

        logger.info("Fetching GBM clinical trials from ClinicalTrials.gov...")

        all_studies = []
        page_token = None

        while len(all_studies) < max_studies:
            params = {
                "query.cond": "Glioblastoma",
                "pageSize": min(100, max_studies - len(all_studies)),
                "fields": "NCTId,BriefTitle,OverallStatus,Phase,StartDate,"
                          "CompletionDate,EnrollmentCount,InterventionName,"
                          "InterventionType,PrimaryOutcomeMeasure,StudyType,"
                          "Condition,BriefSummary",
            }
            if page_token:
                params["pageToken"] = page_token

            try:
                resp = requests.get(CT_API, params=params, timeout=30)
                resp.raise_for_status()
                data = resp.json()

                studies = data.get("studies", [])
                if not studies:
                    break

                for study in studies:
                    proto = study.get("protocolSection", {})
                    ident = proto.get("identificationModule", {})
                    status_mod = proto.get("statusModule", {})
                    design = proto.get("designModule", {})
                    arms = proto.get("armsInterventionsModule", {})
                    outcomes = proto.get("outcomesModule", {})
                    desc = proto.get("descriptionModule", {})

                    # Extract interventions
                    interventions = arms.get("interventions", [])
                    interv_names = [i.get("name", "") for i in interventions]
                    interv_types = [i.get("type", "") for i in interventions]

                    # Extract primary outcomes
                    primary_outcomes = outcomes.get("primaryOutcomes", [])
                    outcome_measures = [o.get("measure", "") for o in primary_outcomes]

                    # Phase
                    phases = design.get("phases", [])

                    all_studies.append({
                        "nct_id": ident.get("nctId", ""),
                        "title": ident.get("briefTitle", ""),
                        "status": status_mod.get("overallStatus", ""),
                        "phase": "; ".join(phases) if phases else "",
                        "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
                        "completion_date": status_mod.get("completionDateStruct", {}).get("date", ""),
                        "enrollment": design.get("enrollmentInfo", {}).get("count"),
                        "interventions": "; ".join(interv_names),
                        "intervention_types": "; ".join(interv_types),
                        "primary_outcomes": "; ".join(outcome_measures),
                        "summary": desc.get("briefSummary", ""),
                    })

                page_token = data.get("nextPageToken")
                if not page_token:
                    break

                logger.info(f"  Fetched {len(all_studies)} trials...")
                time.sleep(0.5)

            except requests.RequestException as e:
                logger.warning(f"ClinicalTrials.gov request failed: {e}")
                time.sleep(3)
                continue

        df = pd.DataFrame(all_studies)
        df.to_parquet(cache_file, index=False)
        logger.info(f"Saved {len(df)} clinical trials to {cache_file}")
        return df

    def analyze_failures(self, trials_df: pd.DataFrame) -> List[Dict]:
        """
        Identify completed/terminated trials and extract lessons.
        This tells the engine what NOT to do.
        """
        failed_statuses = ["TERMINATED", "WITHDRAWN", "SUSPENDED"]
        completed = trials_df[
            (trials_df["status"].isin(failed_statuses)) |
            (trials_df["status"] == "COMPLETED")
        ].copy()

        lessons = []
        for _, row in completed.iterrows():
            interventions = row.get("interventions", "")
            status = row.get("status", "")
            title = row.get("title", "")
            phase = row.get("phase", "")

            # Categorize the failure type
            if status in failed_statuses:
                outcome = "terminated_or_withdrawn"
                lesson = f"Trial was {status.lower()}. Likely safety/futility concerns."
            else:
                outcome = "completed"
                lesson = "Completed but check results for efficacy signal."

            lessons.append({
                "nct_id": row.get("nct_id", ""),
                "title": title,
                "interventions": interventions,
                "phase": phase,
                "outcome": outcome,
                "lesson": lesson,
                "enrollment": row.get("enrollment"),
            })

        return lessons

    def summarize(self) -> Dict:
        df = self.fetch_gbm_trials(max_studies=300)
        failures = self.analyze_failures(df)

        return {
            "total_trials": len(df),
            "status_breakdown": df["status"].value_counts().to_dict(),
            "phase_breakdown": df["phase"].value_counts().head(5).to_dict(),
            "terminated_or_withdrawn": sum(
                1 for f in failures if f["outcome"] == "terminated_or_withdrawn"
            ),
            "most_common_interventions": self._top_interventions(df, 10),
        }

    def _top_interventions(self, df: pd.DataFrame, n: int) -> Dict[str, int]:
        counts = {}
        for interv_str in df["interventions"].dropna():
            for interv in interv_str.split("; "):
                interv = interv.strip()
                if interv and len(interv) > 2:
                    counts[interv] = counts.get(interv, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1])[:n])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    client = ClinicalTrialsClient()
    summary = client.summarize()
    print("\n=== CLINICAL TRIALS SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
