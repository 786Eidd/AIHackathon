"""
vector_store.py — Local identity store for NexGen face embeddings.

Each registered identity can hold multiple embeddings (one per enrollment
photo/angle). Matching compares a query embedding against every stored
embedding for every identity and returns the single best match — this is
deliberately not centroid-averaged, since averaging angle-varied embeddings
tends to blur out the pose information that makes multi-angle enrollment
useful in the first place.

Good for prototyping and hackathon-scale identity counts. Swap out for
Alibaba Tair (TairVector) or AnalyticDB (vector search) when you move past
a local demo — same interface, different backend for `match`/`add_identity`.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Tuple, Union

import numpy as np

UNKNOWN = "unknown"


@dataclass
class IdentityStore:
    """identity_name -> list of L2-normalized embedding vectors."""

    embeddings: Dict[str, List[np.ndarray]] = field(default_factory=dict)

    def add_identity(self, name: str, embeddings: List[np.ndarray]) -> None:
        """Register (or extend) an identity with one or more embeddings."""
        if not embeddings:
            raise ValueError(f"No embeddings provided for identity {name!r}.")
        self.embeddings.setdefault(name, []).extend(embeddings)

    def delete_identity(self, name: str) -> None:
        self.embeddings.pop(name, None)

    def list_identities(self) -> List[str]:
        return sorted(self.embeddings.keys())

    def match(
        self, query_embedding: np.ndarray, threshold: float = 0.65
    ) -> Tuple[str, float]:
        """
        Compare a query embedding against every stored embedding.

        Returns (identity_name, similarity_score). If the best similarity is
        below `threshold`, returns (UNKNOWN, best_score_found) — the score is
        still returned so callers can log near-misses instead of throwing
        the information away.

        `threshold` is a starting point for VGGFace2-style cosine similarity
        on 512-d embeddings; tune it against your own enrollment + test
        footage before relying on it — CCTV-angle faces will generally need
        a lower bar than clean front-facing photos.
        """
        best_name = UNKNOWN
        best_score = -1.0

        for name, vectors in self.embeddings.items():
            for vec in vectors:
                score = float(np.dot(query_embedding, vec))  # both L2-normalized -> cosine sim
                if score > best_score:
                    best_score = score
                    best_name = name

        if best_score < threshold:
            return UNKNOWN, best_score
        return best_name, best_score

    def save(self, path: Union[str, Path]) -> None:
        with open(path, "wb") as f:
            pickle.dump(self.embeddings, f)

    @classmethod
    def load(cls, path: Union[str, Path]) -> "IdentityStore":
        with open(path, "rb") as f:
            data = pickle.load(f)
        return cls(embeddings=data)
