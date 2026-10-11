# app/pipelines/weapon_detector.py

from pathlib import Path
from typing import Dict, List, Optional

from app.core.config import settings
from app.integrations.storage import StorageClient


def normalize_weapon_name(name: str) -> Optional[str]:
    n = name.lower().strip()

    if any(x in n for x in ["knife", "dagger", "blade"]):
        return "knife"

    if any(
        x in n
        for x in [
            "firearm",
            "fire arm",
            "gun",
            "pistol",
            "rifle",
            "shotgun",
            "handgun",
        ]
    ):
        return "firearm"

    # Everyday objects that are only sometimes a threat. Reported at a lower
    # priority than a real weapon.
    if "baseball bat" in n or n == "bat":
        return "baseball_bat"

    if "scissors" in n:
        return "scissors"

    return None


# Classes that are an emergency on sight, as opposed to "worth a look".
LETHAL_CLASSES = ("knife", "firearm")


class WeaponDetector:
    def __init__(self, storage: StorageClient):
        self.settings = settings
        self.storage = storage
        self.model = None
        self.names: Dict[int, str] = {}
        self.weapon_class_ids: List[int] = []
        self._load_model()

    @property
    def loaded(self) -> bool:
        return self.model is not None

    def _load_model(self) -> None:
        model_path: Optional[Path] = None

        try:
            if self.settings.weapon_model_oss_key:
                model_path = self.storage.download_to_cache(
                    self.settings.weapon_model_oss_key
                )

            elif self.settings.weapon_model_path:
                candidate = Path(self.settings.weapon_model_path)
                if candidate.exists():
                    model_path = candidate

            if not model_path or not Path(model_path).exists():
                print("[weapon] No weapon model found.")
                return

            from ultralytics import YOLO

            print(f"[weapon] Loading model: {model_path}")
            self.model = YOLO(str(model_path))

            raw_names = self.model.names

            if isinstance(raw_names, dict):
                self.names = {int(k): str(v) for k, v in raw_names.items()}
            elif isinstance(raw_names, list):
                self.names = {i: str(v) for i, v in enumerate(raw_names)}
            else:
                self.names = {}

            # A general-purpose model (e.g. COCO) has dozens of classes we
            # never report; telling the model which ones matter lets it skip
            # the rest instead of us discarding them afterwards.
            self.weapon_class_ids = [
                class_id
                for class_id, name in self.names.items()
                if normalize_weapon_name(name)
            ]

            print(
                "[weapon] Reporting classes: "
                f"{[self.names[i] for i in self.weapon_class_ids]}"
            )

            if not self.weapon_class_ids:
                print("[weapon] Model has no weapon classes; detection disabled.")
                self.model = None

        except Exception as e:
            print(f"[weapon] Failed to load weapon model: {e}")
            self.model = None

    def detect(
        self,
        frame,
        confidence_threshold: float,
        iou_threshold: float,
    ) -> List[dict]:
        if not self.loaded:
            return []

        try:
            device = 0 if self.settings.computed_device.startswith("cuda") else "cpu"

            results = self.model(
                frame,
                conf=confidence_threshold,
                iou=iou_threshold,
                device=device,
                classes=self.weapon_class_ids,
                imgsz=self.settings.weapon_inference_size,
                verbose=False,
            )

            if not results:
                return []

            result = results[0]
            detections = []

            if result.boxes is None:
                return []

            for box in result.boxes:
                try:
                    cls_tensor = box.cls
                    cls_id = int(cls_tensor.item()) if hasattr(cls_tensor, "item") else int(cls_tensor)

                    conf = float(box.conf.item()) if hasattr(box.conf, "item") else float(box.conf)

                    xyxy = box.xyxy[0].cpu().numpy().tolist()

                    raw_name = self.names.get(cls_id, str(cls_id))
                    normalized = normalize_weapon_name(raw_name)

                    if not normalized:
                        continue

                    detections.append(
                        {
                            "object_class": normalized,
                            "raw_class": raw_name,
                            "confidence": conf,
                            "bbox": xyxy,
                        }
                    )

                except Exception as e:
                    print(f"[weapon] Failed to parse detection: {e}")
                    continue

            return detections

        except Exception as e:
            print(f"[weapon] Detection failed: {e}")
            return []