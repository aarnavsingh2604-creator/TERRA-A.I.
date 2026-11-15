from pathlib import Path
import json
import os
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import requests

BASE_DIR = Path(__file__).parent
DATA_FILE = BASE_DIR / "data" / "candidates_recovered_124.csv"
BACKEND1_URL = os.getenv("TERRA_BACKEND1_URL", "http://127.0.0.1:5001").rstrip("/")
BACKEND2_URL = os.getenv("TERRA_BACKEND2_URL", "http://127.0.0.1:5002").rstrip("/")

st.set_page_config(page_title="TERRA AI | Planetary Analog Intelligence", page_icon="ðŸŒ", layout="wide", initial_sidebar_state="collapsed")

OBJECTIVE_WEIGHTS = {
    "General analog assessment": {"visual_similarity": .25, "terrain_score": .20, "geology_score": .20, "climate_score": .20, "water_score": .15},
    "Rover mobility": {"visual_similarity": .10, "terrain_score": .40, "geology_score": .15, "climate_score": .20, "water_score": .15},
    "Geological investigation": {"visual_similarity": .10, "terrain_score": .15, "geology_score": .45, "climate_score": .15, "water_score": .15},
    "Water / ice resource study": {"visual_similarity": .10, "terrain_score": .10, "geology_score": .15, "climate_score": .15, "water_score": .50},
    "Extreme-environment research": {"visual_similarity": .15, "terrain_score": .15, "geology_score": .15, "climate_score": .40, "water_score": .15},
}
SCORE_LABELS = {"visual_similarity":"Visual similarity", "terrain_score":"Terrain compatibility", "geology_score":"Geological compatibility", "climate_score":"Climate compatibility", "water_score":"Water / ice compatibility"}
def parse_nullable_bool(series):
    def parse(value):
        if pd.isna(value) or str(value).strip().lower() in ("", "nan", "none", "unknown"):
            return pd.NA
        return str(value).strip().lower() in ("true", "1", "yes")
    return series.map(parse).astype("boolean")


@st.cache_data(show_spinner=False)
def load_data():
    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Recovered dataset missing: {DATA_FILE}")
    df = pd.read_csv(DATA_FILE)
    required = ["site_id","site_name","country","latitude","longitude","visual_similarity","terrain_score","geology_score","climate_score","water_score","data_coverage","protected_area","ecology_warning","summary"]
    for col in required:
        if col not in df.columns:
            df[col] = None
    for col in list(SCORE_LABELS) + ["data_coverage", "latitude", "longitude"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in list(SCORE_LABELS) + ["data_coverage"]:
        df[col] = df[col].clip(0, 100)
    df["protected_area"] = parse_nullable_bool(df["protected_area"])
    return df

st.markdown(r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&display=swap');
:root{--ice:#a8edff;--cyan:#5bdcf4;--muted:#a9bed2;--glass:rgba(16,31,52,.53);--line:rgba(174,224,255,.19)}
.stApp{background:radial-gradient(ellipse at 49% 20%,rgba(37,105,149,.28),transparent 38%),radial-gradient(ellipse at 8% 75%,rgba(37,89,142,.18),transparent 35%),linear-gradient(145deg,#050a13 0%,#081321 48%,#050912 100%);color:#edf7ff;font-family:'DM Sans',sans-serif}
.block-container{max-width:1780px;padding:1.0rem 1.35rem 2rem}
[data-testid="stHeader"]{background:rgba(5,10,19,.35)}
[data-testid="stToolbar"]{right:1rem}
h1,h2,h3,.terra-brand{font-family:'Space Grotesk',sans-serif;letter-spacing:-.035em;color:#f2f9ff}
[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(131,196,231,.13),rgba(14,29,49,.58));border:1px solid var(--line);border-radius:17px;padding:13px 16px;backdrop-filter:blur(22px);box-shadow:inset 0 1px rgba(255,255,255,.07),0 12px 35px rgba(0,0,0,.15)}
[data-testid="stMetricLabel"]{color:#9db9d0}[data-testid="stMetricValue"]{color:#effaff;font-family:'Space Grotesk',sans-serif}
[data-testid="stVerticalBlockBorderWrapper"]>div{border-color:var(--line)!important}
[data-testid="stExpander"]{background:rgba(14,29,48,.55);border:1px solid var(--line);border-radius:16px;backdrop-filter:blur(20px)}
.stButton>button,.stDownloadButton>button{border:1px solid rgba(124,224,255,.35);border-radius:999px;background:linear-gradient(120deg,rgba(65,173,207,.24),rgba(66,111,178,.22));color:#eafaff;font-weight:600;backdrop-filter:blur(18px);transition:all .2s}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#8beaff;background:rgba(68,170,210,.32);color:white;transform:translateY(-1px)}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,textarea{background:rgba(8,20,34,.72)!important;border-color:var(--line)!important;border-radius:12px!important;color:#eaf7ff!important}
[data-testid="stSidebar"]{background:rgba(7,15,27,.94);border-right:1px solid var(--line)}
.eyebrow{font-size:10px;letter-spacing:.23em;color:#80dff4;font-weight:700;text-transform:uppercase}
.brandline{display:flex;align-items:center;gap:12px}.brandmark{width:38px;height:38px;border-radius:13px;display:grid;place-items:center;background:linear-gradient(145deg,rgba(124,226,255,.28),rgba(79,125,190,.13));border:1px solid rgba(167,232,255,.32);box-shadow:0 0 26px rgba(76,193,232,.14);font-size:21px}
.glass-panel{background:linear-gradient(145deg,rgba(115,169,210,.13),rgba(12,27,46,.57));border:1px solid rgba(176,222,255,.19);border-radius:20px;padding:17px 18px;box-shadow:inset 0 1px 0 rgba(255,255,255,.08),0 18px 45px rgba(0,0,0,.19);backdrop-filter:blur(24px);-webkit-backdrop-filter:blur(24px)}
.glass-panel h3{font-size:15px;margin:0 0 7px}.muted{color:#9fb7cc;font-size:12px}.tiny{font-size:10px;color:#89a6bf;letter-spacing:.08em;text-transform:uppercase}.big-value{font-family:'Space Grotesk';font-size:25px;color:#e8faff;font-weight:600}.pill{display:inline-block;padding:4px 9px;border:1px solid rgba(119,219,245,.25);border-radius:999px;background:rgba(68,167,200,.12);color:#b8f2ff;font-size:10px;margin:2px 4px 2px 0}.rule{height:1px;background:linear-gradient(90deg,transparent,rgba(163,219,255,.25),transparent);margin:13px 0}
[data-testid="stPlotlyChart"]{border-radius:18px;overflow:hidden}.stCaption{color:#8ea9c2}
</style>
""", unsafe_allow_html=True)

# Header / command bar
h1,h2,h3=st.columns([1.25,2.2,1.0],vertical_alignment="center")
with h1:
    st.markdown('<div class="brandline"><div class="brandmark">ðŸŒ</div><div><div class="eyebrow">Planetary intelligence</div><div class="terra-brand" style="font-size:24px;font-weight:700">TERRA <span style="color:#71e5f8">AI</span></div></div></div>',unsafe_allow_html=True)
with h2:
    st.markdown('<div style="text-align:center"><div class="eyebrow">Earth analog discovery Â· mission research interface</div><div style="font-family:Space Grotesk;font-size:13px;color:#c3d8e9;margin-top:5px">Observe Earth. Understand other worlds.</div></div>',unsafe_allow_html=True)
with h3:
    target=st.selectbox("MISSION TARGET",["Mars","Moon"],label_visibility="collapsed",key="mission_target")
# Load planetary reference locations directly inside Streamlit.
# No external Flask server is required.
PLANETARY_POINTS = {
    "Mars": [
        {"id":"MARS-001","name":"Jezero Crater","latitude":18.38,"longitude":77.58,"status":"REFERENCE LOCATION"},
        {"id":"MARS-002","name":"Gale Crater","latitude":-5.40,"longitude":137.80,"status":"REFERENCE LOCATION"},
        {"id":"MARS-003","name":"Olympus Mons","latitude":18.65,"longitude":-133.80,"status":"REFERENCE LOCATION"},
        {"id":"MARS-004","name":"Valles Marineris","latitude":-13.90,"longitude":-59.20,"status":"REFERENCE LOCATION"},
        {"id":"MARS-005","name":"Hellas Planitia","latitude":-42.40,"longitude":70.50,"status":"REFERENCE LOCATION"},
        {"id":"MARS-006","name":"Elysium Planitia","latitude":4.50,"longitude":135.90,"status":"REFERENCE LOCATION"},
        {"id":"MARS-007","name":"Arcadia Planitia","latitude":46.00,"longitude":180.00,"status":"REFERENCE LOCATION"}
    ],
    "Moon": [
        {"id":"MOON-001","name":"Mare Tranquillitatis","latitude":8.50,"longitude":31.40,"status":"REFERENCE LOCATION"},
        {"id":"MOON-002","name":"Oceanus Procellarum","latitude":18.40,"longitude":-57.40,"status":"REFERENCE LOCATION"},
        {"id":"MOON-003","name":"Tycho Crater","latitude":-43.30,"longitude":-11.20,"status":"REFERENCE LOCATION"},
        {"id":"MOON-004","name":"Copernicus Crater","latitude":9.70,"longitude":-20.10,"status":"REFERENCE LOCATION"},
        {"id":"MOON-005","name":"Mare Imbrium","latitude":32.80,"longitude":-15.60,"status":"REFERENCE LOCATION"},
        {"id":"MOON-006","name":"South Pole-Aitken Basin","latitude":-53.00,"longitude":169.00,"status":"REFERENCE LOCATION"},
        {"id":"MOON-007","name":"Aristarchus Plateau","latitude":23.70,"longitude":-47.40,"status":"REFERENCE LOCATION"}
    ]
}

planetary_points = PLANETARY_POINTS[target]
st.session_state["planetary_reference_points"] = planetary_points
st.session_state["planetary_points_target"] = target

# Read the bundled scientific measurements directly.
measurement_file = BASE_DIR / "data" / "planetary_scientific_measurements.json"
try:
    with measurement_file.open("r", encoding="utf-8") as f:
        measurement_payload = json.load(f)
    planetary_measurements_data = [
        item for item in measurement_payload.get("measurements", [])
        if item.get("planet") == target
    ]
except (OSError, ValueError) as exc:
    planetary_measurements_data = []
    st.warning(f"Could not read planetary measurements: {exc}")


# Main controls in a compact glass toolbar
ctl1,ctl2,ctl3,ctl4=st.columns([1.35,1.5,1.35,1.0])
with ctl1: objective=st.selectbox("Research objective",list(OBJECTIVE_WEIGHTS),label_visibility="collapsed")
with ctl2: min_coverage=st.slider("Minimum data coverage",0,100,0,5,label_visibility="collapsed")
with ctl3: hide_protected=st.checkbox("Hide protected-area flags",value=False)
with ctl4: run_ranking=st.button("âœ¦ Run ranking",use_container_width=True)

# Service health indicators
try: b1_ok=requests.get(f"{BACKEND1_URL}/api/health",timeout=1.2).ok
except requests.RequestException: b1_ok=False
try: b2_ok=requests.get(f"{BACKEND2_URL}/api/health",timeout=1.2).ok
except requests.RequestException: b2_ok=False
status1="CONNECTED" if b1_ok else "LOCAL / OFFLINE"
status2="CONNECTED" if b2_ok else "LOCAL / OFFLINE"
st.markdown(f'<div style="display:flex;gap:8px;justify-content:flex-end;margin:2px 2px 12px"><span class="pill">â— IMAGERY + PDS Â· {status1}</span><span class="pill">â— SCIENCE ENGINE Â· {status2}</span><span class="pill">TARGET Â· {target.upper()}</span></div>',unsafe_allow_html=True)

try: df=load_data()
except Exception as exc: st.error(f"Candidate data could not be loaded: {exc}"); st.stop()
weights=OBJECTIVE_WEIGHTS[objective]

# Ranking service integration, preserving original scoring contract
ranking_context=(target,objective,(DATA_FILE.stat().st_mtime_ns,DATA_FILE.stat().st_size) if DATA_FILE.exists() else None)
if st.session_state.get("terra_ranking_context") != ranking_context:
    st.session_state.pop("terra_ranked_records",None)
if run_ranking:
    if not b2_ok: st.warning("Backend 2 is offline. Showing the clearly labelled local partial index.")
    else:
        try:
            payload=[]
            for _,r in df.iterrows():
                dims={bk:(None if pd.isna(r.get(fk)) else float(r.get(fk))) for fk,bk in [("visual_similarity","visual"),("terrain_score","terrain"),("geology_score","geology"),("climate_score","climate"),("water_score","water")]}
                protected = None if pd.isna(r.protected_area) else bool(r.protected_area)
                payload.append({"site_id":str(r.site_id),"site_name":str(r.site_name),"country":str(r.country),"latitude":None if pd.isna(r.latitude) else float(r.latitude),"longitude":None if pd.isna(r.longitude) else float(r.longitude),"dimensions":dims,"ecology":{"status":"review" if protected is True else "unknown","protected_area":protected,"notes":str(r.ecology_warning)}})
            bw={bk:weights[fk]*100 for fk,bk in [("visual_similarity","visual"),("terrain_score","terrain"),("geology_score","geology"),("climate_score","climate"),("water_score","water")]}
            rr=requests.post(f"{BACKEND2_URL}/api/rank",json={"target":target,"mission":objective,"weights":bw,"candidates":payload},timeout=40);rr.raise_for_status()
            result=rr.json()
            if not isinstance(result.get("candidates"),list): raise ValueError("Invalid ranking response")
            ranked_records=[]
            for item in result["candidates"]:
                dims=item.get("dimension_scores") or {}
                ecology=item.get("ecology") or {}
                missing=item.get("missing_dimensions") or []
                warnings=ecology.get("notes") or ""
                if ecology.get("status") != "pass":
                    warnings=(warnings + " " if warnings else "") + "Ecological gate not passed."

                ranked_records.append({
                    "site_id": item["site_id"],
                    "site_name": item["site_name"],
                    "country": item.get("country"),
                    "latitude": item.get("latitude"),
                    "longitude": item.get("longitude"),
                    "visual_similarity": dims.get("visual"),
                    "terrain_score": dims.get("terrain"),
                    "geology_score": dims.get("geology"),
                    "climate_score": dims.get("climate"),
                    "water_score": dims.get("water"),
                    "data_coverage": item.get("data_coverage"),
                    "protected_area": ecology.get("protected_area"),
                    "ecology_warning": warnings,
                    "summary": (
                        f"{item.get('ranking_index_label', 'Partial').title()} "
                        f"TERRA ranking index: {item.get('ranking_index')}. "
                        f"Coverage: {item.get('data_coverage')}%. "
                        f"Status: {item.get('recommendation_status')}."
                    ),
                    "analog_score": item.get("ranking_index"),
                    "ranking_index": item.get("ranking_index"),
                    "ranking_status": item.get("recommendation_status"),
                    "ecology_gate": ecology.get("status"),
                    "missing_dimensions": ";".join(missing),
                    "target": item.get("target"),
                    "mission": item.get("mission")
                })

            if len(ranked_records) != len(payload):
                raise ValueError("Backend result count does not match submitted candidates.")

            st.session_state["terra_ranked_records"] = ranked_records
            st.session_state["terra_ranking_context"] = ranking_context
        except (requests.RequestException,ValueError,KeyError) as exc: st.error(f"Scientific ranking failed: {exc}")
if st.session_state.get("terra_ranking_context")==ranking_context and st.session_state.get("terra_ranked_records"):
    df=pd.DataFrame(st.session_state["terra_ranked_records"])
    for c in list(SCORE_LABELS)+["data_coverage","analog_score"]:
        if c in df: df[c]=pd.to_numeric(df[c],errors="coerce").clip(0,100)
    df["protected_area"]=parse_nullable_bool(df["protected_area"])
    ranked_live=True
else: ranked_live=False
if not ranked_live:
    def partial_score(r):
        available={k:w for k,w in weights.items() if pd.notna(r.get(k))}; denom=sum(available.values())
        return sum(float(r[k])*w for k,w in available.items())/denom if denom else float("nan")
    df["analog_score"]=df.apply(partial_score,axis=1)
    st.caption("LOCAL PARTIAL INDEX Â· illustrative until the scientific backend returns an evidence-backed ranking")

filtered=df[df["data_coverage"].fillna(0)>=min_coverage].copy()
if hide_protected: filtered=filtered[filtered["protected_area"].ne(True).fillna(True)]
filtered=filtered.sort_values("analog_score",ascending=False,na_position="last").copy()
filtered["rank"]=filtered["analog_score"].rank(method="min",ascending=False)

# Main three-panel mission dashboard
left,center,right=st.columns([.88,1.95,.92],gap="medium")
with left:
    st.markdown(
        '<div class="glass-panel"><div class="eyebrow">Field intelligence</div>'
        '<h3>Candidate sites</h3>'
        '<div class="muted">Assessment status ? validated scores only</div></div>',
        unsafe_allow_html=True
    )
    if len(filtered):
        for _,r in filtered.head(3).iterrows():
            assessed = pd.notna(r.analog_score)
            status = f"RANK {int(r['rank']):02d}" if assessed else "DISCOVERY CANDIDATE"
            score = (
                f'<span class="big-value">{r.analog_score:.1f}'
                '<span style="font-size:11px;color:#89a9c2"> /100</span></span>'
                if assessed else
                '<span class="big-value" style="font-size:17px">PENDING</span>'
            )
            location = (
                f"{r.latitude:.2f}?, {r.longitude:.2f}?"
                if pd.notna(r.latitude) and pd.notna(r.longitude)
                else "Coordinates unavailable"
            )
            country = str(r.country) if pd.notna(r.country) else "Country unverified"
            st.markdown(
                f'<div class="glass-panel" style="margin-top:9px;padding:13px">'
                f'<div style="display:flex;justify-content:space-between">'
                f'<span class="tiny">{r.site_id}</span>'
                f'<span class="pill">{status}</span></div>'
                f'<div style="font-weight:650;color:#eaf7ff;margin:5px 0">{r.site_name}</div>'
                f'<div class="muted">{country} ? {location}</div>'
                f'<div style="display:flex;justify-content:space-between;align-items:end;margin-top:10px">'
                f'<span class="tiny">{"Analog index" if assessed else "Suitability assessment"}</span>'
                f'{score}</div></div>',
                unsafe_allow_html=True
            )
    else:
        st.info("No candidates match current filters.")
    st.markdown(
        f'<div class="glass-panel"><div class="eyebrow">Planetary reference locations</div><h3>{target} reference points</h3><div class="muted">{len(planetary_points)} named landmarks loaded</div></div>',
        unsafe_allow_html=True
    )
    st.markdown('<div class="glass-panel" style="margin-top:10px"><div class="eyebrow">Mission objective</div><div style="font-size:13px;color:#d9eaf6;margin-top:6px">'+objective+'</div><div class="rule"></div><div class="muted">Protected-area flags are separate safeguards and are never cancelled by a high analog score.</div></div>',unsafe_allow_html=True)

with center:
    st.markdown('<div style="display:flex;justify-content:space-between;align-items:center;padding:4px 5px 0"><div><div class="eyebrow">Orbital view Â· interactive globe</div><div style="font-family:Space Grotesk;font-size:19px;color:#eefaff;font-weight:600">Earth analog field</div></div><span class="pill">DRAG TO ROTATE Â· SCROLL TO ZOOM</span></div>',unsafe_allow_html=True)
    globe = go.Figure(go.Scattergeo(
        lon=[point["longitude"] for point in planetary_points],
        lat=[point["latitude"] for point in planetary_points],
        text=[point["name"] for point in planetary_points],
        customdata=[[point["id"], point["status"]] for point in planetary_points],
        mode="markers",
        marker=dict(size=10, color="#ffb347", line=dict(width=1, color="#fff0cf")),
        name=f"{target} reference locations",
        hovertemplate="<b>%{text}</b><br>Latitude: %{lat:.2f}?<br>Longitude: %{lon:.2f}?<br>ID: %{customdata[0]}<br>%{customdata[1]}<extra></extra>"
    ))

    globe.update_geos(
        projection_type="orthographic",
        showland=True,
        landcolor="#25465d",
        showocean=True,
        oceancolor="#071a2b",
        showcoastlines=True,
        coastlinecolor="#8fdcff"
    )

    globe.update_layout(
        height=510,
        margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        geo=dict(bgcolor="rgba(0,0,0,0)")
    )

    st.plotly_chart(
        globe,
        use_container_width=True,
        config={"displayModeBar": False},
        key="terra_interactive_globe"
    )
    st.caption(f"Showing {len(planetary_points)} named {target} reference locations. Hover over markers for details. The base globe is illustrative, not a surface map of {target}.")

    with st.expander("??? Topographic measurements ? NASA", expanded=True):
        if planetary_measurements_data:
            measurement_df = pd.DataFrame(planetary_measurements_data)
            display_columns = [
                "site_name", "elevation", "elevation_unit",
                "reference_surface", "grid_resolution"
            ]
            measurement_df = measurement_df[
                [c for c in display_columns if c in measurement_df.columns]
            ]
            st.dataframe(
                measurement_df,
                use_container_width=True,
                hide_index=True
            )
            st.caption(
                "Sources: NASA MGS MOLA (Mars) and NASA LOLA (Moon). "
                "Grid-cell elevations, not site suitability scores. "
                "Mars values reference the areoid; Moon values reference "
                "the 1737.4 km lunar reference radius."
            )
        else:
            st.info("No planetary elevation measurements are currently available.")

    k1,k2,k3=st.columns(3)
    k1.metric("Candidates in view",len(filtered));k2.metric("Best analog index",f"{filtered.analog_score.max():.1f}" if len(filtered) and pd.notna(filtered.analog_score.max()) else "â€”");k3.metric("Evidence coverage",f"{filtered.data_coverage.mean():.0f}%" if len(filtered) and filtered.data_coverage.notna().any() else "â€”")

with right:
    st.markdown('<div class="glass-panel"><div class="eyebrow">Mission telemetry</div><h3>Research parameters</h3><div class="rule"></div><div class="tiny">Target body</div><div class="big-value">'+target+'</div><div class="rule"></div><div class="tiny">Research mode</div><div style="font-size:13px;color:#d9eaf6;margin-top:4px">'+objective+'</div><div class="rule"></div><div class="tiny">Active candidate set</div><div class="big-value">'+str(len(filtered))+'</div><div class="muted">sites currently visible</div></div>',unsafe_allow_html=True)
    if len(filtered):
        top=filtered.iloc[0]
        st.markdown('<div class="glass-panel" style="margin-top:10px"><div class="eyebrow">Selected signal</div><h3>Leading analog</h3><div style="font-size:15px;color:#effaff;font-weight:650">'+str(top.site_name)+'</div><div class="muted">'+str(top.country)+'</div><div style="font-family:Space Grotesk;font-size:34px;color:#9cecff;margin:9px 0">'+(f"{top.analog_score:.1f}" if pd.notna(top.analog_score) else "â€”")+'<span style="font-size:12px;color:#9bb5c9"> / 100</span></div><div class="muted">'+str(top.ecology_warning)+'</div></div>',unsafe_allow_html=True)
    st.markdown('<div class="glass-panel" style="margin-top:10px"><div class="eyebrow">Scoring model</div><h3>Weighted dimensions</h3></div>',unsafe_allow_html=True)
    weight_df=pd.DataFrame({"Dimension":[SCORE_LABELS[k] for k in weights],"Weight":[v*100 for v in weights.values()]})
    wf=px.bar(weight_df,x="Weight",y="Dimension",orientation="h",range_x=[0,55],text="Weight")
    wf.update_traces(marker_color="#65cfe5",texttemplate="%{text:.0f}%",textposition="outside")
    wf.update_layout(height=245,margin={"l":0,"r":22,"t":5,"b":5},paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color="#d5eafa",xaxis={"showgrid":False,"visible":False},yaxis={"showgrid":False,"title":None},showlegend=False)
    st.plotly_chart(wf,use_container_width=True,config={"displayModeBar":False})

# Bottom glass modules, analogous to launch + category cards in reference
st.markdown('<div class="rule"></div>',unsafe_allow_html=True)
bottom1,bottom2,bottom3=st.columns([1.05,1.3,1.1],gap="medium")
with bottom1:
    st.markdown(
        '<div class="glass-panel"><div class="eyebrow">NASA Planetary Data System</div>'
        '<h3>MRO science archive</h3>'
        '<div class="muted">Search verified Mars Reconnaissance Orbiter observational products.</div></div>',
        unsafe_allow_html=True
    )

    if st.button("Search MRO PDS products", use_container_width=True, key="pds_mro_search"):
        try:
            pds_url = "https://pds.nasa.gov/api/search/1/products"
            mission_lid = "urn:nasa:pds:context:investigation:mission.mars_reconnaissance_orbiter"
            params = {
                "q": '((product_class eq "Product_Observational") and '
                     '(ref_lid_investigation eq "' + mission_lid + '"))',
                "limit": 30
            }
            response = requests.get(
                pds_url,
                params=params,
                headers={"Accept": "application/json"},
                timeout=45
            )
            response.raise_for_status()
            payload = response.json()

            products = []
            for item in payload.get("data", []):
                investigations = [
                    entry.get("id") for entry in item.get("investigations", [])
                ]
                if mission_lid in investigations:
                    products.append(item)

            st.session_state["pds_mro_products"] = products[:6]
            st.session_state["pds_mro_checked"] = True

        except (requests.RequestException, ValueError) as exc:
            st.error(f"NASA PDS search unavailable: {exc}")

    if st.session_state.get("pds_mro_checked"):
        products = st.session_state.get("pds_mro_products", [])
        st.markdown(f"**{len(products)} verified MRO records returned**")

        if not products:
            st.info("No matching MRO products were returned. Try again later.")
        for item in products:
            st.markdown(f"**{item.get('title') or 'PDS observational product'}**")
            st.caption(f"Product ID: {item.get('id') or 'Not supplied'}")

            targets = [x.get("id", "").split(":")[-1] for x in item.get("targets", [])]
            if targets:
                st.caption("Targets: " + ", ".join(targets[:4]))

            label_url = item.get("metadata", {}).get("label_url")
            if isinstance(label_url, str) and label_url.startswith("https://"):
                st.markdown(f"[Open PDS product label]({label_url})")

        st.caption("Records are filtered against the exact MRO investigation identifier. Metadata discovery does not itself validate scientific suitability.")

with bottom2:
    st.markdown('<div class="glass-panel"><div class="eyebrow">Earth observation</div><h3>NASA imagery + CLIP matching</h3><div class="muted">Search imagery references and optionally compare an image against target-specific prompts.</div></div>',unsafe_allow_html=True)
    query=st.text_input("Imagery search",value="Atacama Desert",label_visibility="collapsed",key="nasa_img_q")
    if st.button("Search NASA Images",use_container_width=True):
        try:
            ir = requests.get(
                "https://images-api.nasa.gov/search",
                params={"q": query, "media_type": "image", "page_size": 6},
                timeout=45
            )
            ir.raise_for_status()
            nasa_items = ir.json().get("collection", {}).get("items", [])
            nasa_results = []

            for result in nasa_items:
                metadata = (result.get("data") or [{}])[0]
                links = result.get("links") or []
                preview = next(
                    (link.get("href") for link in links if link.get("rel") == "preview"),
                    None
                )
                if preview:
                    nasa_results.append({
                        "title": metadata.get("title", "NASA image"),
                        "preview_url": preview
                    })

            st.session_state["nasa_img_results"] = nasa_results
            if not nasa_results:
                st.info("No NASA images found. Try another search.")
        except requests.RequestException as exc:
            st.error(f"NASA Images search failed: {exc}")
    imgs=st.session_state.get("nasa_img_results",[])
    if imgs:
        imgcols=st.columns(min(3,len(imgs)))
        for col,item in zip(imgcols,imgs[:3]):
            with col:
                if item.get("preview_url"): st.image(item["preview_url"],use_container_width=True)
                st.caption(str(item.get("title") or "NASA image")[:75])
    upload=st.file_uploader("Image for CLIP analysis",type=["jpg","jpeg","png","webp"],label_visibility="collapsed")
    if upload and st.button("Analyze with CLIP",use_container_width=True):
        try:
            # The backend must be able to access the uploaded image; use multipart upload if supported.
            cr=requests.post(f"{BACKEND1_URL}/api/clip/score",files={"image":(upload.name,upload.getvalue(),upload.type)},data={"target":target},timeout=180)
            if cr.ok: st.session_state["clip_result"]=cr.json()
            else: st.warning("This backend currently expects an image_path. Shared image-upload transport needs to be enabled before remote CLIP analysis.")
        except requests.RequestException as exc: st.error(f"CLIP request failed: {exc}")
    if st.session_state.get("clip_result"):
        st.dataframe(pd.DataFrame(st.session_state["clip_result"].get("matches",[])),use_container_width=True,hide_index=True)
with bottom3:
    st.markdown('<div class="glass-panel"><div class="eyebrow">Candidate intelligence</div><h3>Ranked site comparison</h3><div class="muted">Compare the current candidate set across five assessment dimensions.</div></div>',unsafe_allow_html=True)
    if len(filtered):
        comp=filtered.head(6).copy()
        cf=px.bar(comp,x="site_name",y="analog_score",range_y=[0,100],color="analog_score",color_continuous_scale=[[0,"#365a7b"],[.55,"#4ba9c6"],[1,"#d5f7ff"]])
        cf.update_layout(height=235,margin={"l":0,"r":0,"t":8,"b":5},paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",font_color="#d5eafa",xaxis={"tickangle":-25,"title":None,"showgrid":False},yaxis={"title":None,"showgrid":False},coloraxis_showscale=False)
        st.plotly_chart(cf,use_container_width=True,config={"displayModeBar":False})
    else: st.info("No candidate data to compare.")

# Full candidate detail and transparent formula
with st.expander("Candidate detail Â· evidence, safeguards and score breakdown"):
    if len(filtered):
        choices=filtered.site_id.astype(str).tolist();chosen=st.selectbox("Select candidate",choices,format_func=lambda x:f"{x} Â· {filtered.loc[filtered.site_id.astype(str)==x,'site_name'].iloc[0]}")
        r=filtered.loc[filtered.site_id.astype(str)==chosen].iloc[0]
        st.subheader(str(r.site_name));st.write(r.summary);st.write(f"Coordinates: {r.latitude}, {r.longitude} Â· {r.country}")
        breakdown=pd.DataFrame({"Dimension":[SCORE_LABELS[k] for k in weights],"Score":[r.get(k) for k in weights],"Weight":[v*100 for v in weights.values()]})
        st.dataframe(breakdown,use_container_width=True,hide_index=True)
        st.metric("Objective-weighted analog index",f"{r.analog_score:.1f}/100" if pd.notna(r.analog_score) else "Not calculable")
        if pd.notna(r.protected_area) and bool(r.protected_area): st.error("Protected-area flag: this score is not permission to visit or conduct fieldwork.")
        st.warning(str(r.ecology_warning))
    st.markdown("**Weighted score formula**")
    st.latex(r"S = \frac{\sum_{i\in A} w_i x_i}{\sum_{i\in A} w_i}")
    st.caption("A = dimensions with available measured scores; xáµ¢ = dimension score; wáµ¢ = configured weight. Missing dimensions are excluded and remaining weights are renormalized. This is a ranking index, not a probability or proof of scientific equivalence. Ecological safeguards are assessed separately.")
    for k,v in weights.items(): st.write(f"{SCORE_LABELS[k]}: **{v:.0%}**")

with st.expander("Mission-specific limitations"):
    limits=( ["Earth has a much thicker atmosphere than Mars; pressure and atmospheric composition are not reproduced.","Earth analogs do not reproduce Martian surface radiation exposure or gravity.","Dust behavior, electrostatics and weathering may differ substantially."] if target=="Mars" else ["Earth analogs do not reproduce lunar vacuum, gravity or radiation exposure.","Earth's atmosphere and active hydrological cycle differ fundamentally from the lunar surface.","Thermal cycling and abrasive lunar dust behavior require separate analysis."] )
    for item in limits: st.write("â€¢ "+item)

if len(filtered):
    export=[c for c in ["rank","site_id","site_name","country","latitude","longitude","analog_score","visual_similarity","terrain_score","geology_score","climate_score","water_score","data_coverage","protected_area","ecology_warning"] if c in filtered.columns]
    st.download_button("â†“ Export candidate results Â· CSV",filtered[export].to_csv(index=False).encode("utf-8"),"terra_ai_candidate_results.csv","text/csv")
st.markdown('<div style="text-align:center;padding:22px 0 4px;color:#68859e;font-size:10px;letter-spacing:.12em">TERRA AI Â· PLANETARY ANALOG RESEARCH Â· EVIDENCE BEFORE INFERENCE</div>',unsafe_allow_html=True)



