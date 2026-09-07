"""
face_embedding.py — Face detection + embedding for NexGen enrollment/matching.

Uses MTCNN (facenet-pytorch) for detection + landmark alignment + cropping,
and InceptionResnetV1 (pretrained on VGGFace2) for 512-d embeddings.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple, Union

import numpy as np
import torch
from facenet_pytorch import MTCNN, InceptionResnetV1
from PIL import Image


class FaceEmbedder:
    """Detects faces in an image and produces L2-normalized embedding vectors."""

    def __init__(self, device: Optional[str] = None, min_face_size: int = 40):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        # MTCNN handles detection, landmark alignment, and cropping to 160x160
        # in one step. keep_all=True so we can find every face in a frame
        # (needed later for video processing, not just single-face enrollment shots).
        self.mtcnn = MTCNN(
            image_size=160,
            margin=20,
            min_face_size=min_face_size,
            keep_all=True,
            post_process=True,
            device=self.device,
        )

        # 512-d embeddings, pretrained on VGGFace2.
        self.resnet = InceptionResnetV1(pretrained="vggface2").eval().to(self.device)

    def detect_and_embed(
        self, image: Union[str, Path, Image.Image]
    ) -> List[Tuple[np.ndarray, np.ndarray, float]]:
        """
        Detect every face in `image` and embed each one.

        Returns a list of (box, embedding, detection_confidence) tuples, one
        per detected face. `box` is [x1, y1, x2, y2] in original image pixel
        coordinates. `embedding` is a 512-d, L2-normalized numpy vector.
        Returns an empty list if no face is found.
        """
        img = self._load_image(image)

        boxes, probs = self.mtcnn.detect(img)
        if boxes is None:
            return []

        faces = self.mtcnn.extract(img, boxes, save_path=None)
        if faces is None:
            return []

        with torch.no_grad():
            embeddings = self.resnet(faces.to(self.device)).cpu().numpy()

        results = []
        for box, prob, emb in zip(boxes, probs, embeddings):
            emb = emb / (np.linalg.norm(emb) + 1e-10)
            results.append((box, emb, float(prob)))
        return results

    def embed_single_face(
        self, image: Union[str, Path, Image.Image], *, strict: bool = True
    ) -> np.ndarray:
        """
        Convenience method for enrollment shots, where we expect exactly one
        face per image.

        Raises ValueError if zero or multiple faces are found and
        `strict=True` (the default). With strict=False, returns the
        highest-confidence face instead of raising on multiple detections.
        """
        faces = self.detect_and_embed(image)

        if len(faces) == 0:
            raise ValueError(f"No face detected in {image!r}.")

        if len(faces) > 1:
            if strict:
                raise ValueError(
                    f"Expected exactly one face in {image!r}, found {len(faces)}. "
                    "Use strict=False to auto-pick the most confident detection, "
                    "or crop the enrollment photo to a single person."
                )
            faces = sorted(faces, key=lambda f: f[2], reverse=True)

        _, embedding, _ = faces[0]
        return embedding

    @staticmethod
    def _load_image(image: Union[str, Path, Image.Image]) -> Image.Image:
        if isinstance(image, Image.Image):
            return image.convert("RGB")
        return Image.open(image).convert("RGB")
