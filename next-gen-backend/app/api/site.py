# app/api/site.py

"""
Site profile: where this box is installed and who to call.

The dashboard shows these contacts when an operator acts on an alert. They
live in a small JSON file next to the other runtime state rather than in the
database, because they are configuration an installer edits once, not data.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger("nexgen.api.site")

router = APIRouter(prefix="/api/v1", tags=["site"])

_lock = threading.Lock()


class Contact(BaseModel):
    # police | rescue | fire | ambulance | security | other
    kind: str = Field(default="other", max_length=32)
    label: str = Field(min_length=1, max_length=120)
    phone: str = Field(default="", max_length=40)
    address: str = Field(default="", max_length=300)


class SiteProfile(BaseModel):
    site_name: str = Field(default="", max_length=120)
    site_address: str = Field(default="", max_length=300)
    contacts: List[Contact] = Field(default_factory=list, max_length=20)


# National short codes in Pakistan, where this product is deployed. They work
# from any phone; the local station and the site's own guard are added by the
# installer under Settings.
_DEFAULT_CONTACTS = [
    Contact(kind="police", label="Police emergency helpline", phone="15"),
    Contact(kind="rescue", label="Rescue 1122 (emergency & ambulance)", phone="1122"),
    Contact(kind="fire", label="Fire brigade", phone="16"),
    Contact(kind="ambulance", label="Edhi ambulance", phone="115"),
]


def _path() -> Path:
    return Path(settings.local_storage_dir) / "site_profile.json"


def load_profile() -> SiteProfile:
    path = _path()

    with _lock:
        if path.is_file():
            try:
                return SiteProfile(**json.loads(path.read_text(encoding="utf-8")))
            except Exception as e:
                logger.warning(f"Site profile unreadable, using defaults: {e}")

    return SiteProfile(contacts=list(_DEFAULT_CONTACTS))


def save_profile(profile: SiteProfile) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")

    with _lock:
        tmp_path.write_text(
            json.dumps(profile.model_dump(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp_path, path)


@router.get("/site")
def get_site() -> SiteProfile:
    return load_profile()


@router.put("/site")
def update_site(profile: SiteProfile) -> SiteProfile:
    save_profile(profile)
    return profile

