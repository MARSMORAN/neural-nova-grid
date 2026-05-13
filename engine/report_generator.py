"""
engine/report_generator.py
Generate PDF dossiers for drug candidates.

Each report contains:
  - Molecule structure + properties
  - Screening results (docking, ADMET)
  - Digital twin simulation results
  - Literature context
  - Recommended next steps

Uses basic HTML→text approach for now; WeasyPrint or ReportLab for production PDF.
"""

import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, HRFlowable
    )
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False
    logger.info("ReportLab not installed — will generate text reports instead")


class ReportGenerator:
    """Generate drug candidate dossiers."""

    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_candidate_report(self, candidate: Dict,
                                    cycle_id: int) -> str:
        """
        Generate a full report for a drug candidate.
        Returns path to the generated report file.
        """
        cycle_dir = self.output_dir / f"cycle_{cycle_id:04d}"
        cycle_dir.mkdir(exist_ok=True)

        smiles = candidate.get("smiles", "UNKNOWN")
        safe_name = smiles[:20].replace("/", "_").replace("\\", "_")
        safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in safe_name)

        if HAS_REPORTLAB:
            return self._generate_pdf(candidate, cycle_dir, safe_name, cycle_id)
        else:
            return self._generate_text(candidate, cycle_dir, safe_name, cycle_id)

    def _generate_pdf(self, candidate: Dict, output_dir: Path,
                       name: str, cycle_id: int) -> str:
        """Generate a real PDF report using ReportLab."""
        filepath = output_dir / f"{name}.pdf"
        doc = SimpleDocTemplate(
            str(filepath), pagesize=A4,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
            leftMargin=2*cm, rightMargin=2*cm
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CustomTitle", parent=styles["Title"],
            fontSize=20, spaceAfter=20, textColor=colors.HexColor("#1a1a2e")
        )
        heading_style = ParagraphStyle(
            "CustomHeading", parent=styles["Heading2"],
            fontSize=14, spaceAfter=10, spaceBefore=15,
            textColor=colors.HexColor("#16213e")
        )
        body_style = styles["BodyText"]

        elements = []

        # ── Title page ────────────────────────────────────────
        elements.append(Spacer(1, 2*cm))
        elements.append(Paragraph(
            "NEURAL-NOVA v2", title_style
        ))
        elements.append(Paragraph(
            "Drug Candidate Dossier", heading_style
        ))
        elements.append(Spacer(1, 1*cm))

        smiles = candidate.get("smiles", "N/A")
        elements.append(Paragraph(
            f"<b>Candidate SMILES:</b> {smiles}", body_style
        ))
        elements.append(Paragraph(
            f"<b>Target:</b> {candidate.get('target', 'N/A')}", body_style
        ))
        elements.append(Paragraph(
            f"<b>Discovery Cycle:</b> {cycle_id}", body_style
        ))
        elements.append(Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}", body_style
        ))
        elements.append(Paragraph(
            f"<b>Composite Score:</b> {candidate.get('composite_score', 0):.4f}", body_style
        ))

        elements.append(Spacer(1, 1*cm))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))

        # ── Chemistry profile ─────────────────────────────────
        elements.append(Paragraph("Chemistry Profile", heading_style))
        chem_data = [
            ["Property", "Value", "BBB Threshold", "Status"],
            ["Molecular Weight", f"{candidate.get('mw', 0):.1f}", "< 450", self._status(candidate.get('mw', 500) < 450)],
            ["LogP", f"{candidate.get('logp', 0):.2f}", "0.5 - 4.0", self._status(0.5 <= candidate.get('logp', 0) <= 4.0)],
            ["H-Bond Donors", str(candidate.get('hbd', 0)), "<= 3", self._status(candidate.get('hbd', 5) <= 3)],
            ["H-Bond Acceptors", str(candidate.get('hba', 0)), "<= 7", self._status(candidate.get('hba', 10) <= 7)],
            ["TPSA", f"{candidate.get('tpsa', 0):.1f}", "< 90", self._status(candidate.get('tpsa', 100) < 90)],
            ["Passes Lipinski", str(candidate.get('passes_lipinski', False)), "Yes", ""],
            ["Passes BBB Filter", str(candidate.get('passes_bbb', False)), "Yes", ""],
            ["PAINS Alert", str(candidate.get('is_pains', False)), "No", ""],
        ]
        chem_table = Table(chem_data, colWidths=[3.5*cm, 2.5*cm, 3*cm, 2*cm])
        chem_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f0f5")]),
        ]))
        elements.append(chem_table)

        # ── Binding & Docking ─────────────────────────────────
        elements.append(Paragraph("Binding Analysis", heading_style))
        elements.append(Paragraph(
            f"<b>Estimated Docking Score:</b> {candidate.get('docking_score', 0):.2f} kcal/mol",
            body_style
        ))
        elements.append(Paragraph(
            f"<b>Similarity to Known Actives:</b> {candidate.get('similarity_to_known', 0):.3f} (Tanimoto)",
            body_style
        ))
        interp = "Strong binder" if candidate.get("docking_score", 0) < -8 else \
                 "Moderate binder" if candidate.get("docking_score", 0) < -7 else "Weak binder"
        elements.append(Paragraph(
            f"<b>Interpretation:</b> {interp}", body_style
        ))

        # ── ADMET Profile ─────────────────────────────────────
        elements.append(Paragraph("ADMET Profile", heading_style))
        admet_data = [
            ["Property", "Value", "Interpretation"],
            ["BBB Penetration", f"{candidate.get('bbb_penetration', 0):.3f}",
             "Likely crosses" if candidate.get("bbb_penetration", 0) > 0.5 else "Poor BBB penetration"],
            ["Oral Bioavailability", f"{candidate.get('oral_bioavailability', 0):.3f}",
             "Good" if candidate.get("oral_bioavailability", 0) > 0.5 else "Limited"],
            ["Metabolic Stability", f"{candidate.get('metabolic_stability', 0):.3f}",
             "Stable" if candidate.get("metabolic_stability", 0) > 0.5 else "Rapid clearance"],
            ["hERG Risk", f"{candidate.get('herg_risk', 0):.3f}",
             "LOW RISK" if candidate.get("herg_risk", 0) < 0.3 else "CAUTION"],
        ]
        admet_table = Table(admet_data, colWidths=[4*cm, 2.5*cm, 5*cm])
        admet_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16213e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f5f0")]),
        ]))
        elements.append(admet_table)

        # ── Verdict ───────────────────────────────────────────
        elements.append(Spacer(1, 1*cm))
        score = candidate.get("composite_score", 0)
        if score > 0.7:
            verdict = "HIGHLY PROMISING — Recommend immediate in-vitro validation"
            v_color = colors.HexColor("#27ae60")
        elif score > 0.5:
            verdict = "MODERATE — Consider as secondary candidate for validation"
            v_color = colors.HexColor("#f39c12")
        else:
            verdict = "WEAK — Archive for future reference"
            v_color = colors.HexColor("#e74c3c")

        elements.append(Paragraph("Verdict", heading_style))
        verdict_style = ParagraphStyle(
            "Verdict", parent=body_style,
            fontSize=12, textColor=v_color, fontName="Helvetica-Bold"
        )
        elements.append(Paragraph(verdict, verdict_style))

        # ── Recommended next steps ────────────────────────────
        elements.append(Paragraph("Recommended Next Steps", heading_style))
        steps = [
            "1. Validate binding affinity in cell-free assay (IC50 determination)",
            "2. Test cytotoxicity against U87-MG and U251 GBM cell lines",
            "3. Evaluate BBB penetration in MDCK-MDR1 monolayer assay",
            "4. Assess selectivity vs normal astrocytes (HA cell line)",
            "5. If positive: commence PK study in mouse model",
        ]
        for step in steps:
            elements.append(Paragraph(step, body_style))

        # Build PDF
        doc.build(elements)
        logger.info(f"Generated PDF report: {filepath}")
        return str(filepath)

    def _generate_text(self, candidate: Dict, output_dir: Path,
                        name: str, cycle_id: int) -> str:
        """Fallback: generate a text report."""
        filepath = output_dir / f"{name}.txt"

        lines = [
            "=" * 70,
            "NEURAL-NOVA v2 — DRUG CANDIDATE DOSSIER",
            "=" * 70,
            "",
            f"SMILES:          {candidate.get('smiles', 'N/A')}",
            f"Target:          {candidate.get('target', 'N/A')}",
            f"Discovery Cycle: {cycle_id}",
            f"Generated:       {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Composite Score: {candidate.get('composite_score', 0):.4f}",
            "",
            "--- CHEMISTRY PROFILE ---",
            f"  MW:              {candidate.get('mw', 0):.1f}",
            f"  LogP:            {candidate.get('logp', 0):.2f}",
            f"  TPSA:            {candidate.get('tpsa', 0):.1f}",
            f"  H-Bond Donors:   {candidate.get('hbd', 0)}",
            f"  H-Bond Acceptors:{candidate.get('hba', 0)}",
            f"  Lipinski:        {candidate.get('passes_lipinski', False)}",
            f"  BBB Filter:      {candidate.get('passes_bbb', False)}",
            f"  PAINS:           {candidate.get('is_pains', False)}",
            "",
            "--- BINDING ANALYSIS ---",
            f"  Docking Score:   {candidate.get('docking_score', 0):.2f} kcal/mol",
            f"  Similarity:      {candidate.get('similarity_to_known', 0):.3f}",
            "",
            "--- ADMET PROFILE ---",
            f"  BBB Penetration:     {candidate.get('bbb_penetration', 0):.3f}",
            f"  Oral Bioavailability:{candidate.get('oral_bioavailability', 0):.3f}",
            f"  Metabolic Stability: {candidate.get('metabolic_stability', 0):.3f}",
            f"  hERG Risk:           {candidate.get('herg_risk', 0):.3f}",
            "",
            "--- RECOMMENDED NEXT STEPS ---",
            "  1. Validate binding affinity in cell-free assay",
            "  2. Test cytotoxicity against U87-MG and U251 GBM cell lines",
            "  3. Evaluate BBB penetration in MDCK-MDR1 assay",
            "  4. Assess selectivity vs normal astrocytes",
            "  5. If positive: commence PK study in mouse model",
            "",
            "=" * 70,
        ]

        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Generated text report: {filepath}")
        return str(filepath)

    def generate_cycle_summary(self, cycle_id: int, cycle_stats: Dict,
                                 top_candidates: List[Dict]) -> str:
        """Generate a summary report for a complete cycle."""
        cycle_dir = self.output_dir / f"cycle_{cycle_id:04d}"
        cycle_dir.mkdir(exist_ok=True)
        filepath = cycle_dir / "cycle_summary.txt"

        lines = [
            "=" * 70,
            f"NEURAL-NOVA v2 — CYCLE {cycle_id} SUMMARY",
            "=" * 70,
            "",
            f"Molecules Generated:   {cycle_stats.get('molecules_generated', 0)}",
            f"Passed Screening:      {cycle_stats.get('molecules_passed_screen', 0)}",
            f"Simulated in Twin:     {cycle_stats.get('molecules_simulated', 0)}",
            f"Reports Generated:     {cycle_stats.get('reports_generated', 0)}",
            f"Best Composite Score:  {cycle_stats.get('best_composite_score', 0):.4f}",
            f"Target Used:           {cycle_stats.get('target_used', 'N/A')}",
            f"Elapsed Time:          {cycle_stats.get('elapsed_seconds', 0):.1f}s",
            "",
            "--- TOP CANDIDATES THIS CYCLE ---",
        ]

        for i, cand in enumerate(top_candidates[:10], 1):
            lines.append(
                f"  {i:2d}. {cand.get('smiles', 'N/A')[:40]:<42s}  "
                f"score={cand.get('composite_score', 0):.4f}  "
                f"BBB={cand.get('bbb_penetration', 0):.3f}"
            )

        lines.extend(["", "=" * 70])
        filepath.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Generated cycle summary: {filepath}")
        return str(filepath)

    @staticmethod
    def _status(condition: bool) -> str:
        return "PASS" if condition else "FAIL"
