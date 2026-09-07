"""
enroll.py — Orchestrates enrollment: turns a directory of photos into
embeddings in an IdentityStore, with a basic consistency check per identity.

Expected directory layout:

    data/enrollment/
        alice/
            front.jpg
            left.jpg
            right.jpg
        bob/
            front.jpg
            ...

Usage:
    from enrollment import FaceEmbedder, IdentityStore, enroll_from_directory

    embedder = FaceEmbedder()
    store = IdentityStore()
    enroll_from_directory(Path("data/enrollment"), embedder, store)
    store.save("identity_store.pkl")
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np

from .face_embedding import FaceEmbedder
from .vector_store import IdentityStore

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def enroll_person(
    name: str,
    image_paths: List[Path],
    embedder: FaceEmbedder,
    store: IdentityStore,
    *,
    consistency_warn_threshold: float = 0.5,
) -> Dict[str, float]:
    """
    Enroll a single person from their enrollment photos.

    Returns a small report: number of photos used, and the lowest pairwise
    similarity seen among that person's own embeddings — a rough signal that
    one of the photos may have a bad crop/alignment, since genuine
    multi-angle shots of the same person should still cluster reasonably
    tightly.
    """
    embeddings = []
    for path in image_paths:
        try:
            emb = embedder.embed_single_face(path, strict=False)
            embeddings.append(emb)
        except ValueError as e:
            print(f"[skip] {path}: {e}")

    if not embeddings:
        raise ValueError(f"No usable faces found for {name!r} in {image_paths}.")

    store.add_identity(name, embeddings)

    # Sanity-check: how tightly do this person's own embeddings cluster?
    min_pairwise = 1.0
    for i in range(len(embeddings)):
        for j in range(i + 1, len(embeddings)):
            sim = float(np.dot(embeddings[i], embeddings[j]))
            min_pairwise = min(min_pairwise, sim)

    if len(embeddings) > 1 and min_pairwise < consistency_warn_threshold:
        print(
            f"[warn] {name!r}: lowest pairwise similarity among own photos is "
            f"{min_pairwise:.2f} — check for a bad crop, wrong person, or an "
            "extreme angle in one of the enrollment images."
        )

    return {
        "name": name,
        "num_embeddings": len(embeddings),
        "min_pairwise_similarity": min_pairwise,
    }


def enroll_from_directory(
    root: Path, embedder: FaceEmbedder, store: IdentityStore
) -> List[Dict[str, float]]:
    """Enroll every person found as a subdirectory of `root`."""
    root = Path(root)
    reports = []
    for person_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        image_paths = [
            p for p in sorted(person_dir.iterdir()) if p.suffix.lower() in IMAGE_EXTENSIONS
        ]
        if not image_paths:
            continue
        reports.append(enroll_person(person_dir.name, image_paths, embedder, store))
    return reports
