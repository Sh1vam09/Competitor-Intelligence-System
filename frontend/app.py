<<<<<<< HEAD
"""
Streamlit Frontend for the Competitor Intelligence Engine.

Provides an interactive dashboard with:
    - URL input for analysis
    - Real-time status tracking
    - Company profile display
    - Competitors list
    - Comparative charts
    - PDF report download
"""

import time
import json

import requests
import streamlit as st

# ── Page Configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Competitor Intelligence Engine",
    page_icon="CI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API base URL
API_BASE = "http://localhost:8000"

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .main-header h1 {
        color: #e0e0ff;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #a0a0cc;
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
    }

    .metric-card {
        background: linear-gradient(135deg, #f8f9ff 0%, #e8ecff 100%);
        border: 1px solid #d0d4ff;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-card h3 {
        color: #16213e;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 0 0 0.3rem 0;
    }
    .metric-card .value {
        color: #0f3460;
        font-size: 1.6rem;
        font-weight: 700;
    }

    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-pending { background: #fff3cd; color: #856404; }
    .status-running { background: #cce5ff; color: #004085; }
    .status-completed { background: #d4edda; color: #155724; }
    .status-failed { background: #f8d7da; color: #721c24; }

    .competitor-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        transition: box-shadow 0.2s;
    }
    .competitor-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    .section-divider {
        border-top: 2px solid #0f3460;
        margin: 2rem 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
    <h1>AI Competitor Intelligence Engine</h1>
    <p>Powered by Groq Llama • LLM Discovery • FAISS Semantic Search</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Settings")
    api_url = st.text_input("API URL", value=API_BASE, help="Backend API endpoint")
    API_BASE = api_url.rstrip("/")

    st.markdown("---")
    st.markdown("### How It Works")
    st.markdown("""
    1. **Enter** a website URL
    2. **Wait** while the engine crawls & analyzes
    3. **View** business profile & competitors
    4. **Download** the full PDF report
    """)

    st.markdown("---")
    st.markdown("### Pipeline Steps")
    st.markdown("""
    - Adaptive web crawling
    - Text extraction & chunking
    - Visual brand analysis (Llama Vision)
    - Business profile extraction
    - Semantic embeddings (FAISS)
    - Competitor discovery (LLM + DuckDuckGo)
    - Comparative intelligence
    - PDF report generation
    """)


# ── Session State ──────────────────────────────────────────────────────────────
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "company_id" not in st.session_state:
    st.session_state.company_id = None
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


# ── URL Input ──────────────────────────────────────────────────────────────────
st.markdown("### Analyze a Website")

col1, col2, col3 = st.columns([4, 1, 1])
with col1:
    url_input = st.text_input(
        "Website URL",
        placeholder="https://example.com",
        label_visibility="collapsed",
    )
with col2:
    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)
with col3:
    reset_btn = st.button("Reset", use_container_width=True)

if reset_btn:
    st.session_state.job_id = None
    st.session_state.company_id = None
    st.session_state.analysis_done = False
    st.rerun()

if analyze_btn and url_input:
    # Client-side URL validation
    clean_url = url_input.strip()
    if not clean_url:
        st.error("Please enter a URL.")
    elif "." not in clean_url:
        st.error("Please enter a valid domain (e.g., example.com).")
    else:
        try:
            resp = requests.post(
                f"{API_BASE}/analyze",
                json={"url": clean_url},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.job_id = data["job_id"]
                st.session_state.analysis_done = False
                st.session_state.company_id = None
                st.success(f"Analysis started! Job ID: `{data['job_id']}`")
            elif resp.status_code == 429:
                st.warning("An analysis is already in progress. Please wait for it to complete.")
            elif resp.status_code == 422:
                detail = resp.json().get("detail", [{}])
                msg = detail[0].get("msg", "Invalid URL") if isinstance(detail, list) else str(detail)
                st.error(f"Invalid URL: {msg}")
            else:
                st.error(f"Failed to start analysis: {resp.text}")
        except requests.ConnectionError:
            st.error("Cannot connect to the API. Is the backend running?")
        except Exception as e:
            st.error(f"Error: {e}")

# ── Status Polling ─────────────────────────────────────────────────────────────
if st.session_state.job_id and not st.session_state.analysis_done:
    st.markdown("---")
    st.markdown("### Analysis Progress")

    status_placeholder = st.empty()
    progress_bar = st.progress(0)

    polling = True
    step_count = 0
    max_poll_time = 900  # 15 minutes max
    poll_start = time.time()
    while polling:
        if time.time() - poll_start > max_poll_time:
            status_placeholder.error("**Timeout:** Analysis took too long. Please try again.")
            polling = False
            break

        try:
            resp = requests.get(
                f"{API_BASE}/status/{st.session_state.job_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                status = resp.json()
                job_status = status["status"]
                progress_text = status.get("progress", "")

                if job_status == "running":
                    step_count = min(step_count + 5, 90)
                    progress_bar.progress(step_count)
                    status_placeholder.info(f"**Running:** {progress_text}")
                elif job_status == "completed":
                    progress_bar.progress(100)
                    status_placeholder.success(f"**Complete:** {progress_text}")
                    st.session_state.company_id = status.get("company_id")
                    st.session_state.analysis_done = True
                    polling = False
                elif job_status == "failed":
                    progress_bar.progress(0)
                    status_placeholder.error(f"**Failed:** {status.get('error', 'Unknown')}")
                    polling = False
                else:
                    status_placeholder.warning(f"**Pending:** {progress_text}")

            time.sleep(3)
        except Exception as e:
            status_placeholder.error(f"Polling error: {e}")
            time.sleep(5)


# ── Results Display ────────────────────────────────────────────────────────────
if st.session_state.analysis_done and st.session_state.company_id:
    company_id = st.session_state.company_id

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Company Profile ────────────────────────────────────────────────────
    try:
        resp = requests.get(f"{API_BASE}/company/{company_id}", timeout=10)
        if resp.status_code == 200:
            company = resp.json()

            st.markdown(f"### {company.get('name', 'Company Profile')}")

            profile = company.get("json_profile", {})
            visual = company.get("visual_profile", {})

            # Metrics row
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                st.markdown(f"""<div class="metric-card">
                    <h3>Industry</h3>
                    <div class="value" style="font-size:1rem;">{profile.get('industry', 'N/A')}</div>
                </div>""", unsafe_allow_html=True)
            with mcol2:
                st.markdown(f"""<div class="metric-card">
                    <h3>CTA Score</h3>
                    <div class="value">{profile.get('CTA_aggressiveness_score', 'N/A')}</div>
                </div>""", unsafe_allow_html=True)
            with mcol3:
                st.markdown(f"""<div class="metric-card">
                    <h3>Design Modernity</h3>
                    <div class="value">{visual.get('design_modernity_score', 'N/A')}</div>
                </div>""", unsafe_allow_html=True)
            with mcol4:
                st.markdown(f"""<div class="metric-card">
                    <h3>Trust Score</h3>
                    <div class="value">{visual.get('trust_signal_score', 'N/A')}</div>
                </div>""", unsafe_allow_html=True)

            st.markdown("")

            # Profile details in tabs
            tab1, tab2, tab3 = st.tabs(["Business Profile", "Visual Profile", "DOM Features"])

            with tab1:
                if profile:
                    for key, value in profile.items():
                        if isinstance(value, list):
                            st.markdown(f"**{key.replace('_', ' ').title()}:**")
                            for item in value:
                                st.markdown(f"  - {item}")
                        else:
                            st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
                else:
                    st.info("No profile data available.")

            with tab2:
                if visual:
                    for key, value in visual.items():
                        st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
                else:
                    st.info("No visual profile data available.")

            with tab3:
                dom = company.get("dom_features", {})
                if dom:
                    col_a, col_b = st.columns(2)
                    items = list(dom.items())
                    mid = len(items) // 2
                    with col_a:
                        for k, v in items[:mid]:
                            st.metric(k.replace("_", " ").title(), str(v))
                    with col_b:
                        for k, v in items[mid:]:
                            st.metric(k.replace("_", " ").title(), str(v))
                else:
                    st.info("No DOM features available.")

    except Exception as e:
        st.error(f"Error loading company profile: {e}")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Competitors ────────────────────────────────────────────────────────
    try:
        resp = requests.get(f"{API_BASE}/company/{company_id}/competitors", timeout=10)
        if resp.status_code == 200:
            comp_data = resp.json()
            local_competitors = comp_data.get("local_competitors", [])
            global_competitors = comp_data.get("global_competitors", [])
            total = len(local_competitors) + len(global_competitors)

            st.markdown(f"### Discovered Competitors ({total})")

            def _render_competitor_list(competitors, label):
                """Render a list of competitors with chart and expanders."""
                if not competitors:
                    st.info(f"No {label} competitors discovered.")
                    return

                # Similarity chart
                names = [c.get("name", "Unknown") for c in competitors]
                scores = [c.get("similarity_score", 0) for c in competitors]
                chart_data = {"Competitor": names, "Similarity Score": scores}
                st.bar_chart(chart_data, x="Competitor", y="Similarity Score", horizontal=True)

                # Competitor details
                for comp in competitors:
                    with st.expander(
                        f"{comp.get('name', 'Unknown')} — "
                        f"Similarity: {comp.get('similarity_score', 0):.2f}"
                    ):
                        st.markdown(f"**URL:** {comp.get('url', 'N/A')}")
                        comp_profile = comp.get("json_profile", {})
                        if comp_profile:
                            for key, value in comp_profile.items():
                                if isinstance(value, list):
                                    st.markdown(f"**{key.replace('_', ' ').title()}:** {', '.join(str(v) for v in value)}")
                                else:
                                    st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")

            tab_local, tab_global = st.tabs([
                f"🇮🇳 Local Competitors ({len(local_competitors)})",
                f"🌍 Global Competitors ({len(global_competitors)})",
            ])

            with tab_local:
                _render_competitor_list(local_competitors, "local")

            with tab_global:
                _render_competitor_list(global_competitors, "global")

    except Exception as e:
        st.error(f"Error loading competitors: {e}")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Report Download ────────────────────────────────────────────────────
    st.markdown("### Intelligence Report")

    col_r1, col_r2 = st.columns(2)

    with col_r1:
        try:
            resp = requests.get(
                f"{API_BASE}/company/{company_id}/report/json",
                timeout=10,
            )
            if resp.status_code == 200:
                report_data = resp.json()
                report_content = report_data.get("report", {})

                if report_content:
                    st.markdown("**Comparative Analysis Highlights:**")
                    for key in ["positioning_comparison", "pricing_comparison",
                                "market_saturation_estimate"]:
                        value = report_content.get(key)
                        if value:
                            label = key.replace("_", " ").title()
                            if isinstance(value, dict):
                                st.markdown(f"**{label}:**")
                                st.json(value)
                            else:
                                st.markdown(f"**{label}:** {value}")
        except Exception as e:
            st.warning(f"Could not load report data: {e}")

    with col_r2:
        st.markdown("**Download Full Report**")
        download_url = f"{API_BASE}/company/{company_id}/report"
        st.markdown(
            f'<a href="{download_url}" target="_blank">'
            f'<button style="background:#0f3460;color:white;border:none;'
            f'padding:12px 24px;border-radius:8px;cursor:pointer;'
            f'font-size:1rem;font-weight:600;width:100%;">'
            f'Download PDF Report</button></a>',
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.info("The PDF report includes all sections: Executive Summary, "
                "Business Profile, Visual Analysis, Competitor Profiles, "
                "Comparison Tables, and Strategic Recommendations.")


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<p style="text-align:center;color:#888;font-size:0.8rem;">'
    'AI-Powered Competitor Intelligence Engine • Groq Llama + FAISS'
    '</p>',
    unsafe_allow_html=True,
)
=======
"""
Streamlit Frontend for the Competitor Intelligence Engine.

Provides an interactive dashboard with:
    - URL input for analysis
    - Real-time status tracking
    - Company profile display
    - Competitors list
    - Comparative charts
    - PDF report download
"""

import time
import json

import requests
import streamlit as st

# ── Page Configuration ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Competitor Intelligence Engine",
    page_icon="CI",
    layout="wide",
    initial_sidebar_state="expanded",
)

# API base URL
API_BASE = "http://localhost:8000"

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    .stApp {
        font-family: 'Inter', sans-serif;
    }

    .main-header {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        padding: 2rem 2rem;
        border-radius: 16px;
        margin-bottom: 2rem;
        text-align: center;
    }
    .main-header h1 {
        color: #e0e0ff;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
    }
    .main-header p {
        color: #a0a0cc;
        font-size: 1rem;
        margin: 0.5rem 0 0 0;
    }

    .metric-card {
        background: linear-gradient(135deg, #f8f9ff 0%, #e8ecff 100%);
        border: 1px solid #d0d4ff;
        border-radius: 12px;
        padding: 1.2rem;
        text-align: center;
    }
    .metric-card h3 {
        color: #16213e;
        font-size: 0.85rem;
        font-weight: 500;
        margin: 0 0 0.3rem 0;
    }
    .metric-card .value {
        color: #0f3460;
        font-size: 1.6rem;
        font-weight: 700;
    }

    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .status-pending { background: #fff3cd; color: #856404; }
    .status-running { background: #cce5ff; color: #004085; }
    .status-completed { background: #d4edda; color: #155724; }
    .status-failed { background: #f8d7da; color: #721c24; }

    .competitor-card {
        background: white;
        border: 1px solid #e0e0e0;
        border-radius: 12px;
        padding: 1.2rem;
        margin-bottom: 0.8rem;
        transition: box-shadow 0.2s;
    }
    .competitor-card:hover {
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }

    .section-divider {
        border-top: 2px solid #0f3460;
        margin: 2rem 0;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown(
    """
<div class="main-header">
    <h1>AI Competitor Intelligence Engine</h1>
    
</div>
""",
    unsafe_allow_html=True,
)

# ── Sidebar ────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Settings")
    api_url = st.text_input("API URL", value=API_BASE, help="Backend API endpoint")
    API_BASE = api_url.rstrip("/")

    st.markdown("---")
    st.markdown("### How It Works")
    st.markdown("""
    1. **Enter** a website URL
    2. **Wait** while the engine analyzes
    3. **View** business profile & competitors
    4. **Download** the full PDF report
    """)


# ── Session State ──────────────────────────────────────────────────────────────
if "job_id" not in st.session_state:
    st.session_state.job_id = None
if "company_id" not in st.session_state:
    st.session_state.company_id = None
if "analysis_done" not in st.session_state:
    st.session_state.analysis_done = False


# ── URL Input ──────────────────────────────────────────────────────────────────
st.markdown("### Analyze a Website")

col1, col2, col3 = st.columns([4, 1, 1])
with col1:
    url_input = st.text_input(
        "Website URL",
        placeholder="https://example.com",
        label_visibility="collapsed",
    )
with col2:
    analyze_btn = st.button("Analyze", type="primary", use_container_width=True)
with col3:
    reset_btn = st.button("Reset", use_container_width=True)

if reset_btn:
    st.session_state.job_id = None
    st.session_state.company_id = None
    st.session_state.analysis_done = False
    st.rerun()

if analyze_btn and url_input:
    # Client-side URL validation
    clean_url = url_input.strip()
    if not clean_url:
        st.error("Please enter a URL.")
    elif "." not in clean_url:
        st.error("Please enter a valid domain (e.g., example.com).")
    else:
        try:
            resp = requests.post(
                f"{API_BASE}/analyze",
                json={"url": clean_url},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.job_id = data["job_id"]
                st.session_state.analysis_done = False
                st.session_state.company_id = None
                st.success(f"Analysis started! Job ID: `{data['job_id']}`")
            elif resp.status_code == 429:
                st.warning(
                    "An analysis is already in progress. Please wait for it to complete."
                )
            elif resp.status_code == 422:
                detail = resp.json().get("detail", [{}])
                msg = (
                    detail[0].get("msg", "Invalid URL")
                    if isinstance(detail, list)
                    else str(detail)
                )
                st.error(f"Invalid URL: {msg}")
            else:
                st.error(f"Failed to start analysis: {resp.text}")
        except requests.ConnectionError:
            st.error("Cannot connect to the API. Is the backend running?")
        except Exception as e:
            st.error(f"Error: {e}")

# ── Status Polling ─────────────────────────────────────────────────────────────
if st.session_state.job_id and not st.session_state.analysis_done:
    st.markdown("---")
    st.markdown("### Analysis Progress")

    status_placeholder = st.empty()
    progress_bar = st.progress(0)

    polling = True
    step_count = 0
    max_poll_time = 3600  # 1 hour max
    poll_start = time.time()
    while polling:
        if time.time() - poll_start > max_poll_time:
            status_placeholder.error(
                "**Timeout:** Analysis took too long. Please try again."
            )
            polling = False
            break

        try:
            resp = requests.get(
                f"{API_BASE}/status/{st.session_state.job_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                status = resp.json()
                job_status = status["status"]
                progress_text = status.get("progress", "")

                if job_status == "running":
                    step_count = min(step_count + 5, 90)
                    progress_bar.progress(step_count)
                    status_placeholder.info(f"**Running:** {progress_text}")
                elif job_status == "completed":
                    progress_bar.progress(100)
                    status_placeholder.success(f"**Complete:** {progress_text}")
                    st.session_state.company_id = status.get("company_id")
                    st.session_state.analysis_done = True
                    polling = False
                elif job_status == "failed":
                    progress_bar.progress(0)
                    status_placeholder.error(
                        f"**Failed:** {status.get('error', 'Unknown')}"
                    )
                    polling = False
                else:
                    status_placeholder.warning(f"**Pending:** {progress_text}")

            time.sleep(3)
        except Exception as e:
            status_placeholder.error(f"Polling error: {e}")
            time.sleep(5)


# ── Results Display ────────────────────────────────────────────────────────────
if st.session_state.analysis_done and st.session_state.company_id:
    company_id = st.session_state.company_id

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Company Profile ────────────────────────────────────────────────────
    try:
        resp = requests.get(f"{API_BASE}/company/{company_id}", timeout=10)
        if resp.status_code == 200:
            company = resp.json()

            st.markdown(f"### {company.get('name', 'Company Profile')}")

            profile = company.get("json_profile", {})
            visual = company.get("visual_profile", {})

            # Metrics row
            mcol1, mcol2, mcol3, mcol4 = st.columns(4)
            with mcol1:
                st.markdown(
                    f"""<div class="metric-card">
                    <h3>Industry</h3>
                    <div class="value" style="font-size:1rem;">{profile.get("industry", "N/A")}</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with mcol2:
                st.markdown(
                    f"""<div class="metric-card">
                    <h3>CTA Score</h3>
                    <div class="value">{profile.get("CTA_aggressiveness_score", "N/A")}</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with mcol3:
                st.markdown(
                    f"""<div class="metric-card">
                    <h3>Design Modernity</h3>
                    <div class="value">{visual.get("design_modernity_score", "N/A")}</div>
                </div>""",
                    unsafe_allow_html=True,
                )
            with mcol4:
                st.markdown(
                    f"""<div class="metric-card">
                    <h3>Trust Score</h3>
                    <div class="value">{visual.get("trust_signal_score", "N/A")}</div>
                </div>""",
                    unsafe_allow_html=True,
                )

            st.markdown("")

            # Profile details in tabs
            tab1, tab2 = st.tabs(["Business Profile", "Visual Profile"])

            with tab1:
                if profile:
                    for key, value in profile.items():
                        if isinstance(value, list):
                            st.markdown(f"**{key.replace('_', ' ').title()}:**")
                            for item in value:
                                st.markdown(f"  - {item}")
                        else:
                            st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
                else:
                    st.info("No profile data available.")

            with tab2:
                if visual:
                    for key, value in visual.items():
                        st.markdown(f"**{key.replace('_', ' ').title()}:** {value}")
                else:
                    st.info("No visual profile data available.")

    except Exception as e:
        st.error(f"Error loading company profile: {e}")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Competitors ────────────────────────────────────────────────────────
    try:
        resp = requests.get(f"{API_BASE}/company/{company_id}/competitors", timeout=10)
        if resp.status_code == 200:
            comp_data = resp.json()
            local_competitors = comp_data.get("local_competitors", [])
            global_competitors = comp_data.get("global_competitors", [])
            total = len(local_competitors) + len(global_competitors)

            st.markdown(f"### Discovered Competitors ({total})")

            def _render_competitor_list(competitors, label):
                """Render a list of competitors with chart and expanders."""
                if not competitors:
                    st.info(f"No {label} competitors discovered.")
                    return

                # Similarity chart
                names = [c.get("name", "Unknown") for c in competitors]
                scores = [c.get("similarity_score", 0) for c in competitors]
                chart_data = {"Competitor": names, "Similarity Score": scores}
                st.bar_chart(
                    chart_data, x="Competitor", y="Similarity Score", horizontal=True
                )

                # Competitor details
                for comp in competitors:
                    with st.expander(
                        f"{comp.get('name', 'Unknown')} — "
                        f"Similarity: {comp.get('similarity_score', 0):.2f}"
                    ):
                        st.markdown(f"**URL:** {comp.get('url', 'N/A')}")
                        comp_profile = comp.get("json_profile", {})
                        if comp_profile:
                            for key, value in comp_profile.items():
                                if isinstance(value, list):
                                    st.markdown(
                                        f"**{key.replace('_', ' ').title()}:** {', '.join(str(v) for v in value)}"
                                    )
                                else:
                                    st.markdown(
                                        f"**{key.replace('_', ' ').title()}:** {value}"
                                    )

            tab_local, tab_global = st.tabs(
                [
                    f"🇮🇳 Local Competitors ({len(local_competitors)})",
                    f"🌍 Global Competitors ({len(global_competitors)})",
                ]
            )

            with tab_local:
                _render_competitor_list(local_competitors, "local")

            with tab_global:
                _render_competitor_list(global_competitors, "global")

    except Exception as e:
        st.error(f"Error loading competitors: {e}")

    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # ── Report Download ────────────────────────────────────────────────────
    st.markdown("### Intelligence Report")

    col_r1, col_r2 = st.columns(2)

    with col_r1:
        try:
            resp = requests.get(
                f"{API_BASE}/company/{company_id}/report/json",
                timeout=10,
            )
            if resp.status_code == 200:
                report_data = resp.json()
                report_content = report_data.get("report", {})

                if report_content:
                    st.markdown("**Comparative Analysis Highlights:**")
                    for key in [
                        "positioning_comparison",
                        "pricing_comparison",
                        "market_saturation_estimate",
                    ]:
                        value = report_content.get(key)
                        if value:
                            label = key.replace("_", " ").title()
                            if isinstance(value, dict):
                                # Format dict values as readable text
                                if key == "market_saturation_estimate":
                                    level = value.get("saturation_level", "Unknown")
                                    reason = value.get("reasoning", "N/A")
                                    trajectory = value.get("growth_trajectory", "N/A")
                                    st.markdown(
                                        f"**{label}:**<br>"
                                        f"• **Saturation Level:** {level}<br>"
                                        f"• **Reasoning:** {reason}<br>"
                                        f"• **Growth Trajectory:** {trajectory}",
                                        unsafe_allow_html=True,
                                    )
                                else:
                                    st.markdown(f"**{label}:**")
                                    st.json(value)
                            else:
                                st.markdown(f"**{label}:** {value}")
        except Exception as e:
            st.warning(f"Could not load report data: {e}")

    with col_r2:
        st.markdown("**Download Full Report**")
        download_url = f"{API_BASE}/company/{company_id}/report"
        st.markdown(
            f'<a href="{download_url}" target="_blank">'
            f'<button style="background:#0f3460;color:white;border:none;'
            f"padding:12px 24px;border-radius:8px;cursor:pointer;"
            f'font-size:1rem;font-weight:600;width:100%;">'
            f"Download PDF Report</button></a>",
            unsafe_allow_html=True,
        )
        st.markdown("")
        st.info(
            "The PDF report includes all sections: Executive Summary, "
            "Business Profile, Visual Analysis, Competitor Profiles, "
            "Comparison Tables, and Strategic Recommendations."
        )


# ── Footer ─────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<p style="text-align:center;color:#888;font-size:0.8rem;">'
    "AI-Powered Competitor Intelligence Engine • Groq Llama + FAISS"
    "</p>",
    unsafe_allow_html=True,
)
>>>>>>> c8b6483 (updated the report and fixed bugs)
