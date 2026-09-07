# NexGen — Face Enrollment & Embedding Module

Foundation piece of the NexGen surveillance system: detects faces, produces
embeddings, and matches a face against a set of registered ("known")
identities.

## Layout

```
enrollment/
    face_embedding.py   # FaceEmbedder: MTCNN detection/alignment + FaceNet (InceptionResnetV1) embeddings
    vector_store.py      # IdentityStore: local pickle-backed identity -> embeddings store, cosine-similarity matching
    enroll.py             # enroll_person / enroll_from_directory: photos-on-disk -> IdentityStore
notebooks/
    01_face_enrollment_prototype.ipynb   # interactive walkthrough
data/
    enrollment/           # put your enrollment photos here: data/enrollment/<name>/*.jpg
```

## Quickstart

```bash
pip install -r requirements.txt
```

1. Add enrollment photos: `data/enrollment/<person_name>/*.jpg` — 3-5 photos
   per person, varied angle/lighting, one clear face per photo.
2. Open `notebooks/01_face_enrollment_prototype.ipynb` and run the cells top
   to bottom. It enrolls everyone found, saves `data/identity_store.pkl`,
   then lets you test-match a query photo against the store.

Or from code directly:

```python
from pathlib import Path
from enrollment import FaceEmbedder, IdentityStore, enroll_from_directory

embedder = FaceEmbedder()
store = IdentityStore()
enroll_from_directory(Path("data/enrollment"), embedder, store)
store.save("data/identity_store.pkl")

# later, on a video frame:
for box, embedding, det_conf in embedder.detect_and_embed(frame):
    name, score = store.match(embedding, threshold=0.65)  # "unknown" if below threshold
```

## Design notes

- **Multiple embeddings per identity, not a centroid.** Matching compares a
  query against every stored embedding for every identity and takes the
  best score. Averaging angle-varied embeddings into one centroid tends to
  blur out exactly the pose variation multi-angle enrollment is meant to
  capture.
- **`threshold` in `IdentityStore.match` is a starting point, not a
  calibrated constant.** Tune it against your own enrollment + test footage
  — CCTV-angle faces generally need a more forgiving threshold than clean
  front-facing enrollment photos.
- **This store is local/pickle-backed on purpose**, for fast prototyping.
  `add_identity` / `match` are the two methods to reimplement against
  Alibaba Tair (TairVector) or AnalyticDB vector search when you move this
  past a local demo — same call sites, different backend.

## Next module

Run `embedder.detect_and_embed()` per sampled video frame (not just single
test images) and feed the per-frame matches into the event pipeline
alongside the weapon detector's output.
