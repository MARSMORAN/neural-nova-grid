"""
engine/molecule_generator.py
De novo molecule generation for GBM drug candidates.

Three strategies:
  1. SMILES-LSTM: Autoregressive LSTM trained on drug-like molecules
  2. Fragment mutation: Modify known scaffolds (TMZ, kinase inhibitors)
  3. Enumeration: Systematic functional group variation

All generated molecules are valid SMILES checked by RDKit if available.
"""

import random
import math
import logging
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Dict, Optional, Set
from dataclasses import dataclass

logger = logging.getLogger(__name__)

try:
    from rdkit import Chem
    from rdkit.Chem import AllChem
    HAS_RDKIT = True
except ImportError:
    HAS_RDKIT = False


# ── SMILES vocabulary ────────────────────────────────────────

SMILES_CHARS = list(
    "CNOSFPIBrcnoslp=#()[]+-0123456789@/\\.H"
)
CHAR_TO_IDX = {c: i+2 for i, c in enumerate(SMILES_CHARS)}
IDX_TO_CHAR = {v: k for k, v in CHAR_TO_IDX.items()}
VOCAB_SIZE  = len(SMILES_CHARS) + 3  # +PAD(0) +BOS(1) +EOS(last)
BOS_IDX = 1
EOS_IDX = VOCAB_SIZE - 1


def encode_smiles(smi: str) -> List[int]:
    return [CHAR_TO_IDX.get(c, 0) for c in smi]


def decode_smiles(indices: List[int]) -> str:
    return "".join(IDX_TO_CHAR.get(i, "") for i in indices)


# ── Training data: Trojan Metabolites ──────────────────────────

# Seed set weaponized for GBM's hyper-metabolism
SEED_MOLECULES = [
    # Glucose analogs (GLUT1/3 targeting)
    "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@H]1O",            # D-Glucose (Base)
    "OC[C@H]1OC(NC(=O)c2ccccn2)[C@H](O)[C@@H](O)[C@H]1O", # Glucose-Pyridine Trojan
    "OC[C@H]1OC(NC(=O)Nc2ccc(F)cc2)[C@H](O)[C@@H](O)[C@H]1O", # Glucose-Urea Trojan
    # Glutamine analogs (SLC1A5 targeting)
    "N[C@@H](CCC(=O)N)C(=O)O",                        # L-Glutamine (Base)
    "NC(CCC(=O)Nc1ccncc1)C(=O)O",                     # Glutamine-Pyridine Trojan
    "NC(CCC(=O)Nc1ccc(Cl)cc1)C(=O)O",                  # Glutamine-Chlorobenzamide Trojan
    # Ascorbic Acid analogs (SVCT2 targeting)
    "OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",                  # Vitamin C (Base)
    "NC(=O)c1cccc(c1)OC[C@H](O)[C@H]1OC(=O)C(O)=C1O",  # Vitamin C-Amide Trojan
    # Large neutral amino acid analogs (LAT1 targeting)
    "N[C@@H](Cc1ccccc1)C(=O)O",                        # Phenylalanine (Base)
    "NC(Cc1ccc(NC(=O)c2ccncc2)cc1)C(=O)O",             # Phenylalanine-Pyridine Trojan
]


# ── LSTM generator ───────────────────────────────────────────

class SMILESGenerator(nn.Module):
    """
    Autoregressive character-level LSTM for SMILES generation.
    Trained on drug-like molecules; generates novel valid SMILES.
    """

    def __init__(self, vocab_size: int = VOCAB_SIZE,
                 embed_dim: int = 64, hidden: int = 256,
                 n_layers: int = 2):
        super().__init__()
        self.embed  = nn.Embedding(vocab_size, embed_dim, padding_idx=0)
        self.lstm   = nn.LSTM(embed_dim, hidden, n_layers,
                               batch_first=True, dropout=0.1)
        self.head   = nn.Linear(hidden, vocab_size)
        self.hidden = hidden
        self.n_layers = n_layers

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        emb = self.embed(x)
        out, _ = self.lstm(emb)
        return self.head(out)

    @torch.no_grad()
    def sample(self, max_len: int = 80, temperature: float = 0.8) -> str:
        """Generate a single SMILES string."""
        self.eval()
        tokens = [BOS_IDX]
        h0 = torch.zeros(self.n_layers, 1, self.hidden)
        c0 = torch.zeros(self.n_layers, 1, self.hidden)
        hc = (h0, c0)

        for _ in range(max_len):
            x = torch.tensor([[tokens[-1]]])
            emb = self.embed(x)
            out, hc = self.lstm(emb, hc)
            logits = self.head(out[0, -1]) / max(temperature, 0.1)
            probs = F.softmax(logits, dim=-1)
            nxt = torch.multinomial(probs, 1).item()
            if nxt == EOS_IDX or nxt == 0:
                break
            tokens.append(nxt)

        return decode_smiles(tokens[1:])  # skip BOS


class MoleculeGenerator:
    """
    Generates novel drug candidate SMILES via three strategies.
    """

    def __init__(self, seed_smiles: List[str] = None):
        self.seed_smiles = seed_smiles or SEED_MOLECULES
        self.model = SMILESGenerator()
        self._pretrain()
        self.generated_history: Set[str] = set()

    def _pretrain(self):
        """Train the LSTM on the seed molecule set."""
        logger.info("Pre-training SMILES generator on seed molecules...")
        opt = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        self.model.train()

        # Prepare training data
        encoded = []
        for smi in self.seed_smiles:
            enc = [BOS_IDX] + encode_smiles(smi) + [EOS_IDX]
            if len(enc) < 80:
                enc += [0] * (80 - len(enc))  # pad
            encoded.append(enc[:80])

        data = torch.tensor(encoded, dtype=torch.long)

        for epoch in range(300):
            idx = torch.randint(0, len(data), (min(16, len(data)),))
            batch = data[idx]
            inputs  = batch[:, :-1]
            targets = batch[:, 1:]

            logits = self.model(inputs)
            loss = F.cross_entropy(
                logits.reshape(-1, VOCAB_SIZE),
                targets.reshape(-1),
                ignore_index=0
            )
            opt.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            opt.step()

        logger.info("  Pre-training complete")

    def _is_valid_smiles(self, smi: str) -> bool:
        """Check if a SMILES string is valid."""
        if not smi or len(smi) < 3:
            return False
        if HAS_RDKIT:
            return Chem.MolFromSmiles(smi) is not None
        # Heuristic: balanced parentheses and brackets
        return smi.count("(") == smi.count(")") and smi.count("[") == smi.count("]")

    # ── Strategy 1: LSTM generation ───────────────────────────

    def generate_denovo(self, n: int = 100,
                         temperature: float = 0.8) -> List[str]:
        """Generate novel molecules using the LSTM."""
        results = []
        attempts = 0
        max_attempts = n * 10

        while len(results) < n and attempts < max_attempts:
            smi = self.model.sample(temperature=temperature)
            attempts += 1
            if self._is_valid_smiles(smi) and smi not in self.generated_history:
                results.append(smi)
                self.generated_history.add(smi)

        logger.info(f"  LSTM generated {len(results)}/{n} valid novel molecules "
                     f"({attempts} attempts)")
        return results

    # ── Strategy 2: Fragment mutation ─────────────────────────

    FUNCTIONAL_GROUPS = [
        ("F", "Cl"),  ("Cl", "F"),  ("F", "Br"),
        ("O", "S"),   ("S", "O"),   ("N", "O"),
        ("C", "N"),   ("c1ccccc1", "c1ccncc1"),  # benzene → pyridine
        ("c1ccncc1", "c1ccoc1"),   # pyridine → furan
        ("(=O)", "(=S)"),
        ("NC(=O)", "NC(=S)"),
        ("C(=O)O", "C(=O)N"),     # acid → amide
    ]

    def generate_fragments(self, n: int = 100) -> List[str]:
        """
        Generate molecules by mutating known scaffolds.
        """
        results = []
        for _ in range(n * 5):
            if len(results) >= n:
                break
            parent = random.choice(self.seed_smiles)
            fg_old, fg_new = random.choice(self.FUNCTIONAL_GROUPS)

            if fg_old in parent:
                child = parent.replace(fg_old, fg_new, 1)
                if (self._is_valid_smiles(child) and
                        child not in self.generated_history and
                        child not in self.seed_smiles):
                    results.append(child)
                    self.generated_history.add(child)

        logger.info(f"  Fragment mutation generated {len(results)}/{n} molecules")
        return results

    # ── Strategy 3: Enumeration ───────────────────────────────

    SUBSTITUENTS = [
        "F", "Cl", "Br", "O", "N", "C", "CC", "OC",
        "C(F)(F)F", "C#N", "C(=O)N", "S(=O)(=O)N",
    ]

    def generate_enumeration(self, n: int = 100) -> List[str]:
        """
        Systematic substitution on seed scaffolds.
        """
        results = []
        for _ in range(n * 5):
            if len(results) >= n:
                break
            parent = random.choice(self.seed_smiles)
            sub = random.choice(self.SUBSTITUENTS)

            # Try adding substituent at a random position
            if "c1" in parent:
                # Add to aromatic ring
                child = parent.replace("c1ccc", f"c1c({sub})cc", 1)
            elif "C(" in parent:
                child = parent.replace("C(", f"C({sub})(", 1)
            else:
                child = parent + sub

            if (self._is_valid_smiles(child) and
                    child not in self.generated_history):
                results.append(child)
                self.generated_history.add(child)

        logger.info(f"  Enumeration generated {len(results)}/{n} molecules")
        return results

    # ── Hybrid: all strategies ────────────────────────────────

    def generate(self, n: int = 500,
                 denovo_frac: float = 0.5,
                 fragment_frac: float = 0.3,
                 enum_frac: float = 0.2) -> List[str]:
        """
        Generate molecules using all three strategies.
        """
        n_denovo   = int(n * denovo_frac)
        n_fragment = int(n * fragment_frac)
        n_enum     = n - n_denovo - n_fragment

        logger.info(f"Generating {n} molecules "
                     f"(LSTM={n_denovo}, frag={n_fragment}, enum={n_enum})")

        all_mols = []
        all_mols.extend(self.generate_denovo(n_denovo))
        all_mols.extend(self.generate_fragments(n_fragment))
        all_mols.extend(self.generate_enumeration(n_enum))

        # Deduplicate
        unique = list(set(all_mols))
        logger.info(f"  Total unique molecules: {len(unique)}")
        return unique

    def retrain(self, good_smiles: List[str], lr: float = 5e-4):
        """
        Fine-tune the generator on molecules that scored well.
        This is how the engine self-improves.
        """
        if len(good_smiles) < 3:
            logger.warning("Not enough good molecules to retrain")
            return

        logger.info(f"Retraining generator on {len(good_smiles)} winning molecules...")

        opt = torch.optim.Adam(self.model.parameters(), lr=lr)
        self.model.train()

        encoded = []
        for smi in good_smiles:
            enc = [BOS_IDX] + encode_smiles(smi) + [EOS_IDX]
            if len(enc) < 80:
                enc += [0] * (80 - len(enc))
            encoded.append(enc[:80])

        data = torch.tensor(encoded, dtype=torch.long)

        for epoch in range(100):
            idx = torch.randint(0, len(data), (min(8, len(data)),))
            batch = data[idx]
            logits = self.model(batch[:, :-1])
            loss = F.cross_entropy(
                logits.reshape(-1, VOCAB_SIZE),
                batch[:, 1:].reshape(-1),
                ignore_index=0
            )
            opt.zero_grad()
            loss.backward()
            opt.step()

        logger.info("  Retraining complete")

    def save_model(self, path: str):
        torch.save(self.model.state_dict(), path)
        logger.info(f"Saved generator to {path}")

    def classify_metabolic_trap(self, smiles: str) -> str:
        """Classify which metabolic pathway this Trojan is exploiting."""
        s = smiles.lower()
        if "c1oc(o)[c@h](o)[c@@h](o)[c@h]1o" in s or "c[c@h]1oc(o)" in s:
            return "Glucose Mimetic (GLUT1/3 Trap)"
        if "ccc(=o)n)c(=o)o" in s or "ccc(=o)n" in s:
            return "Glutamine Mimetic (SLC1A5 Trap)"
        if "oc[c@h](o)[c@h]1oc(=o)c(o)=c1o" in s:
            return "Ascorbic Acid Mimetic (SVCT2 Trap)"
        if "cc)c(=o)o" in s or "cc)c(=o)n" in s:
            return "Amino Acid Mimetic (LAT1 Trap)"
        return "Broad Metabolic Trojan"

    def load_model(self, path: str):
        self.model.load_state_dict(torch.load(path, weights_only=True))
        logger.info(f"Loaded generator from {path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    gen = MoleculeGenerator()
    mols = gen.generate(n=50)
    print(f"\nGenerated {len(mols)} unique molecules")
    for m in mols[:10]:
        valid = "VALID" if gen._is_valid_smiles(m) else "invalid"
        print(f"  {m[:60]:<62s}  [{valid}]")
