from pathlib import Path
import pandas as pd
import streamlit as st
import plotly.express as px
import requests

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "candidates.csv"

st.set_page_config(
    page_title="Terra AI | Planetary Analog Discovery",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------
# Demo data: replace with backend-generated candidates.csv
# -----------------------------
DEMO_DATA = [
    {
        "site_id": "TA-001", "site_name": "Demo candidate – Atacama region",
        "country": "Chile", "latitude": -23.5, "longitude": -68.2,
        "visual_similarity": 91, "terrain_score": 86, "geology_score": 88,
        "climate_score": 95, "water_score": 32, "data_coverage": 91,
        "protected_area": False, "ecology_warning": "Low vegetation indicator; field assessment still required",
        "summary": "Illustrative dry, high-altitude environment for testing the dashboard."
    },
    {
        "site_id": "TA-002", "site_name": "Demo candidate – Icelandic volcanic terrain",
        "country": "Iceland", "latitude": 64.8, "longitude": -16.8,
        "visual_similarity": 84, "terrain_score": 82, "geology_score": 94,
        "climate_score": 48, "water_score": 72, "data_coverage": 88,
        "protected_area": True, "ecology_warning": "Protected-area flag: review restrictions before any field activity",
        "summary": "Illustrative volcanic landscape; included to demonstrate ecological safeguards."
    },
    {
        "site_id": "TA-003", "site_name": "Demo candidate – Utah desert terrain",
        "country": "United States", "latitude": 38.3, "longitude": -110.0,
        "visual_similarity": 79, "terrain_score": 93, "geology_score": 80,
        "climate_score": 82, "water_score": 38, "data_coverage": 95,
        "protected_area": False, "ecology_warning": "Check local land-management rules and habitat sensitivity",
        "summary": "Illustrative arid terrain for rover mobility and geomorphology interface testing."
    },
    {
        "site_id": "TA-004", "site_name": "Demo candidate – Namib region",
        "country": "Namibia", "latitude": -24.7, "longitude": 15.3,
        "visual_similarity": 87, "terrain_score": 77, "geology_score": 75,
        "climate_score": 92, "water_score": 25, "data_coverage": 79,
        "protected_area": False, "ecology_warning": "Fragile desert ecosystems may be present; verify locally",
        "summary": "Illustrative dune and arid-land environment; not a verified analog finding."
    },
    {
        "site_id": "TA-005", "site_name": "Demo candidate – Canadian Arctic",
        "country": "Canada", "latitude": 69.0, "longitude": -135.0,
        "visual_similarity": 73, "terrain_score": 69, "geology_score": 71,
        "climate_score": 88, "water_score": 90, "data_coverage": 83,
        "protected_area": False, "ecology_warning": "Seasonal wildlife and sensitive tundra considerations",
        "summary": "Illustrative cold-region environment for water/ice research interface testing."
    },
]

# Correct a deliberately explicit coordinate value in the demo record.
DEMO_DATA[-1]["longitude"] = -135.0

OBJECTIVE_WEIGHTS = {
    "General analog assessment": {"visual_similarity": 0.25, "terrain_score": 0.20, "geology_score": 0.20, "climate_score": 0.20, "water_score": 0.15},
    "Rover mobility": {"visual_similarity": 0.10, "terrain_score": 0.40, "geology_score": 0.15, "climate_score": 0.20, "water_score": 0.15},
    "Geological investigation": {"visual_similarity": 0.10, "terrain_score": 0.15, "geology_score": 0.45, "climate_score": 0.15, "water_score": 0.15},
    "Water / ice resource study": {"visual_similarity": 0.10, "terrain_score": 0.10, "geology_score": 0.15, "climate_score": 0.15, "water_score": 0.50},
    "Extreme-environment research": {"visual_similarity": 0.15, "terrain_score": 0.15, "geology_score": 0.15, "climate_score": 0.40, "water_score": 0.15},
}

SCORE_LABELS = {
    "visual_similarity": "Visual similarity",
    "terrain_score": "Terrain compatibility",
    "geology_score": "Geological compatibility",
    "climate_score": "Climate compatibility",
    "water_score": "Water / ice compatibility",
}

@st.cache_data
def load_data():
    if DATA_FILE.exists():
        df = pd.read_csv(DATA_FILE)
    else:
        df = pd.DataFrame(DEMO_DATA)
    required = [
        "site_id", "site_name", "country", "latitude", "longitude",
        "visual_similarity", "terrain_score", "geology_score",
        "climate_score", "water_score", "data_coverage",
        "protected_area", "ecology_warning", "summary"
    ]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError("Missing required CSV columns: " + ", ".join(missing))
    # Preserve missing scientific measurements as NaN; missing is not a zero score.
    for col in list(SCORE_LABELS) + ["data_coverage"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").clip(0, 100)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["protected_area"] = df["protected_area"].astype(str).str.lower().isin(["true", "1", "yes"])
    return df

st.markdown("""
<style>
.block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
[data-testid="stMetric"] {background: rgba(120, 140, 160, 0.08); padding: 14px; border-radius: 12px;}
.small-note {font-size: 0.88rem; opacity: 0.8;}
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.title("🌍 Terra AI")
    st.caption("Responsible Global Planetary Analog Discovery")
    st.divider()
    target = st.selectbox("Planetary target", ["Mars", "Moon"])
    objective = st.selectbox("Research objective", list(OBJECTIVE_WEIGHTS))
    st.markdown("**Discovery settings**")
    max_results = st.slider("Number of candidates to display", 3, 124, 124)
    hide_protected = st.checkbox("Hide protected-area candidates", value=False)
    min_coverage = st.slider("Minimum data coverage (%)", 0, 100, 0, 5)
    st.divider()
    st.markdown("**Backend 1 · Earth spatial screening**")
    bbox_west = st.number_input("West longitude", min_value=-180.0, max_value=180.0, value=-70.0, step=0.5)
    bbox_south = st.number_input("South latitude", min_value=-90.0, max_value=90.0, value=-25.0, step=0.5)
    bbox_east = st.number_input("East longitude", min_value=-180.0, max_value=180.0, value=-65.0, step=0.5)
    bbox_north = st.number_input("North latitude", min_value=-90.0, max_value=90.0, value=-20.0, step=0.5)
    grid_spacing = st.select_slider("Grid spacing (km)", options=[25, 50, 100, 200, 500], value=100)
    if st.button("Screen Earth region", use_container_width=True):
        try:
            screen_response = requests.post(
                "http://127.0.0.1:5001/api/screen",
                json={"target": target, "bbox": {"west": bbox_west, "south": bbox_south,
                      "east": bbox_east, "north": bbox_north},
                      "spacing_km": grid_spacing, "max_points": 5000}, timeout=30
            )
            screen_response.raise_for_status()
            points = screen_response.json()["points"]
            candidate_rows = [{
                "site_id": point["site_id"],
                "site_name": f"Unassessed Earth grid candidate {i+1}",
                "country": "Unresolved",
                "latitude": point["latitude"],
                "longitude": point["longitude"],
                "summary": "Spatial discovery point only. Scientific dimensions and ecological status have not yet been assessed."
            } for i, point in enumerate(points)]
            generated = requests.post(
                "http://127.0.0.1:5001/api/candidates/generate",
                json={"target": target, "candidates": candidate_rows}, timeout=30
            )
            generated.raise_for_status()
            load_data.clear()
            st.success(f"Generated {len(candidate_rows)} Earth screening points. Backend 2 will rank only measured dimensions.")
            st.rerun()
        except requests.RequestException as exc:
            st.error(f"Backend 1 unavailable or request failed: {exc}")
    st.divider()
    st.caption("Prototype UI • Demo data is not a scientific result")

backend2_status = False
try:
    backend2_status = requests.get("http://127.0.0.1:5002/api/health", timeout=1.5).ok
except requests.RequestException:
    backend2_status = False

st.title("Planetary Analog Discovery")
st.caption("Backend 2 scientific ranking: connected" if backend2_status else "Backend 2 scientific ranking: offline (local prototype mode)")
st.write(
    f"Explore Earth environments for **{target}** research. Backend 1 discovers candidates and imagery; Backend 2 applies evidence-based scientific scoring and ecological review."
)

if not DATA_FILE.exists():
    st.info("DEMO MODE: the locations and scores shown are illustrative sample records, not validated discoveries or field-site recommendations. Start Backend 1 and generate candidates to use live records.")

with st.expander("Backend 1 · NASA imagery discovery and CLIP analysis"):
    imagery_query = st.text_input("Search Earth analog imagery", value="Atacama Desert")
    if st.button("Search NASA imagery"):
        try:
            image_response = requests.get(
                "http://127.0.0.1:5001/api/imagery/search",
                params={"target": target, "q": imagery_query, "page_size": 8}, timeout=40
            )
            image_response.raise_for_status()
            st.session_state["terra_imagery_results"] = image_response.json().get("items", [])
        except requests.RequestException as exc:
            st.error(f"NASA imagery search failed: {exc}")
    for item in st.session_state.get("terra_imagery_results", []):
        st.markdown(f"**{item.get('title') or 'Untitled NASA image'}**")
        if item.get("preview_url"):
            st.image(item["preview_url"], width=220)
        st.caption(f"NASA ID: {item.get('nasa_id')} · {item.get('date_created') or 'Date unavailable'}")
        st.caption(item.get("warning", ""))
    uploaded_image = st.file_uploader("Optional local image for CLIP semantic matching", type=["jpg", "jpeg", "png", "webp"])
    if uploaded_image is not None and st.button("Analyze image with CLIP"):
        try:
            image_dir = BASE_DIR / "data" / "images"
            image_dir.mkdir(parents=True, exist_ok=True)
            safe_name = Path(uploaded_image.name).name
            image_path = image_dir / safe_name
            image_path.write_bytes(uploaded_image.getvalue())
            clip_response = requests.post(
                "http://127.0.0.1:5001/api/clip/score",
                json={"target": target, "image_path": str(image_path)}, timeout=180
            )
            clip_response.raise_for_status()
            clip_result = clip_response.json()
            st.write(f"Model: {clip_result.get('model')} · Device: {clip_result.get('device')}")
            st.dataframe(pd.DataFrame(clip_result.get("matches", [])), use_container_width=True)
            st.caption(clip_result.get("interpretation", ""))
        except requests.RequestException as exc:
            st.error(f"CLIP analysis failed: {exc}")

try:
    df = load_data()
except Exception as exc:
    st.error(f"Could not load candidate data: {exc}")
    st.stop()

weights = OBJECTIVE_WEIGHTS[objective]

# Integrate the scientific ranking service when real Backend 1 candidates exist.
# The frontend objective weights are translated to Backend 2's short dimension keys.
backend2_url = "http://127.0.0.1:5002"
backend2_status = False
try:
    backend2_status = requests.get(f"{backend2_url}/api/health", timeout=1.5).ok
except requests.RequestException:
    backend2_status = False

# Rank only when explicitly requested. Keep the last successful result
# in Streamlit session state while display filters are changed.
backend2_ranked = False

discovery_signature = None
if DATA_FILE.exists():
    stat = DATA_FILE.stat()
    discovery_signature = (stat.st_mtime_ns, stat.st_size)

ranking_context = (target, objective, discovery_signature)

if st.session_state.get("terra_ranking_context") != ranking_context:
    st.session_state.pop("terra_ranked_records", None)
    st.session_state.pop("terra_ranking_context", None)

run_ranking = st.sidebar.button(
    "Run scientific ranking",
    use_container_width=True,
    disabled=not backend2_status or df.empty
)

if run_ranking:
    try:
        payload_candidates = []
        for _, row in df.iterrows():
            dimensions = {}
            for frontend_key, backend_key in [
                ("visual_similarity", "visual"), ("terrain_score", "terrain"),
                ("geology_score", "geology"), ("climate_score", "climate"),
                ("water_score", "water")
            ]:
                value = row.get(frontend_key)
                dimensions[backend_key] = None if pd.isna(value) else float(value)

            protected = bool(row.get("protected_area", False))
            payload_candidates.append({
                "site_id": str(row.get("site_id", "UNASSIGNED")),
                "site_name": str(row.get("site_name", "Unnamed candidate")),
                "country": str(row.get("country", "Unresolved")),
                "latitude": None if pd.isna(row.get("latitude")) else float(row.get("latitude")),
                "longitude": None if pd.isna(row.get("longitude")) else float(row.get("longitude")),
                "dimensions": dimensions,
                "ecology": {
                    "status": "review" if protected else "unknown",
                    "protected_area": protected,
                    "notes": str(row.get("ecology_warning", ""))
                }
            })

        backend_weights = {
            "visual": weights["visual_similarity"] * 100,
            "terrain": weights["terrain_score"] * 100,
            "geology": weights["geology_score"] * 100,
            "climate": weights["climate_score"] * 100,
            "water": weights["water_score"] * 100
        }

        response = requests.post(
            f"{backend2_url}/api/rank",
            json={
                "target": target,
                "mission": objective,
                "weights": backend_weights,
                "candidates": payload_candidates
            },
            timeout=30
        )
        response.raise_for_status()
        ranking_response = response.json()

        if not isinstance(ranking_response.get("candidates"), list):
            raise ValueError("Backend 2 returned an invalid ranking response.")

        scientific_csv = BASE_DIR / "data" / "scientific_candidates.csv"
        if not scientific_csv.exists():
            raise ValueError("Backend 2 did not create scientific_candidates.csv.")

        ranked_df = pd.read_csv(scientific_csv)
        if len(ranked_df) != len(payload_candidates):
            raise ValueError("Ranked CSV candidate count does not match the submitted candidates.")

        st.session_state["terra_ranked_records"] = ranked_df.to_dict("records")
        st.session_state["terra_ranking_context"] = ranking_context
        st.sidebar.success(
            f"Scientific ranking completed: {len(ranked_df)} candidates."
        )

    except (requests.RequestException, ValueError, KeyError) as exc:
        st.sidebar.warning(f"Backend 2 ranking failed: {exc}")

if (
    st.session_state.get("terra_ranking_context") == ranking_context
    and st.session_state.get("terra_ranked_records") is not None
):
    df = pd.DataFrame(st.session_state["terra_ranked_records"])
    df["protected_area"] = (
        df["protected_area"].astype(str).str.strip().str.lower()
        .isin(["true", "1", "yes"])
    )
    for col in list(SCORE_LABELS) + ["data_coverage", "analog_score"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").clip(0, 100)
    backend2_ranked = True
elif not backend2_status:
    st.sidebar.warning("Backend 2 is offline ? showing local prototype ranking")
else:
    st.sidebar.info("Click 'Run scientific ranking' to calculate the scientific ranking.")

# Use the Backend 2 index when present. Otherwise calculate a clearly labelled
# partial local prototype index using only measured dimensions (never NaN -> 0).
if not backend2_ranked:
    def local_partial_score(row):
        available = {k: w for k, w in weights.items() if pd.notna(row.get(k))}
        denominator = sum(available.values())
        if denominator <= 0:
            return float("nan")
        return sum(float(row[k]) * w for k, w in available.items()) / denominator
    df["analog_score"] = df.apply(local_partial_score, axis=1)

filtered = df[df["data_coverage"].fillna(0) >= min_coverage].copy()
if hide_protected:
    filtered = filtered[~filtered["protected_area"]]
filtered = filtered.sort_values("analog_score", ascending=False, na_position="last").head(max_results)
filtered["rank"] = range(1, len(filtered) + 1)

# Top-level metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Candidates displayed", len(filtered))
m2.metric("Highest analog score", f"{filtered['analog_score'].max():.1f}/100" if len(filtered) else "—")
m3.metric("Average data coverage", f"{filtered['data_coverage'].mean():.0f}%" if len(filtered) else "—")
m4.metric("Protected-area flags", int(filtered["protected_area"].sum()) if len(filtered) else 0)

st.divider()
map_col, rank_col = st.columns([1.25, 1])

with map_col:
    st.subheader("Global candidate map")
    if len(filtered):
        map_data = filtered.dropna(subset=["latitude", "longitude"])[["latitude", "longitude"]]
        st.map(map_data, latitude="latitude", longitude="longitude", use_container_width=True)
        st.caption("Map pins represent the currently displayed sample candidates.")
    else:
        st.warning("No candidates match the current filters.")

with rank_col:
    st.subheader("Candidate ranking")
    if len(filtered):
        chart = px.bar(
            filtered.sort_values("analog_score"),
            x="analog_score", y="site_name", orientation="h",
            labels={"analog_score": "Analog score (0–100)", "site_name": "Candidate"},
            range_x=[0, 100],
        )
        chart.update_layout(height=360, margin=dict(l=10, r=10, t=15, b=10))
        st.plotly_chart(chart, use_container_width=True)
    else:
        st.info("Adjust the filters to see ranked candidates.")

st.divider()
st.subheader("Candidate explorer")
if len(filtered):
    options = filtered["site_id"].tolist()
    selected_id = st.selectbox(
        "Choose a candidate",
        options,
        format_func=lambda x: f"{x} · {filtered.loc[filtered.site_id == x, 'site_name'].iloc[0]}"
    )
    candidate = filtered.loc[filtered.site_id == selected_id].iloc[0]

    left, right = st.columns([1, 1])
    with left:
        st.markdown(f"### {candidate['site_name']}")
        st.write(f"**Country/region:** {candidate['country']}")
        st.write(f"**Coordinates:** {candidate['latitude']:.3f}, {candidate['longitude']:.3f}")
        st.write(candidate["summary"])
        score_value = candidate["analog_score"]
        st.metric("Objective-weighted analog index", f"{score_value:.1f}/100" if pd.notna(score_value) else "Not yet calculable")
        st.progress(int(candidate["data_coverage"] if pd.notna(candidate["data_coverage"]) else 0), text=f"Data coverage: {candidate['data_coverage']:.0f}%" if pd.notna(candidate["data_coverage"]) else "Data coverage: unavailable")
        if "ranking_status" in candidate.index:
            st.write(f"**Scientific ranking status:** {candidate['ranking_status']}")
        if "ecology_gate" in candidate.index:
            st.write(f"**Separate ecological gate:** {candidate['ecology_gate']}")
        if candidate["protected_area"]:
            st.error("Protected-area flag: do not treat this as permission to visit or conduct fieldwork.")
        else:
            st.warning("Environmental review is still required before any field activity.")
        st.caption(str(candidate["ecology_warning"]))

    with right:
        st.markdown("### Similarity breakdown")
        score_frame = pd.DataFrame({
            "Dimension": [SCORE_LABELS[k] for k in weights],
            "Score": [candidate[k] for k in weights],
            "Weight": [weights[k] for k in weights],
        })
        fig = px.bar(
            score_frame, x="Score", y="Dimension", orientation="h",
            range_x=[0, 100], text="Score",
        )
        fig.update_traces(texttemplate="%{text:.0f}", textposition="outside")
        fig.update_layout(height=310, margin=dict(l=10, r=20, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with st.expander("How this score is calculated"):
        st.write("The score is a weighted ranking index, not a probability or proof of scientific equivalence. If dimensions are missing, Backend 2 renormalizes only over measured dimensions and labels the index partial.")
        for key, weight in weights.items():
            st.write(f"- {SCORE_LABELS[key]}: **{weight:.0%}**")
        st.write("Environmental safeguards are shown separately and are not allowed to be cancelled out by a high analog score.")
else:
    st.info("No candidate is available to inspect.")

st.divider()
st.subheader("Earth vs planetary environment: important limitations")
if target == "Mars":
    limitations = [
        "Earth has a much thicker atmosphere than Mars; pressure and atmospheric composition are not reproduced.",
        "Earth analogs do not reproduce Martian surface radiation exposure or gravity.",
        "Dust behavior, electrostatics, and weathering may differ substantially.",
    ]
else:
    limitations = [
        "Earth analogs do not reproduce lunar vacuum, gravity, or radiation exposure.",
        "Earth's atmosphere and active hydrological cycle differ fundamentally from the lunar surface.",
        "Thermal cycling and abrasive lunar dust behavior require separate analysis.",
    ]
for item in limitations:
    st.write(f"- {item}")

st.caption(
    "Scientific note: visual resemblance alone is insufficient. Verify source datasets, spatial resolution, acquisition dates, "
    "geological classifications, and uncertainty before interpreting a candidate."
)

# Export the filtered candidate table
if len(filtered):
    export_cols = [
        "rank", "site_id", "site_name", "country", "latitude", "longitude",
        "analog_score", "visual_similarity", "terrain_score", "geology_score",
        "climate_score", "water_score", "data_coverage", "protected_area",
        "ecology_warning"
    ]
    csv_bytes = filtered[export_cols].to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download candidate results (CSV)",
        data=csv_bytes,
        file_name="terra_ai_candidate_results.csv",
        mime="text/csv",
    )

with st.expander("Backend integration contract"):
    st.write("The frontend reads `data/candidates.csv`. Your backend can generate this file or replace `load_data()` with an API call.")
    st.code(
        "site_id,site_name,country,latitude,longitude,visual_similarity,terrain_score,geology_score,climate_score,water_score,data_coverage,protected_area,ecology_warning,summary",
        language="text",
    )
