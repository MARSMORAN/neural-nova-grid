"""Test all data harvesters against real public APIs."""
import sys, io, logging

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

print("=" * 60)
print("NEURAL-NOVA v8.0 Sovereign — DATA HARVESTER TEST")
print("Pulling REAL data from public APIs...")
print("=" * 60)

# 1. TCGA — Real GBM patient data
print("\n[1/4] TCGA-GBM Clinical Data...")
from harvester.tcga_client import TCGAClient
tcga = TCGAClient()
summary = tcga.summarize()
print(f"  Patients:          {summary['total_patients']}")
print(f"  Median survival:   {summary['median_survival_months']} months")
print(f"  Mutations fetched: {summary['total_mutations_fetched']}")
print(f"  Druggable targets: {summary['druggable_targets']}")

# 2. PDB — Real protein structures
print("\n[2/4] PDB Protein Structures...")
from harvester.pdb_client import PDBClient
pdb = PDBClient()
pdb_summary = pdb.summarize()
print(f"  Targets:           {pdb_summary['targets']}")
print(f"  PDB files:         {pdb_summary['total_pdb_files']}")

# 3. ClinicalTrials.gov
print("\n[3/4] ClinicalTrials.gov GBM trials...")
from harvester.clintrials_client import ClinicalTrialsClient
ct = ClinicalTrialsClient()
ct_summary = ct.summarize()
print(f"  Total GBM trials:  {ct_summary['total_trials']}")
print(f"  Terminated/Withdrawn: {ct_summary['terminated_or_withdrawn']}")

# 4. PubMed
print("\n[4/4] PubMed Research Papers...")
from harvester.pubmed_miner import PubMedMiner
pm = PubMedMiner()
pm_summary = pm.summarize()
print(f"  Papers mined:      {pm_summary['total_papers']}")
print(f"  Year range:        {pm_summary['year_range']}")
top_drugs = pm_summary.get("top_drug_mentions", {})
if top_drugs:
    print("  Top drug mentions:")
    for drug, count in list(top_drugs.items())[:8]:
        print(f"    {drug}: {count} papers")

print("\n" + "=" * 60)
print("ALL DATA HARVESTERS WORKING")
print("=" * 60)
