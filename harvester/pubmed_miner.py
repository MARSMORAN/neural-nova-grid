"""
harvester/pubmed_miner.py
Mine PubMed for GBM drug discovery research papers.

Extracts paper metadata (title, abstract, MeSH terms, publication date)
to build a knowledge base of what has been tried, what worked, what failed.
"""

import json
import time
import logging
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


@dataclass
class Paper:
    pmid: str
    title: str
    abstract: str
    authors: str
    journal: str
    year: int
    mesh_terms: List[str]
    keywords: List[str]


class PubMedMiner:
    """Mine PubMed for GBM-relevant research papers."""

    SEARCH_QUERIES = [
        "glioblastoma drug discovery",
        "glioblastoma targeted therapy clinical trial",
        "GBM blood brain barrier drug delivery",
        "glioblastoma immunotherapy checkpoint",
        "glioblastoma CAR-T cell therapy",
        "glioblastoma mRNA vaccine",
        "glioblastoma EGFR inhibitor resistance",
        "glioblastoma IDH1 inhibitor",
        "glioblastoma nanoparticle drug delivery",
        "glioblastoma temozolomide resistance mechanism",
    ]

    def __init__(self, cache_dir: str = "./data/literature"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def search(self, query: str, max_results: int = 100) -> List[str]:
        """Search PubMed and return list of PMIDs."""
        url = f"{EUTILS_BASE}/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "retmode": "json",
            "sort": "relevance",
        }
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
            pmids = data.get("esearchresult", {}).get("idlist", [])
            logger.info(f"  Search '{query[:40]}...': {len(pmids)} results")
            return pmids
        except requests.RequestException as e:
            logger.warning(f"PubMed search failed: {e}")
            return []

    def fetch_details(self, pmids: List[str]) -> List[Paper]:
        """Fetch paper details (title, abstract, MeSH) for given PMIDs."""
        if not pmids:
            return []

        url = f"{EUTILS_BASE}/efetch.fcgi"
        papers = []

        # Batch fetch in groups of 50
        for i in range(0, len(pmids), 50):
            batch = pmids[i:i+50]
            params = {
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
                "rettype": "abstract",
            }
            try:
                resp = requests.get(url, params=params, timeout=30)
                resp.raise_for_status()
                root = ET.fromstring(resp.content)

                for article_elem in root.findall(".//PubmedArticle"):
                    paper = self._parse_article(article_elem)
                    if paper:
                        papers.append(paper)

                time.sleep(0.4)  # NCBI rate limit: 3 requests/second
            except (requests.RequestException, ET.ParseError) as e:
                logger.warning(f"PubMed fetch failed: {e}")
                time.sleep(2)

        return papers

    def _parse_article(self, elem) -> Paper:
        """Parse a PubmedArticle XML element into a Paper object."""
        try:
            medline = elem.find(".//MedlineCitation")
            article = medline.find(".//Article")
            pmid = medline.findtext("PMID", "")
            title = article.findtext("ArticleTitle", "")

            # Abstract
            abstract_parts = []
            abstract_elem = article.find("Abstract")
            if abstract_elem is not None:
                for text in abstract_elem.findall("AbstractText"):
                    label = text.get("Label", "")
                    content = text.text or ""
                    if label:
                        abstract_parts.append(f"{label}: {content}")
                    else:
                        abstract_parts.append(content)
            abstract = " ".join(abstract_parts)

            # Authors
            author_list = article.find("AuthorList")
            authors = []
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last = author.findtext("LastName", "")
                    initials = author.findtext("Initials", "")
                    if last:
                        authors.append(f"{last} {initials}")
            author_str = "; ".join(authors[:5])
            if len(authors) > 5:
                author_str += f" et al. ({len(authors)} authors)"

            # Journal
            journal_elem = article.find("Journal")
            journal = journal_elem.findtext(".//Title", "") if journal_elem is not None else ""

            # Year
            pub_date = article.find(".//PubDate")
            year = int(pub_date.findtext("Year", "0")) if pub_date is not None else 0

            # MeSH terms
            mesh_list = medline.find("MeshHeadingList")
            mesh_terms = []
            if mesh_list is not None:
                for heading in mesh_list.findall("MeshHeading"):
                    descriptor = heading.findtext("DescriptorName", "")
                    if descriptor:
                        mesh_terms.append(descriptor)

            # Keywords
            kw_list = medline.find("KeywordList")
            keywords = []
            if kw_list is not None:
                for kw in kw_list.findall("Keyword"):
                    if kw.text:
                        keywords.append(kw.text)

            return Paper(
                pmid=pmid, title=title, abstract=abstract,
                authors=author_str, journal=journal, year=year,
                mesh_terms=mesh_terms, keywords=keywords,
            )
        except Exception as e:
            logger.debug(f"Failed to parse article: {e}")
            return None

    def mine_all(self, max_per_query: int = 50) -> List[Paper]:
        """
        Run all search queries and collect papers.
        Deduplicates by PMID.
        """
        cache_file = self.cache_dir / "pubmed_papers.json"
        if cache_file.exists():
            logger.info(f"Loading cached PubMed papers from {cache_file}")
            with open(cache_file) as f:
                data = json.load(f)
            return [Paper(**p) for p in data]

        logger.info("Mining PubMed for GBM research papers...")
        all_pmids = set()
        for query in self.SEARCH_QUERIES:
            pmids = self.search(query, max_results=max_per_query)
            all_pmids.update(pmids)
            time.sleep(0.5)

        logger.info(f"Total unique PMIDs: {len(all_pmids)}")
        papers = self.fetch_details(list(all_pmids))

        # Cache
        with open(cache_file, "w") as f:
            json.dump([asdict(p) for p in papers], f, indent=2)

        logger.info(f"Saved {len(papers)} papers to {cache_file}")
        return papers

    def extract_drug_mentions(self, papers: List[Paper]) -> Dict[str, int]:
        """
        Extract drug/compound mentions from paper abstracts.
        Simple keyword matching — production would use NER.
        """
        drug_keywords = [
            "temozolomide", "bevacizumab", "erlotinib", "gefitinib",
            "osimertinib", "ivosidenib", "nivolumab", "pembrolizumab",
            "palbociclib", "everolimus", "sirolimus", "carmustine",
            "lomustine", "procarbazine", "vincristine", "irinotecan",
            "regorafenib", "depatuxizumab", "rindopepimut", "tumor treating fields",
            "CAR-T", "checkpoint inhibitor", "EGFR inhibitor", "IDH inhibitor",
            "nanoparticle", "liposome", "convection enhanced delivery",
            "focused ultrasound", "oncolytic virus", "mRNA vaccine",
        ]
        counts = {}
        for paper in papers:
            text = (paper.title + " " + paper.abstract).lower()
            for drug in drug_keywords:
                if drug.lower() in text:
                    counts[drug] = counts.get(drug, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1]))

    def summarize(self) -> Dict:
        papers = self.mine_all(max_per_query=30)
        drug_mentions = self.extract_drug_mentions(papers)
        return {
            "total_papers": len(papers),
            "year_range": f"{min(p.year for p in papers if p.year)}-{max(p.year for p in papers if p.year)}" if papers else "N/A",
            "top_drug_mentions": dict(list(drug_mentions.items())[:15]),
            "top_mesh_terms": self._top_mesh(papers, 10),
        }

    def _top_mesh(self, papers: List[Paper], n: int) -> Dict[str, int]:
        counts = {}
        for p in papers:
            for term in p.mesh_terms:
                counts[term] = counts.get(term, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: -x[1])[:n])


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    miner = PubMedMiner()
    summary = miner.summarize()
    print("\n=== PUBMED MINING SUMMARY ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
