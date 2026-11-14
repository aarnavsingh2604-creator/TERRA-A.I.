# TERRA AI — Full Integrated Project

This package brings together the existing Streamlit frontend (`app.py`), Backend Developer 1 (Earth spatial discovery, NASA imagery search, CLIP), and Backend Developer 2 (scientific scoring, ecology gate, explainable ranking).

## Architecture and ports

- Frontend: Streamlit `app.py` — http://localhost:8501
- Backend 1: Flask `backend_api.py` — http://127.0.0.1:5001
- Backend 2: Flask `backend2_api.py` — http://127.0.0.1:5002
- Shared handoff: `data/candidates.csv`
- Backend 2 audit output: `data/scientific_analysis.json`

Your original frontend has been carried forward and extended, not replaced by a Flask app.

## Install

Use Python 3.10 or newer (Python 3.11 is a good choice for PyTorch compatibility).

```bash
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

The first CLIP inference may download model weights and can take time. CPU works but can be slow; a compatible CUDA setup is faster.

## Start all three services

```bash
python run_all.py
```

Or start separately in three terminals:

```bash
python backend_api.py
```

```bash
python backend2_api.py
```

```bash
streamlit run app.py
```

## End-to-end workflow

1. Open the Streamlit dashboard at http://localhost:8501.
2. Choose Mars or Moon and a research objective.
3. In the sidebar, enter a bounding box and click **Screen Earth region**. The frontend calls Backend 1 `/api/screen`, then `/api/candidates/generate`.
4. Backend 1 writes discovery coordinates to `data/candidates.csv`. These are unassessed grid candidates, not scientifically validated analog sites.
5. The frontend calls Backend 2 `/api/rank` when it detects a live candidate CSV and Backend 2 is online. Backend 2 calculates the weighted index from dimensions that actually have scores, calculates data coverage, applies a separate ecological status gate, and rewrites the shared CSV with ranking and audit fields.
6. The dashboard reads the enriched CSV, displays the map, ranking, candidate details, score breakdown and CSV export.
7. Use the **NASA imagery discovery and CLIP analysis** expander to search NASA's Image and Video Library or run CLIP semantic comparison on a local uploaded image.

## Important scientific limitation

The spatial grid only generates candidate coordinates. NASA Image and Video Library search is an image-discovery feature; results are not guaranteed to be georeferenced/calibrated remote-sensing products. CLIP scores semantic resemblance to text prompts; they are not scientific suitability scores or probabilities.

Backend 2 does not invent terrain, geology, climate, water or ecological measurements. Until evidence-backed scores are added to candidate records, those dimensions remain missing. Missing values are not converted to zero. The ranking is a partial index over available dimensions, clearly labelled with coverage. Ecology `unknown` or `review` is not a clearance; only an explicit `pass` clears the separate gate, and `reject` excludes a candidate from recommendation.

The default 28/25/20/17/10 weights and objective profiles are prototypes. They must be calibrated and approved by relevant domain experts before research or operational use.

## Key API endpoints

Backend 1:
- `GET /api/health`
- `POST /api/screen`
- `GET /api/imagery/search?target=Mars&q=Atacama%20Desert`
- `POST /api/clip/score`
- `POST /api/compare`
- `POST /api/candidates/generate`

Backend 2:
- `GET /api/health`
- `GET /api/profiles`
- `POST /api/analyze`
- `POST /api/rank`
- `POST /api/compare`
- `GET /api/export.csv`

## Tests

```bash
python -m unittest discover -s tests -v
```

Backend 2 tests are included in `tests_backend2/` and can be run with:

```bash
python -m unittest discover -s tests_backend2 -v
```
