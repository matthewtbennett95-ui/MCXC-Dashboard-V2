import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
import base64
import datetime
import requests
import plotly.express as px
import numpy as np
import re
from streamlit_gsheets import GSheetsConnection
import json

def _push_meet_to_firebase(meet_name, meet_date, races_list):
    """
    Writes meet data to Firebase Realtime Database so the timer.html tool
    can load it from its dropdown without manual entry.

    races_list: [{"name": str, "dist": str, "runners": [{"username": str, "name": str, "pr": str}]}]

    Uses the Firebase REST API (no firebase-admin SDK needed — just HTTP).
    The database URL and API key are read from Streamlit secrets if available,
    otherwise this silently skips (timer still works with manual entry).
    """
    try:
        db_url  = st.secrets.get("firebase_db_url", "https://mcxc-timer-default-rtdb.firebaseio.com")
        api_key = st.secrets.get("firebase_api_key", "AIzaSyAKFLshFCubsJtJ5TTb7FFWB2kUl-wph_c")

        import re as _re
        meet_key = _re.sub(r'[^a-zA-Z0-9_-]', '_', meet_name) + "_" + str(meet_date).replace("-","")

        races_payload = {}
        for race in races_list:
            race_key = _re.sub(r'[^a-zA-Z0-9_-]', '_', race["name"])
            races_payload[race_key] = {
                "name":    race["name"],
                "dist":    race.get("dist", "5K"),
                "runners": [{"username": r["username"], "name": r["name"], "pr": r.get("pr","")}
                            for r in race.get("runners", [])]
            }

        payload = {
            "name":    meet_name,
            "date":    str(meet_date),
            "season":  calculate_season(str(meet_date)),
            "races":   races_payload,
            "createdAt": str(pd.Timestamp.now(tz="America/New_York"))
        }

        url = f"{db_url}/meets/{meet_key}.json"
        resp = requests.put(url, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception:
        return False  # Silently fail — timer still works with manual entry

# ==========================================
# 1. APP SETUP & VISUAL THEMES
# ==========================================
st.set_page_config(page_title="MCXC Team Dashboard", layout="wide", page_icon="mcxc_logo.png")

st.markdown("""
    <style>
    footer {visibility: hidden !important;}
    [data-testid="stHeader"] {display: none !important;}
    .viewerBadge_container__1QSob {display: none !important;}
    [class^="viewerBadge_"] {display: none !important;}
    .block-container {padding-top: 1rem !important;}
    </style>
""", unsafe_allow_html=True)

def force_mobile_icon():
    try:
        with open("mcxc_logo.png", "rb") as f:
            encoded = base64.b64encode(f.read()).decode()
        components.html(f"""
        <script>
            const doc = window.parent.document;
            let link = doc.querySelector("link[rel~='apple-touch-icon']");
            if (!link) {{ link = doc.createElement('link'); link.rel = 'apple-touch-icon'; doc.head.appendChild(link); }}
            link.href = 'data:image/png;base64,{encoded}';
        </script>""", height=0, width=0)
    except Exception:
        pass

force_mobile_icon()

MCXC_CRIMSON, MCXC_NAVY, MCXC_GOLD = "#8B2331", "#0C223F", "#C7B683"

THEMES = {
    "MCXC Classic (Light)": {
        "bar": f"linear-gradient(to right, {MCXC_CRIMSON}, {MCXC_NAVY}, {MCXC_GOLD})",
        "metric_bg": "rgba(139, 35, 49, 0.05)", "metric_border": "rgba(139, 35, 49, 0.2)",
        "line": MCXC_CRIMSON, "app_bg": "#FFFFFF", "text": "#31333F",
        "header": MCXC_NAVY, "sidebar_bg": "#F0F2F6", "plotly_template": "plotly_white", "is_dark": False
    },
    "MCXC Elite (Dark)": {
        "bar": f"linear-gradient(to right, {MCXC_CRIMSON}, {MCXC_GOLD}, {MCXC_CRIMSON})",
        "metric_bg": "rgba(199, 182, 131, 0.1)", "metric_border": "rgba(199, 182, 131, 0.3)",
        "line": MCXC_GOLD, "app_bg": MCXC_NAVY, "text": "#FFFFFF",
        "header": MCXC_GOLD, "sidebar_bg": "#08182D", "plotly_template": "plotly_dark", "is_dark": True
    },
    "Midnight Runner (Dark)": {
        "bar": "linear-gradient(to right, #FF4B4B, #FF904F)",
        "metric_bg": "rgba(255, 75, 75, 0.1)", "metric_border": "rgba(255, 75, 75, 0.3)",
        "line": "#FF4B4B", "app_bg": "#0E1117", "text": "#FFFFFF",
        "header": MCXC_GOLD, "sidebar_bg": "#1A1C24", "plotly_template": "plotly_dark", "is_dark": True
    },
    "Ocean Pace (Light)": {
        "bar": "linear-gradient(to right, #00C9FF, #92FE9D)",
        "metric_bg": "rgba(0, 201, 255, 0.05)", "metric_border": "rgba(0, 201, 255, 0.3)",
        "line": "#00C9FF", "app_bg": "#F4F8FB", "text": "#1A2A3A",
        "header": "#00C9FF", "sidebar_bg": "#E5F0F9", "plotly_template": "plotly_white", "is_dark": False
    },
    "Forest Trail (Light)": {
        "bar": "linear-gradient(to right, #2E7D32, #81C784)",
        "metric_bg": "rgba(46, 125, 50, 0.05)", "metric_border": "rgba(46, 125, 50, 0.3)",
        "line": "#2E7D32", "app_bg": "#F1F8E9", "text": "#1B5E20",
        "header": "#1B5E20", "sidebar_bg": "#E8F5E9", "plotly_template": "plotly_white", "is_dark": False
    },
    "Neon Track (Dark)": {
        "bar": "linear-gradient(to right, #E040FB, #18FFFF)",
        "metric_bg": "rgba(224, 64, 251, 0.1)", "metric_border": "rgba(24, 255, 255, 0.3)",
        "line": "#18FFFF", "app_bg": "#121212", "text": "#FFFFFF",
        "header": "#E040FB", "sidebar_bg": "#1E1E1E", "plotly_template": "plotly_dark", "is_dark": True
    }
}

if "theme" not in st.session_state:
    st.session_state["theme"] = "MCXC Classic (Light)"

T = THEMES[st.session_state["theme"]]  # Shorthand for current theme

dark_css = ""
if T["is_dark"]:
    dark_css = f"""
        [data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="base-input"] {{
            background-color: rgba(0,0,0,0.4) !important; color: #FFFFFF !important; border-color: rgba(255,255,255,0.2) !important;
        }}
        [data-testid="stForm"] {{ background-color: {T['sidebar_bg']} !important; border-color: rgba(255,255,255,0.1) !important; }}
        input, textarea, select {{ color: #FFFFFF !important; }}
        [data-testid="stDataFrame"], [data-testid="stDataEditor"] {{ filter: invert(0.92) hue-rotate(180deg); }}"""

st.markdown(f"""
    <style>
        .stApp {{ background-color: {T['app_bg']} !important; }}
        [data-testid="stSidebar"] {{ background-color: {T['sidebar_bg']} !important; }}
        [data-testid="stHeader"] {{ background-color: transparent !important; }}
        .color-bar {{ height: 8px; background: {T['bar']}; margin-bottom: 2rem; border-radius: 4px; }}
        div[data-testid="metric-container"] {{ background-color: {T['metric_bg']} !important; border: 1px solid {T['metric_border']} !important; padding: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        h1, h2, h3, h4, h5, h6, .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{ color: {T['header']} !important; }}
        .stMarkdown p, .stMarkdown li, .stMarkdown span, div[data-testid="stCaptionContainer"], label, .stMetricValue, div[data-testid="stTabs"] button p {{ color: {T['text']} !important; }}
        div.stButton > button, div.stFormSubmitButton > button {{ background-color: {T['sidebar_bg']} !important; color: {T['text']} !important; border: 1px solid {T['metric_border']} !important; transition: all 0.3s ease; }}
        div.stButton > button:hover, div.stFormSubmitButton > button:hover {{ border-color: {T['line']} !important; color: {T['line']} !important; background-color: {T['app_bg']} !important; }}
        {dark_css}
    </style>
    <div class="color-bar"></div>
""", unsafe_allow_html=True)

# ==========================================
# 2. MATH, LOGIC, & UTILITIES
# ==========================================
def time_to_seconds(time_str):
    if pd.isna(time_str) or str(time_str).strip() == "": return 0
    parts = str(time_str).strip().split(":")
    if len(parts) == 2:
        try: return int(parts[0]) * 60 + float(parts[1])
        except: return 0
    return 0

def seconds_to_time(seconds):
    if not seconds or seconds <= 0 or pd.isna(seconds): return ""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins}:{secs:05.2f}".replace(".00", "")

def parse_fast_time(val, mode):
    if pd.isna(val) or str(val).strip() == "": return ""
    val_str = str(val).strip()
    if ":" in val_str: return val_str
    if not val_str.replace(".", "").isdigit(): return val_str
    num = float(val_str)
    if "Total Seconds" in mode:
        return f"{int(num // 60)}:{num % 60:05.2f}".replace(".00", "")
    if "." in val_str:
        whole_num, decimal_part = int(val_str.split(".")[0]), "." + val_str.split(".")[1]
    else:
        whole_num, decimal_part = int(val_str), ""
    if len(str(whole_num)) <= 2:
        return f"{whole_num // 60}:{whole_num % 60:02d}{decimal_part}"
    secs = int(str(whole_num)[-2:])
    mins = int(str(whole_num)[:-2]) + secs // 60
    return f"{mins}:{secs % 60:02d}{decimal_part}"

def get_grade_level(grad_year_str):
    if str(grad_year_str).upper() == "COACH" or not str(grad_year_str).strip().isdigit(): return "Coach"
    today = datetime.date.today()
    current_season_year = today.year - 1 if today.month < 7 else today.year
    grade = 12 - (int(grad_year_str) - (current_season_year + 1))
    grade_map = {9: "9th", 10: "10th", 11: "11th", 12: "12th"}
    if grade in grade_map: return grade_map[grade]
    return "Middle School" if grade < 9 else "Alumni"

def calculate_season(date_val):
    try:
        d = pd.to_datetime(date_val)
        if pd.isna(d): return str(datetime.date.today().year)
        return str(d.year) if d.month >= 7 else str(d.year - 1)
    except: return str(datetime.date.today().year)

CURRENT_SEASON = calculate_season(datetime.date.today())

@st.cache_data(ttl=86400)
def get_weather_for_date(date_str):
    LAT, LON = 34.077604, -83.877289
    try:
        d_obj = pd.to_datetime(date_str)
        d = d_obj.strftime("%Y-%m-%d")
        days_ago = (pd.to_datetime("today") - d_obj).days
        base = "https://archive-api.open-meteo.com/v1/archive" if days_ago > 60 else "https://api.open-meteo.com/v1/forecast"
        url = f"{base}?latitude={LAT}&longitude={LON}&start_date={d}&end_date={d}&daily=temperature_2m_max,precipitation_sum&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America/New_York"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json().get("daily", {})
            temp = data.get("temperature_2m_max", [None])[0]
            if temp is None: return "Can't access weather data"
            precip = data.get("precipitation_sum", [None])[0]
            suffix = f" ({round(precip, 1)}in Rain)" if precip and precip > 0.05 else " (Dry)"
            return f"{round(temp)}°F{suffix}"
        return "Can't access weather data"
    except: return "Can't access weather data"

# ==========================================
# PRINT HELPERS
# ==========================================

def wrap_html_for_print(title, body_content, is_attendance=False, force_landscape=False):
    """
    Shared HTML shell for all printable sheets.

    Improvements over original:
    - force_landscape=True sets @page to landscape explicitly (used when rep
      count is high on workout sheets).
    - table-layout:fixed + font-size scaling via CSS clamp() so columns shrink
      gracefully instead of overflowing.
    - th/td use overflow:hidden + text-overflow:ellipsis as a last resort.
    - @page margin kept at 0 so browser never prints its own date/URL header.
      The body padding of 0.4in at print time gives clean white margins.
    """
    if force_landscape:
        page_css = "size: landscape; margin: 0;"
    elif is_attendance:
        page_css = "size: portrait; margin: 0;"
    else:
        page_css = "size: auto; margin: 0;"

    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>
<style>
    :root {{
        --border-color: #cbd5e1;
        --text-main: #1e293b;
        --text-muted: #64748b;
        --font-family: 'Inter', system-ui, -apple-system, sans-serif;
        --mcxc-crimson: #8B2331;
        --mcxc-navy: #0C223F;
    }}
    body {{
        font-family: var(--font-family);
        padding: 16px;
        margin: 0;
        color: var(--text-main);
        background: #ffffff;
    }}
    @page {{ {page_css} }}

    /* ---- Header ---- */
    .sheet-header {{
        border-left: 5px solid var(--mcxc-crimson);
        padding: 6px 0 6px 12px;
        margin-bottom: 16px;
    }}
    .sheet-header h1 {{
        margin: 0; font-size: 18px; font-weight: 700;
        color: var(--mcxc-navy); letter-spacing: -0.3px;
    }}
    .sheet-header .sub {{
        margin: 2px 0 0 0; font-size: 12px; color: var(--text-muted);
    }}

    /* ---- Section headings (race / gender blocks) ---- */
    h2 {{
        margin: 14px 0 0 0; font-size: 13px; font-weight: 700;
        background: var(--mcxc-navy); color: #ffffff;
        padding: 7px 12px; border-radius: 4px 4px 0 0;
        page-break-after: avoid; break-after: avoid;
        text-transform: uppercase; letter-spacing: 0.5px;
    }}
    h3 {{
        margin: 14px 0 0 0; font-size: 12px; font-weight: 600;
        background: #f1f5f9; color: var(--text-main);
        padding: 6px 12px;
        border: 1px solid var(--border-color);
        border-radius: 4px 4px 0 0; border-bottom: none;
        page-break-after: avoid; break-after: avoid;
    }}

    /* ---- Tables ---- */
    table {{
        width: 100%;
        border-collapse: collapse;
        margin-bottom: 20px;
        table-layout: fixed;          /* forces columns to share space evenly */
        page-break-inside: avoid;
        break-inside: avoid;
        border: 1px solid var(--border-color);
    }}
    tr {{ page-break-inside: avoid; page-break-after: auto; }}
    th, td {{
        border: 1px solid var(--border-color);
        text-align: center;
        font-size: clamp(8px, 1.1vw, 12px);   /* shrinks gracefully */
        padding: 7px 3px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    th:first-child, td:first-child {{
        text-align: left;
        padding-left: 10px;
        width: 22%;           /* name column gets a fixed share */
        white-space: normal;  /* allow names to wrap if needed */
    }}
    th {{
        color: var(--text-muted); font-weight: 700;
        text-transform: uppercase; letter-spacing: 0.4px;
        font-size: clamp(7px, 1vw, 11px);
        background: #f8fafc;
    }}

    /* ---- Rest cycle mini-table (workout sheets) ---- */
    .rest-table {{ margin-top: 12px; }}
    .rest-table h3 {{ background: #fef3c7; color: #92400e; border-color: #fcd34d; }}
    .rest-table table {{ font-size: clamp(7px, 1vw, 11px); }}

    /* ---- Page-break helpers ---- */
    .keep-together {{ page-break-inside: avoid; break-inside: avoid; margin-bottom: 20px; }}
    .page-break    {{ page-break-before: always; break-before: always; }}

    /* ---- Print button (screen only) ---- */
    .no-print-container {{
        text-align: center; margin-bottom: 24px; padding: 16px;
        background: #f0f4f8; border-radius: 10px;
        border: 1px solid var(--border-color);
    }}
    .print-btn {{
        background: var(--mcxc-crimson); color: #ffffff; border: none;
        padding: 10px 22px; border-radius: 6px; font-size: 14px;
        font-weight: 600; cursor: pointer; text-transform: uppercase;
        letter-spacing: 0.5px; margin-bottom: 8px;
        box-shadow: 0 4px 6px -1px rgba(139,35,49,0.3);
    }}
    .print-btn:hover {{ filter: brightness(1.1); }}

    @media print {{
        .no-print {{ display: none !important; }}
        body {{ padding: 0.4in; }}
        * {{ -webkit-print-color-adjust: exact !important;
             print-color-adjust: exact !important; }}
    }}
</style>
</head><body>
<div class="no-print no-print-container">
    <button class="print-btn" onclick="window.print()">🖨️ Click Here to Print / Save as PDF</button>
    <p style="color:var(--text-muted);font-size:13px;margin:6px 0 0 0;">
        <strong>Pro Tip:</strong> In the print dialog set <em>Scale → Fit to Page</em> if anything looks cut off.
    </p>
    <p style="color:var(--text-muted);font-size:12px;margin:4px 0 0 0;">
        Uncheck <em>Headers and Footers</em> if you see a date/URL on the printout.
    </p>
</div>
{body_content}
</body></html>"""


def _get_athlete_pr(uname, races_df, season=None):
    """
    Returns (time_str, source_label) for an athlete's best 5K or 2-Mile.
    Used to sort split sheets by PR and show the time on workout sheets.
    If season is given, prefers that season's PR; falls back to all-time.
    """
    active = races_df[races_df["Active"].isin(ACTIVE_FLAGS)].copy()
    active["sec"] = active["Total_Time"].apply(time_to_seconds)
    active = active[(active["Username"] == uname) & (active["sec"] > 0)]
    if active.empty:
        return None, None

    for dist in ["5K", "2 MILE"]:
        subset = active[active["Distance"].str.upper() == dist]
        if season:
            s_subset = subset[subset["Season"] == season]
            if not s_subset.empty:
                best = s_subset.loc[s_subset["sec"].idxmin()]
                return seconds_to_time(best["sec"]), f"{season} {dist} PR"
        if not subset.empty:
            best = subset.loc[subset["sec"].idxmin()]
            return seconds_to_time(best["sec"]), f"All-Time {dist} PR"
    return None, None


def _build_split_sheet_html(p_meet, races_df, roster_df, race_list=None,
                             meet_date=None, prior_meet_name=None, filled=False):
    """
    Builds the HTML body for a meet split sheet.

    filled=False (default): blank clipboard sheet — time columns are empty.
    filled=True:            results sheet — actual recorded times are shown,
                            runners sorted by finish time within each race.

    prior_meet_name: optional name of a previous year's version of this meet.
      When set, get_prior_time() checks BOTH the current meet name AND the
      prior meet name so year-to-year renaming doesn't break historical PRs.

    Each race block forces a page break before it (except the first) so a race
    never starts mid-page after another race ends.
    """
    active_athletes = roster_df[roster_df["Role"].str.upper() == "ATHLETE"].copy()
    athlete_opts = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}"
                    for _, row in active_athletes.iterrows()}

    def get_prior_time(uname):
        """
        Returns the best time for this athlete at this meet (or the linked
        prior meet name). Falls back to all-time 5K PR labelled (PR).
        """
        meet_names = [p_meet]
        if prior_meet_name and prior_meet_name != p_meet:
            meet_names.append(prior_meet_name)

        best_sec = None
        for mname in meet_names:
            subset = races_df[
                (races_df["Username"] == uname) &
                (races_df["Meet_Name"] == mname) &
                (races_df["Total_Time"].str.strip() != "")
            ].copy()
            if not subset.empty:
                subset["sec"] = subset["Total_Time"].apply(time_to_seconds)
                subset = subset[subset["sec"] > 0]
                if not subset.empty:
                    m = subset["sec"].min()
                    if best_sec is None or m < best_sec:
                        best_sec = m

        if best_sec is not None:
            return seconds_to_time(best_sec)

        # Fall back to all-time 5K PR
        all_5k = races_df[
            (races_df["Username"] == uname) &
            (races_df["Distance"].str.upper() == "5K") &
            (races_df["Total_Time"].str.strip() != "")
        ].copy()
        if not all_5k.empty:
            all_5k["sec"] = all_5k["Total_Time"].apply(time_to_seconds)
            all_5k = all_5k[all_5k["sec"] > 0]
            if not all_5k.empty:
                return f"{seconds_to_time(all_5k['sec'].min())} (PR)"
        return "—"

    date_str = ""
    if meet_date:
        try: date_str = pd.to_datetime(meet_date).strftime("%B %d, %Y")
        except: date_str = str(meet_date)

    prior_note = f' <span style="font-size:11px;opacity:0.7;">(linked to: {prior_meet_name})</span>' if prior_meet_name and prior_meet_name != p_meet else ""

    sheet_type = "Results Sheet" if filled else "Split Sheet"
    html  = '<div class="sheet-header">'
    html += f'<h1>{p_meet} — {sheet_type}{prior_note}</h1>'
    if date_str:
        html += f'<p class="sub">{date_str}</p>'
    html += '</div>'

    meet_rows = races_df[races_df["Meet_Name"] == p_meet]
    races_to_show = race_list if race_list else [
        {"name": rn,
         "dist": meet_rows[meet_rows["Race_Name"] == rn]["Distance"].iloc[0]
                 if not meet_rows[meet_rows["Race_Name"] == rn].empty else ""}
        for rn in meet_rows["Race_Name"].unique()
    ]

    for i, race in enumerate(races_to_show):
        r_name  = race["name"] if isinstance(race, dict) else race
        r_dist  = race.get("dist", "") if isinstance(race, dict) else ""
        runners = (race.get("runners",
                    meet_rows[meet_rows["Race_Name"] == r_name]["Username"].tolist())
                   if isinstance(race, dict) else
                   meet_rows[meet_rows["Race_Name"] == r_name]["Username"].tolist())

        if filled:
            # Sort by actual finish time for this race (fastest first).
            # Runners with no finish time go to the bottom.
            def filled_sort_key(uname):
                row_data = meet_rows[
                    (meet_rows["Race_Name"] == r_name) &
                    (meet_rows["Username"]   == uname)
                ]
                if row_data.empty: return 9999
                fin = str(row_data["Total_Time"].iloc[0]).strip()
                sec = time_to_seconds(fin)
                return sec if sec > 0 else 9999
            runners_sorted = sorted(runners, key=filled_sort_key)
        else:
            # Sort by current-season PR fastest → slowest (clipboard order)
            def runner_sort_key(uname):
                t, _ = _get_athlete_pr(uname, races_df, season=CURRENT_SEASON)
                return time_to_seconds(t) if t else 9999
            runners_sorted = sorted(runners, key=runner_sort_key)

        # Each race block forces a page break BEFORE it (except the first)
        # so a race never starts mid-page after another race ends.
        # page-break-inside:avoid keeps the whole table on one page.
        break_style = " page-break-before: always; break-before: always;" if i > 0 else ""
        html += (f'<div style="page-break-inside:avoid;break-inside:avoid;'
'                    margin-bottom:20px;{break_style}">')
        html += f'<h2>{r_name} ({r_dist})</h2>'
        html += ("<table><tr>"
                 "<th>Athlete</th>"
                 "<th>Prior Best at Meet</th>"
                 "<th>1 Mile</th><th>2 Mile</th><th>Finish</th>"
                 "</tr>")
        for uname in runners_sorted:
            name  = athlete_opts.get(uname, uname)
            prior = get_prior_time(uname)
            if filled:
                # Pull actual recorded times for this race
                row_data = meet_rows[
                    (meet_rows["Race_Name"] == r_name) &
                    (meet_rows["Username"]   == uname)
                ]
                m1  = str(row_data["Mile_1"].iloc[0]).strip()    if not row_data.empty else ""
                m2  = str(row_data["Mile_2"].iloc[0]).strip()    if not row_data.empty else ""
                fin = str(row_data["Total_Time"].iloc[0]).strip() if not row_data.empty else ""
                # Highlight the finish time cell if it has a value
                fin_style = "font-weight:700;color:#0C223F;" if fin else ""
                html += (f"<tr>"
                         f"<td>{name}</td>"
                         f"<td>{prior}</td>"
                         f"<td>{m1}</td>"
                         f"<td>{m2}</td>"
                         f"<td style='{fin_style}'>{fin}</td>"
                         f"</tr>")
            else:
                html += f"<tr><td>{name}</td><td>{prior}</td><td></td><td></td><td></td></tr>"
        html += "</table></div>"

    return html

def _build_filled_workout_sheet_html(w_date, workouts_df, roster_df, races_df):
    """
    Builds a filled-in workout results sheet for a specific date.

    Finds all workout sessions logged on w_date, groups by gender,
    and prints actual recorded splits in the rep columns alongside
    each athlete's name and current PR.

    If multiple workout types were logged on the same date (e.g. a
    combined Tempo + Hills session), each appears as its own section.
    Boys and Girls are on separate pages.
    """
    try:
        date_str = pd.to_datetime(w_date).strftime("%B %d, %Y")
    except:
        date_str = str(w_date)

    # All workout rows for this date
    day_workouts = workouts_df[workouts_df["Date"] == str(w_date)].copy()
    if day_workouts.empty:
        return "<p>No workout data found for this date.</p>", False

    # Unique workout type + distance combos for that day
    combos = day_workouts[["Workout_Type","Rep_Distance"]].drop_duplicates().values.tolist()

    html_parts = []
    for gender_label, gender_val in [("Boys", "Male"), ("Girls", "Female")]:
        athletes = roster_df[
            (roster_df["Role"].str.upper() == "ATHLETE") &
            (roster_df["Active_Clean"].isin(ACTIVE_FLAGS)) &
            (roster_df["Gender"].str.title() == gender_val)
        ].sort_values(["Last_Name","First_Name"])

        if athletes.empty:
            continue

        part = f'<div class="sheet-header"><h1>{gender_label} Workout Results</h1>'
        part += f'<p class="sub">{date_str}</p></div>'

        for w_type, w_dist in combos:
            combo_rows = day_workouts[
                (day_workouts["Workout_Type"] == w_type) &
                (day_workouts["Rep_Distance"] == w_dist)
            ]

            # Find max rep count across all athletes for this combo
            max_reps = 1
            for _, r in combo_rows.iterrows():
                splits = [s.strip() for s in str(r.get("Splits","")).split(",") if s.strip()]
                if len(splits) > max_reps: max_reps = len(splits)

            rep_headers = "".join(f"<th>{i}</th>" for i in range(1, max_reps+1))
            part += f'<div class="keep-together">'
            part += f'<h2>{gender_label} — {w_type} ({w_dist})</h2>'
            part += f'<table><tr><th>Athlete (PR)</th>{rep_headers}<th>Status</th></tr>'

            for _, athlete in athletes.iterrows():
                uname = athlete["Username"]
                a_row = combo_rows[combo_rows["Username"] == uname]
                pr_time, _ = _get_athlete_pr(uname, races_df, season=CURRENT_SEASON)
                pr_display = pr_time if pr_time else "—"
                name_cell  = (f"{athlete['Last_Name']}, {athlete['First_Name']}"
                              f"<span style='font-size:10px;color:#64748b;'> ({pr_display})</span>")

                if a_row.empty:
                    # Athlete not in this workout session — skip row
                    continue

                status = str(a_row.iloc[0].get("Status","")).strip()
                splits = [s.strip() for s in str(a_row.iloc[0].get("Splits","")).split(",") if s.strip()]

                # Color-code status
                status_style = ""
                if status == "Present":   status_style = "color:#22c55e;font-weight:600;"
                elif status in ("Sick","Injured"): status_style = "color:#ef4444;"
                elif status == "Unexcused": status_style = "color:#f59e0b;"

                part += f'<tr><td style="text-align:left;padding-left:8px;">{name_cell}</td>'
                for i in range(max_reps):
                    val = splits[i] if i < len(splits) else ""
                    part += f'<td>{val}</td>'
                part += f'<td style="{status_style}">{status}</td></tr>'

            part += "</table></div>"

        html_parts.append(part)

    body          = '<div class="page-break"></div>'.join(html_parts) if html_parts else "<p>No data found.</p>"
    force_landscape = max_reps > 7 if html_parts else False
    return body, force_landscape


def _build_workout_sheet_html(w_type, w_dist, w_date, rep_count, roster_df, races_df, rest_df):
    """
    Builds the HTML body for a printable workout sheet.

    Layout (matches your paper format):
    ┌─────────────────────────────────────────────────┐
    │  [Boys/Girls] Workout Sheet                     │
    │  [Workout Type] — [Distance] — [Date]           │
    ├──────────────┬───┬───┬───┬───┬───┬─────────────┤
    │ Athlete      │ 1 │ 2 │ 3 │ 4 │ 5 │ ...         │
    ├──────────────┼───┼───┼───┼───┼───┤             │
    │ ...          │   │   │   │   │   │             │
    └──────────────┴───┴───┴───┴───┴───┴─────────────┘
    [Rest Cycle table for this workout type]

    Boys and Girls are separate <div class="page-break"> sections so they
    print on separate pages from a single downloaded file.

    force_landscape is returned as a boolean so the caller can pass it to
    wrap_html_for_print — triggered when rep_count > 7.
    """
    try:
        date_str = pd.to_datetime(w_date).strftime("%B %d, %Y")
    except:
        date_str = str(w_date)

    # Rep column headers
    rep_headers = "".join(f"<th>{i}</th>" for i in range(1, rep_count + 1))

    # Rest cycle rows relevant to this workout type
    rest_subset = rest_df[rest_df["Workout"].str.contains(w_type, case=False, na=False)]
    rest_html = ""
    if not rest_subset.empty:
        rest_rows = "".join(
            f"<tr><td style='text-align:left;padding-left:8px;'>{row['Pace / Time']}</td>"
            f"<td>{row['Cycle / Rest']}</td></tr>"
            for _, row in rest_subset.iterrows()
        )
        rest_html = f"""
        <div class="rest-table keep-together">
            <h3>Rest Cycle — {w_type} ({w_dist})</h3>
            <table>
                <tr><th style="text-align:left;padding-left:8px;">VDOT / Pace Range</th>
                    <th>Cycle / Rest</th></tr>
                {rest_rows}
            </table>
        </div>"""

    html_parts = []
    for gender_label, gender_val in [("Boys", "Male"), ("Girls", "Female")]:
        athletes = roster_df[
            (roster_df["Role"].str.upper() == "ATHLETE") &
            (roster_df["Active_Clean"].isin(ACTIVE_FLAGS)) &
            (roster_df["Gender"].str.title() == gender_val)
        ].sort_values(["Last_Name", "First_Name"])

        if athletes.empty:
            continue

        athlete_rows = ""
        for _, row in athletes.iterrows():
            pr_time, _ = _get_athlete_pr(row["Username"], races_df, season=CURRENT_SEASON)
            pr_display = pr_time if pr_time else "—"
            blank_reps = "".join("<td></td>" for _ in range(rep_count))
            athlete_rows += (
                f"<tr>"
                f"<td style='text-align:left;padding-left:8px;'>"
                f"{row['Last_Name']}, {row['First_Name']}"
                f"<span style='font-size:10px;color:#64748b;'> ({pr_display})</span>"
                f"</td>"
                f"{blank_reps}"
                f"</tr>"
            )

        part  = '<div class="sheet-header">'
        part += f'<h1>{gender_label} Workout Sheet</h1>'
        part += f'<p class="sub">{w_type} — {w_dist} &nbsp;|&nbsp; {date_str}</p>'
        part += '</div>'
        part += f"<div class='keep-together'>"
        part += f"<h2>{gender_label} — {w_type} ({w_dist})</h2>"
        part += f"<table><tr><th>Athlete (Current PR)</th>{rep_headers}</tr>"
        part += athlete_rows
        part += "</table></div>"
        part += rest_html
        html_parts.append(part)

    # Join pages with a page-break div between Boys and Girls
    body = '<div class="page-break"></div>'.join(html_parts)
    force_landscape = rep_count > 7
    return body, force_landscape

# ==========================================
# 3. DATABASE CONNECTION & CACHING
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

# Each sheet has its own @st.cache_data function so we can invalidate only the
# sheet that actually changed instead of clearing all 7 sheets at once.
#
# TTL strategy (balancing freshness vs. API quota):
#   Roster / VDOT / Rest / Docs  — 3600s (1 hr): rarely changes mid-session
#   Races / Workouts             —  900s (15 min): coach enters after events
#   Announcements                —  120s (2 min):  athletes need to see posts quickly
#
# After any conn.update() call, use the matching invalidate_*() helper below
# instead of st.cache_data.clear() so only one sheet re-reads on the next run.

@st.cache_data(ttl=3600)
def _fetch_roster():
    return conn.read(worksheet="Roster", ttl=0).dropna(how="all")

@st.cache_data(ttl=900)
def _fetch_races():
    return conn.read(worksheet="Races", ttl=0).dropna(how="all")

@st.cache_data(ttl=900)
def _fetch_workouts():
    return conn.read(worksheet="Workouts", ttl=0).dropna(how="all")

@st.cache_data(ttl=3600)
def _fetch_vdot():
    try:
        df = conn.read(worksheet="VDOT", ttl=0).dropna(how="all")
        return df if "5K_Time" in df.columns else None
    except: return None

@st.cache_data(ttl=3600)
def _fetch_rest():
    try:
        df = conn.read(worksheet="Rest", ttl=0).dropna(how="all")
        return df if "Workout" in df.columns else None
    except: return None

@st.cache_data(ttl=3600)
def _fetch_docs():
    try:
        df = conn.read(worksheet="Documents", ttl=0).dropna(how="all")
        return df if "Title" in df.columns else None
    except: return None

@st.cache_data(ttl=120)
def _fetch_announcements():
    try:
        df = conn.read(worksheet="Announcements", ttl=0).dropna(how="all")
        required = ["ID","Title","Message","Link","Link_Label","Posted_By","Date_Posted","Active"]
        for col in required:
            if col not in df.columns: df[col] = ""
        # Cast all columns to str so Active can always hold "TRUE"/"FALSE"
        # without pandas FutureWarning about incompatible dtypes
        df = df.astype(str).replace("nan", "")
        return df
    except: return DEFAULT_ANNOUNCEMENTS.copy()

# Targeted invalidation helpers — call these instead of st.cache_data.clear()
def invalidate_roster():        _fetch_roster.clear()
def invalidate_races():         _fetch_races.clear()
def invalidate_workouts():      _fetch_workouts.clear()
def invalidate_vdot():          _fetch_vdot.clear()
def invalidate_rest():          _fetch_rest.clear()
def invalidate_docs():          _fetch_docs.clear()
def invalidate_announcements(): _fetch_announcements.clear()

roster_data    = _fetch_roster()
races_data     = _fetch_races()
workouts_data  = _fetch_workouts()

DEFAULT_VDOT = pd.DataFrame([
    {"VDOT": 66, "5K_Time": "15:41", "2_Mile_Time": "9:46", "Easy_Pace": "6:36-7:00", "Tempo_Mile": "5:28", "Tempo_400m": "1:21", "Interval_400m": "1:15", "Interval_800m": "2:30", "Interval_1000m": "3:06", "Interval_1200m": "3:42", "Interval_Mile": "5:00"},
    {"VDOT": 64, "5K_Time": "16:07", "2_Mile_Time": "10:02", "Easy_Pace": "6:46-7:09", "Tempo_Mile": "5:36", "Tempo_400m": "1:23", "Interval_400m": "1:17", "Interval_800m": "2:34", "Interval_1000m": "3:12", "Interval_1200m": "3:50", "Interval_Mile": "5:08"},
    {"VDOT": 62, "5K_Time": "16:34", "2_Mile_Time": "10:19", "Easy_Pace": "6:56-7:21", "Tempo_Mile": "5:45", "Tempo_400m": "1:26", "Interval_400m": "1:19", "Interval_800m": "2:38", "Interval_1000m": "3:17", "Interval_1200m": "3:56", "Interval_Mile": "5:16"},
    {"VDOT": 60, "5K_Time": "17:03", "2_Mile_Time": "10:37", "Easy_Pace": "7:07-7:33", "Tempo_Mile": "5:54", "Tempo_400m": "1:28", "Interval_400m": "1:21", "Interval_800m": "2:42", "Interval_1000m": "3:23", "Interval_1200m": "4:04", "Interval_Mile": "5:24"},
    {"VDOT": 58, "5K_Time": "17:33", "2_Mile_Time": "10:56", "Easy_Pace": "7:19-7:46", "Tempo_Mile": "6:04", "Tempo_400m": "1:31", "Interval_400m": "1:23", "Interval_800m": "2:47", "Interval_1000m": "3:29", "Interval_1200m": "4:11", "Interval_Mile": "5:34"},
    {"VDOT": 56, "5K_Time": "18:05", "2_Mile_Time": "11:17", "Easy_Pace": "7:31-7:58", "Tempo_Mile": "6:14", "Tempo_400m": "1:33", "Interval_400m": "1:26", "Interval_800m": "2:51", "Interval_1000m": "3:34", "Interval_1200m": "4:17", "Interval_Mile": "5:42"},
    {"VDOT": 54, "5K_Time": "18:40", "2_Mile_Time": "11:39", "Easy_Pace": "7:44-8:13", "Tempo_Mile": "6:26", "Tempo_400m": "1:36", "Interval_400m": "1:28", "Interval_800m": "2:56", "Interval_1000m": "3:40", "Interval_1200m": "4:24", "Interval_Mile": "5:52"},
    {"VDOT": 52, "5K_Time": "19:17", "2_Mile_Time": "12:02", "Easy_Pace": "7:58-8:28", "Tempo_Mile": "6:37", "Tempo_400m": "1:39", "Interval_400m": "1:31", "Interval_800m": "3:02", "Interval_1000m": "3:47", "Interval_1200m": "4:32", "Interval_Mile": "6:04"},
    {"VDOT": 50, "5K_Time": "19:55", "2_Mile_Time": "12:27", "Easy_Pace": "8:15-8:45", "Tempo_Mile": "6:51", "Tempo_400m": "1:42", "Interval_400m": "1:34", "Interval_800m": "3:08", "Interval_1000m": "3:55", "Interval_1200m": "4:42", "Interval_Mile": "6:16"},
    {"VDOT": 48, "5K_Time": "20:39", "2_Mile_Time": "12:55", "Easy_Pace": "8:31-9:02", "Tempo_Mile": "7:05", "Tempo_400m": "1:46", "Interval_400m": "1:37", "Interval_800m": "3:14", "Interval_1000m": "4:03", "Interval_1200m": "4:52", "Interval_Mile": "6:28"},
    {"VDOT": 46, "5K_Time": "21:25", "2_Mile_Time": "13:24", "Easy_Pace": "8:48-9:21", "Tempo_Mile": "7:19", "Tempo_400m": "1:49", "Interval_400m": "1:40", "Interval_800m": "3:21", "Interval_1000m": "4:11", "Interval_1200m": "5:01", "Interval_Mile": "6:42"},
    {"VDOT": 44, "5K_Time": "22:13", "2_Mile_Time": "13:56", "Easy_Pace": "9:09-9:42", "Tempo_Mile": "7:35", "Tempo_400m": "1:53", "Interval_400m": "1:44", "Interval_800m": "3:29", "Interval_1000m": "4:21", "Interval_1200m": "5:13", "Interval_Mile": "6:58"},
    {"VDOT": 42, "5K_Time": "23:08", "2_Mile_Time": "14:31", "Easy_Pace": "9:28-10:04", "Tempo_Mile": "7:53", "Tempo_400m": "1:58", "Interval_400m": "1:48", "Interval_800m": "3:36", "Interval_1000m": "4:36", "Interval_1200m": "5:24", "Interval_Mile": "7:12"},
    {"VDOT": 40, "5K_Time": "24:07", "2_Mile_Time": "15:08", "Easy_Pace": "9:49-10:27", "Tempo_Mile": "8:13", "Tempo_400m": "2:03", "Interval_400m": "1:53", "Interval_800m": "3:45", "Interval_1000m": "4:41", "Interval_1200m": "5:37", "Interval_Mile": "7:30"},
    {"VDOT": 35, "5K_Time": "26:58", "2_Mile_Time": "16:58", "Easy_Pace": "10:52-11:35", "Tempo_Mile": "9:09", "Tempo_400m": "2:17", "Interval_400m": "2:06", "Interval_800m": "4:11", "Interval_1000m": "5:14", "Interval_1200m": "6:17", "Interval_Mile": "8:22"},
    {"VDOT": 30, "5K_Time": "30:40", "2_Mile_Time": "19:19", "Easy_Pace": "12:17-12:59", "Tempo_Mile": "10:19", "Tempo_400m": "2:34", "Interval_400m": "2:22", "Interval_800m": "4:44", "Interval_1000m": "5:55", "Interval_1200m": "7:06", "Interval_Mile": "9:28"},
])

DEFAULT_REST = pd.DataFrame([
    {"Workout": "Tempo 400s", "Pace / Time": "1:20 and faster", "Cycle / Rest": "2:30 Cycle"},
    {"Workout": "Tempo 400s", "Pace / Time": "1:22-1:24", "Cycle / Rest": "2:40 Cycle"},
    {"Workout": "Tempo 400s", "Pace / Time": "1:25-1:27", "Cycle / Rest": "2:50 Cycle"},
    {"Workout": "Tempo 400s", "Pace / Time": "1:28 and 1:29", "Cycle / Rest": "3:00 Cycle"},
    {"Workout": "Tempo 400s", "Pace / Time": "1:30-1:35", "Cycle / Rest": "3:10 Cycle"},
    {"Workout": "Tempo 400s", "Pace / Time": "1:36-1:40", "Cycle / Rest": "3:20 Cycle"},
    {"Workout": "Tempo 400s", "Pace / Time": "1:41 and slower", "Cycle / Rest": "Start next rep 2:00 after finish"},
    {"Workout": "800s (I Pace)", "Pace / Time": "Sub 17:30 (5K)", "Cycle / Rest": "5:00 Cycle"},
    {"Workout": "800s (I Pace)", "Pace / Time": "17:31-18:39 (5K)", "Cycle / Rest": "5:10 Cycle"},
    {"Workout": "800s (I Pace)", "Pace / Time": "18:40-19:16 (5K)", "Cycle / Rest": "5:25 Cycle"},
    {"Workout": "800s (I Pace)", "Pace / Time": "19:17-19:54 (5K)", "Cycle / Rest": "5:30 Cycle"},
    {"Workout": "800s (I Pace)", "Pace / Time": "19:55-20:59 (5K)", "Cycle / Rest": "5:40 Cycle"},
    {"Workout": "800s (I Pace)", "Pace / Time": "21:00-25:10 (5K)", "Cycle / Rest": "5:50 Cycle"},
    {"Workout": "800s (I Pace)", "Pace / Time": "25:11 and over (5K)", "Cycle / Rest": "6:00 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "Sub 17:30 (5K)", "Cycle / Rest": "6:00 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "17:49-18:23 (5K)", "Cycle / Rest": "6:15 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "18:40-18:57 (5K)", "Cycle / Rest": "6:30 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "19:17-19:36 (5K)", "Cycle / Rest": "6:45 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "19:55-20:39 (5K)", "Cycle / Rest": "7:00 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "21:02-25:10 (5K)", "Cycle / Rest": "7:45 Cycle"},
    {"Workout": "1000s (I Pace)", "Pace / Time": "25:46+ (5K)", "Cycle / Rest": "8:00 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "Under 17:33 (5K)", "Cycle / Rest": "6:10 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "17:34-18:23 (5K)", "Cycle / Rest": "6:45 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "18:40-18:57 (5K)", "Cycle / Rest": "6:55 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "18:58-19:36 (5K)", "Cycle / Rest": "7:05 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "19:37-20:39 (5K)", "Cycle / Rest": "7:25 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "20:40-25:10 (5K)", "Cycle / Rest": "7:45 Cycle"},
    {"Workout": "1200s (I Pace)", "Pace / Time": "All others", "Cycle / Rest": "Jog back to start, start when ready"},
    {"Workout": "Mile Intervals", "Pace / Time": "Sub 13:00 (2M)", "Cycle / Rest": "9:00 Cycle"},
    {"Workout": "Mile Intervals", "Pace / Time": "13:01-15:00 (2M)", "Cycle / Rest": "11:00 Cycle"},
    {"Workout": "Mile Intervals", "Pace / Time": "15:01-16:59 (2M)", "Cycle / Rest": "12:00 Cycle"},
    {"Workout": "Mile Intervals", "Pace / Time": "17:00+ (2M)", "Cycle / Rest": "13:30 Cycle"},
    {"Workout": "Hills (I Pace)", "Pace / Time": "Sub 22:00 (5K)", "Cycle / Rest": "10 minute cycle"},
    {"Workout": "Hills (I Pace)", "Pace / Time": "22:00-29:00 (5K)", "Cycle / Rest": "12 minute cycle"},
    {"Workout": "Hills (I Pace)", "Pace / Time": "29:00+ (5K)", "Cycle / Rest": "15 minute cycle"},
])

DEFAULT_DOCS = pd.DataFrame([
    {"Title": "Team Expectations & Rules", "URL": ""},
    {"Title": "Meet Schedule & Location Links", "URL": ""}
])

DEFAULT_ANNOUNCEMENTS = pd.DataFrame(columns=["ID","Title","Message","Link","Link_Label","Posted_By","Date_Posted","Active"])

_vdot = _fetch_vdot()
_rest = _fetch_rest()
_docs = _fetch_docs()
vdot_data          = _vdot if _vdot is not None else DEFAULT_VDOT
rest_data          = _rest if _rest is not None else DEFAULT_REST
docs_data          = _docs if _docs is not None else DEFAULT_DOCS
announcements_data = _fetch_announcements()


# Clean up data
for df, col in [(roster_data, "Username"), (races_data, "Username"), (workouts_data, "Username")]:
    if col in df.columns: df.dropna(subset=[col], inplace=True)

if "Active" in roster_data.columns:
    roster_data["Active_Clean"] = roster_data["Active"].astype(str).str.strip().str.upper()
else:
    roster_data["Active_Clean"] = "TRUE"
if "Gender" not in roster_data.columns: roster_data["Gender"] = "N/A"

for col in ["Date", "Meet_Name", "Race_Name", "Distance", "Username", "Mile_1", "Mile_2", "Total_Time", "Weight", "Active"]:
    if col not in races_data.columns:
        races_data[col] = 1.0 if col == "Weight" else ("TRUE" if col == "Active" else "")

races_data["Weight"] = pd.to_numeric(races_data["Weight"], errors="coerce").fillna(1.0)
races_data["Active"] = races_data["Active"].astype(str).str.strip().str.upper()
races_data.loc[races_data["Active"] == "NAN", "Active"] = "TRUE"

for col in ["Date", "Workout_Type", "Rep_Distance", "Weather", "Username", "Status", "Splits"]:
    if col not in workouts_data.columns: workouts_data[col] = ""

races_data["Season"] = races_data["Date"].apply(calculate_season)
workouts_data["Season"] = workouts_data["Date"].apply(calculate_season)

ACTIVE_FLAGS = ["TRUE", "1", "1.0"]

# ==========================================
# 4. SESSION STATE MANAGEMENT
# ==========================================
if "logged_in" not in st.session_state:
    st.session_state.update({"logged_in": False, "username": "", "first_name": "", "last_name": "", "role": "", "first_login": False})

for key in ["current_meet", "current_meet_date", "current_race", "current_distance"]:
    if key not in st.session_state: st.session_state[key] = None

if "workout_saved" not in st.session_state: st.session_state["workout_saved"] = False

def logout():
    st.session_state.update({"logged_in": False, "first_login": False, "workout_saved": False,
                              "username": "", "first_name": "", "last_name": "", "role": "",
                              "current_meet": None, "current_meet_date": None, "current_race": None, "current_distance": None})

def save_to_sheet(worksheet, data):
    """Helper to push data to Google Sheets, stripping helper columns."""
    push = data.drop(columns=["Active_Clean"]) if "Active_Clean" in data.columns else data
    conn.update(worksheet=worksheet, data=push)
    invalidate_workouts()

# ==========================================
# 5. VISUAL UI COMPONENTS & CHARTS
# ==========================================
def extract_seconds(time_str):
    m = re.search(r"(\d+):(\d+)", time_str)
    if m: return int(m.group(1)) * 60 + int(m.group(2))
    m2 = re.search(r"(\d+) minute", time_str)
    if m2: return int(m2.group(1)) * 60
    return None

def find_suggested_rest(category, compare_sec):
    if not compare_sec or pd.isna(compare_sec): return "Rest data unavailable"
    subset = rest_data[rest_data["Workout"].str.contains(category, case=False, na=False)]
    for _, row in subset.iterrows():
        cond = str(row["Pace / Time"]).lower()
        res = str(row["Cycle / Rest"])
        times = re.findall(r"(\d+:\d+)", cond)
        if ("sub" in cond or "under" in cond or "faster" in cond) and times and compare_sec < extract_seconds(times[0]): return res
        elif ("+" in cond or "slower" in cond or "over" in cond) and times and compare_sec >= extract_seconds(times[0]): return res
        elif len(times) == 2:
            lower, upper = extract_seconds(times[0]), extract_seconds(times[1])
            if lower <= compare_sec <= upper: return res
    return "Check Coach / Rest Chart directly"

def get_athlete_baseline(target_username):
    user_races = races_data[(races_data["Username"] == target_username) & (races_data["Active"].isin(ACTIVE_FLAGS))].copy()
    if user_races.empty: return None, None
    checks = [
        (lambda r: (r["Season"] == CURRENT_SEASON) & (r["Distance"].str.upper() == "5K"), "Current Season 5K PR"),
        (lambda r: (r["Season"] == CURRENT_SEASON) & (r["Distance"].str.upper() == "2 MILE"), "Current Season 2-Mile PR"),
        (lambda r: r["Distance"].str.upper() == "5K", "Past Season 5K PR"),
    ]
    for filt, label in checks:
        subset = user_races[filt(user_races) & (user_races["Total_Time"].str.strip() != "")]
        if not subset.empty:
            subset = subset.copy()
            subset["sec"] = subset["Total_Time"].apply(time_to_seconds)
            return subset["sec"].min(), label
    return None, None

def get_theme_val(key):
    return THEMES[st.session_state["theme"]][key]

def plotly_chart_defaults():
    return dict(template=get_theme_val("plotly_template"), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color=get_theme_val("text")))

def display_suggested_paces(target_username):
    st.subheader("Suggested Training Paces")
    st.markdown("""
    **What are these paces?** These suggested paces are based on the **VDOT system** (developed by legendary coach Jack Daniels). The system uses your recent race performances to measure your current fitness level and provides optimal paces to train at to maximize physiological benefits without overtraining.

    *Note: These are SUGGESTED paces. You must always adjust based on weather, if you are running on a difficult cross-country course vs a track, and how your body feels that day.*
    """)
    st.markdown("---")

    best_sec, baseline_source = get_athlete_baseline(target_username)
    vdot_df = vdot_data.copy()
    col_rename = {"5K_Time": "5K", "2_Mile_Time": "2-Mile", "Easy_Pace": "Easy", "Tempo_400m": "T 400m", "Tempo_Mile": "T Mile",
                  "Interval_400m": "I 400m", "Interval_800m": "I 800m", "Interval_1000m": "I 1000m", "Interval_1200m": "I 1200m", "Interval_Mile": "I Mile"}
    pace_cols = list(col_rename.keys())

    if not best_sec:
        st.info("**New Runner:** When you have races logged, you will see a personalized pace calculator here! For now, review the Master Pace Chart below.")
        st.markdown("### Master VDOT Pace Chart")
        st.dataframe(vdot_df[["VDOT"] + pace_cols].rename(columns=col_rename), hide_index=True, width='stretch')
        st.markdown("### Master Rest Cycles")
        st.dataframe(rest_data, hide_index=True, width='stretch')
        return

    vdot_df["sec"] = vdot_df["2_Mile_Time" if "2-Mile" in baseline_source else "5K_Time"].apply(time_to_seconds)
    closest_idx = (vdot_df["sec"] - best_sec).abs().idxmin()
    matched_row = vdot_df.loc[closest_idx]
    matched_vdot = matched_row["VDOT"]

    st.success(f"**Baseline Match:** Using your **{baseline_source}** ({seconds_to_time(best_sec)}) to calculate your current VDOT fitness level.")
    st.markdown("### Quick Pace & Rest Calculator")
    st.markdown("Select a workout below to instantly see your custom target time and rest cycle.")

    col_w1, col_w2, _ = st.columns([1, 1, 2])
    with col_w1: wk_type = st.selectbox("Workout Type", ["Intervals", "Tempo", "Easy Run", "Hills"])
    with col_w2:
        dist_opts = {"Intervals": ["400m", "800m", "1000m", "1200m", "1 Mile"], "Tempo": ["400m", "Miles"]}.get(wk_type)
        if dist_opts:
            wk_dist = st.selectbox("Distance", dist_opts)
        else:
            wk_dist = "N/A"
            st.selectbox("Distance", ["Any / Continuous"], disabled=True)

    vdot_5k_sec = time_to_seconds(matched_row.get("5K_Time", "0:0"))
    vdot_2m_sec = time_to_seconds(matched_row.get("2_Mile_Time", "0:0"))
    pace_rest_map = {
        ("Easy Run", "N/A"): (matched_row.get("Easy_Pace", "N/A"), "Continuous Run (No Rest)"),
        ("Tempo", "Miles"): (f"{matched_row.get('Tempo_Mile', 'N/A')} per Mile", "Standard Tempo Rest (Typically 1 min per mile)"),
        ("Tempo", "400m"): (f"{matched_row.get('Tempo_400m', 'N/A')} per 400m", find_suggested_rest("Tempo 400s", time_to_seconds(str(matched_row.get("Tempo_400m", ""))))),
        ("Hills", "N/A"): ("Run at I-Pace effort", find_suggested_rest("Hills", vdot_5k_sec)),
        ("Intervals", "400m"): (matched_row.get("Interval_400m", "N/A"), "Equal rest or Coach's Discretion"),
        ("Intervals", "800m"): (matched_row.get("Interval_800m", "N/A"), find_suggested_rest("800s", vdot_5k_sec)),
        ("Intervals", "1000m"): (matched_row.get("Interval_1000m", "N/A"), find_suggested_rest("1000s", vdot_5k_sec)),
        ("Intervals", "1200m"): (matched_row.get("Interval_1200m", "N/A"), find_suggested_rest("1200s", vdot_5k_sec)),
        ("Intervals", "1 Mile"): (matched_row.get("Interval_Mile", "N/A"), find_suggested_rest("Mile Intervals", vdot_2m_sec)),
    }
    target_pace, suggested_rest = pace_rest_map.get((wk_type, wk_dist), ("N/A", "N/A"))

    bg, border = get_theme_val("metric_bg"), get_theme_val("metric_border")
    st.markdown(f"""
    <div style="background-color: {bg}; border: 2px solid {border}; padding: 20px; border-radius: 10px; margin-top: 15px; margin-bottom: 30px;">
        <h4 style="margin-top: 0; padding-bottom: 10px; border-bottom: 1px solid {border};">{wk_type} ({wk_dist}) Target</h4>
        <p style="font-size: 18px; margin: 10px 0;"><strong>Target Pace:</strong> {target_pace}</p>
        <p style="font-size: 18px; margin: 0;"><strong>Rest Cycle:</strong> {suggested_rest}</p>
    </div>""", unsafe_allow_html=True)

    bracket_df = vdot_df.iloc[max(0, closest_idx - 1):min(len(vdot_df), closest_idx + 2)].copy()
    def highlight_match(row):
        return ['background-color: rgba(139, 35, 49, 0.2)'] * len(row) if row["VDOT"] == matched_vdot else [''] * len(row)

    st.markdown("### Your Target Pace Bracket")
    st.dataframe(bracket_df[["VDOT"] + pace_cols].rename(columns=col_rename).style.apply(highlight_match, axis=1), hide_index=True, width='stretch')
    st.markdown("### Master Rest Cycles")
    st.dataframe(rest_data, hide_index=True, width='stretch')

def display_team_resources():
    """
    Renders each team document as a responsive embedded iframe.

    Layout strategy:
    - The iframe uses width="100%" so it always fills the available column
      width on both desktop and mobile — no fixed pixel width.
    - A paddingBottom percentage trick (aspect-ratio container) is avoided
      here because Google Docs pages are tall and variable, so we use a
      fixed viewport height (85vh) instead — that fills most of the screen
      on any device without overflowing.
    - The "Open in new tab" link is shown prominently above the embed as the
      primary action on mobile, since pinch-zooming inside iframes is
      inconsistent across browsers. The embed below is a convenience preview.
    - Google Doc 'edit' links are converted to 'preview' links for embedding.
    - Google Doc 'pub' (Publish to Web) links are used as-is.
    """
    st.subheader("Team Resources")
    if docs_data.empty:
        st.info("No documents have been uploaded by the coaches yet.")
        return

    has_valid = False
    for _, row in docs_data.iterrows():
        url = str(row.get("URL", "")).strip()
        if not pd.notna(row.get("URL")) or not url.startswith("http"):
            continue
        has_valid = True

        # Convert Google Doc edit links to embeddable preview links
        if "edit" in url and "pub" not in url:
            url = url.replace("edit", "preview")

        title = str(row.get("Title", "Document"))
        st.markdown(f"#### {title}")

        # Primary action button — especially important on mobile where the
        # embed is a preview only. Styled as a solid pill button matching the
        # current theme accent color so it is easy to tap.
        _T = THEMES[st.session_state["theme"]]
        st.markdown(
            f'<a href="{url}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-block;margin-bottom:14px;padding:10px 22px;'
            f'background-color:{_T["line"]};color:#ffffff;font-size:14px;'
            f'font-weight:600;border-radius:6px;text-decoration:none;'
            f'box-shadow:0 2px 6px rgba(0,0,0,0.15);">'
            f'Open {title} &#8594;</a>',
            unsafe_allow_html=True
        )

        # Responsive iframe: 100% width, 85% of viewport height.
        # No fixed pixel widths — scales to any screen size automatically.
        st.markdown(f"""
        <div style="
            position: relative;
            width: 100%;
            height: 85vh;
            border: 1px solid #ccc;
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 32px;
        ">
            <iframe
                src="{url}"
                style="
                    position: absolute;
                    top: 0; left: 0;
                    width: 100%;
                    height: 100%;
                    border: none;
                "
                allowfullscreen="true"
            ></iframe>
        </div>
        """, unsafe_allow_html=True)

    if not has_valid:
        st.info("No active document links have been uploaded yet.")

def display_career_history(target_username):
    user_races = races_data[(races_data["Username"] == target_username) & (races_data["Active"].isin(ACTIVE_FLAGS))].copy()
    if user_races.empty:
        st.info("No race data found for career history.")
        return
    user_races["Time_Sec"] = user_races["Total_Time"].apply(time_to_seconds)
    user_races = user_races[user_races["Time_Sec"] > 0]
    found_any = False
    for dist in ["5K", "2 Mile"]:
        dist_races = user_races[user_races["Distance"].str.upper() == dist.upper()].copy()
        if dist_races.empty: continue
        found_any = True
        st.markdown(f"### {dist} Season-by-Season PRs")
        idx = dist_races.groupby("Season")["Time_Sec"].idxmin()
        prs = dist_races.loc[idx].sort_values("Season")
        prs["Season"] = prs["Season"].astype(str)
        fig = px.bar(prs, x="Season", y="Time_Sec", text="Total_Time", hover_data={"Meet_Name": True, "Date": True, "Time_Sec": False}, title=f"{dist} Progression")
        fig.update_traces(marker_color=get_theme_val("line"), textposition="outside", textfont=dict(size=14, color=get_theme_val("text")))
        fig.update_yaxes(visible=False, showgrid=False)
        fig.update_xaxes(title="", type="category")
        fig.update_layout(**plotly_chart_defaults(), margin=dict(t=40, b=0, l=0, r=0), height=300, bargap=0.1)
        col_chart, _ = st.columns([1, 1.5])
        with col_chart:
            st.plotly_chart(fig, width='stretch', theme=None)
        st.dataframe(prs[["Season", "Total_Time", "Meet_Name", "Date"]].rename(columns={"Total_Time": "PR Time", "Meet_Name": "Meet", "Date": "Date Achieved"}), hide_index=True, width='stretch')
        st.markdown("<br><br>", unsafe_allow_html=True)
    if not found_any: st.info("No valid races found to build progression history.")

def show_rankings_tab():
    st.subheader("Team Rankings & Season Grid")
    r_col1, r_col2, r_col3 = st.columns(3)
    available_seasons = sorted(races_data["Season"].unique().tolist(), reverse=True) or [CURRENT_SEASON]
    with r_col1: r_season = st.selectbox("Season", available_seasons, key="rankings_season")
    with r_col2: r_gender = st.selectbox("Category", ["Men's", "Women's"], key="rankings_category")
    with r_col3: r_dist = st.selectbox("Distance", ["5K", "2 Mile"], key="rankings_distance")

    target_gender = "Male" if r_gender == "Men's" else "Female"
    merged = pd.merge(races_data, roster_data[["Username", "First_Name", "Last_Name", "Gender", "Active_Clean"]], on="Username", how="inner")
    merged = merged[merged["Active_Clean"].isin(ACTIVE_FLAGS) & merged["Active"].isin(ACTIVE_FLAGS) &
                    (merged["Gender"].astype(str).str.title() == target_gender) & (merged["Distance"].astype(str).str.upper() == r_dist.upper()) & (merged["Season"] == r_season)]

    if merged.empty: return st.info("No active race data found for this category and season.")

    tab_lead, tab_grid = st.tabs(["Leaderboard", "Master Grid"])
    with tab_lead:
        r_metric = st.radio("Rank By:", ["Weighted Average", "Personal Record (PR)"], horizontal=True, key="rankings_metric")
        merged["Time_Sec"] = merged["Total_Time"].apply(time_to_seconds)
        merged["Weight"] = pd.to_numeric(merged["Weight"], errors="coerce").fillna(1.0)
        results = []
        for user, group in merged.groupby("Username"):
            valid = group[group["Weight"] > 0]
            if valid.empty: continue
            name = f"{group.iloc[0]['First_Name']} {group.iloc[0]['Last_Name']}"
            if r_metric == "Personal Record (PR)":
                best = valid["Time_Sec"].min()
                results.append({"Athlete": name, "Time_Sec": best, "Mark": seconds_to_time(best)})
            else:
                tw = valid["Weight"].sum()
                if tw <= 0: continue
                avg = (valid["Time_Sec"] * valid["Weight"]).sum() / tw
                results.append({"Athlete": name, "Time_Sec": avg, "Mark": seconds_to_time(avg)})
        if not results:
            st.info("No valid ranked data (check if races have a weight of 0).")
        else:
            rank_df = pd.DataFrame(results).sort_values("Time_Sec").reset_index(drop=True)
            rank_df.index += 1
            rank_df = rank_df.rename_axis("Rank").reset_index()
            label = "PR Time" if r_metric == "Personal Record (PR)" else "Weighted Avg Time"
            _, center_col, _ = st.columns([1, 2, 1])
            with center_col:
                st.dataframe(rank_df[["Rank", "Athlete", "Mark"]].rename(columns={"Mark": label}), hide_index=True, width='stretch')

    with tab_grid:
        st.markdown(f"### Master {r_dist} Grid")
        grid_df = merged.copy()
        grid_df["Athlete"] = grid_df["First_Name"] + " " + grid_df["Last_Name"]
        grid_df["Date_Obj"] = pd.to_datetime(grid_df["Date"], errors="coerce")
        grid_df = grid_df.sort_values("Date_Obj")
        grid_df["Race_Col"] = grid_df["Meet_Name"] + " (" + grid_df["Date_Obj"].dt.strftime("%m/%d").fillna("") + ") [" + grid_df["Weight"].apply(lambda x: f"{float(x):.1f}") + "x]"
        ordered_cols = grid_df["Race_Col"].unique().tolist()
        pivot_df = grid_df.pivot_table(index="Athlete", columns="Race_Col", values="Total_Time", aggfunc="first").reindex(columns=ordered_cols).fillna("-").reset_index()
        st.dataframe(pivot_df, hide_index=True, width='stretch')

def plot_athlete_progress(user_races):
    df = user_races[(user_races["Distance"].str.upper() == "5K") & (user_races["Time_Sec"] > 0)].copy()
    if df.empty or len(df) < 2: return
    df["Date_Obj"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date_Obj")
    df["Time_Min"] = df["Time_Sec"] / 60.0
    fig = px.line(df, x="Date_Obj", y="Time_Min", markers=True, text="Meet_Name", title="Current Season 5K Progression",
                  hover_data={"Date_Obj": "|%b %d, %Y", "Time_Min": False, "Total_Time": True, "Meet_Name": False})
    fig.update_traces(textposition="top center", line_color=get_theme_val("line"), line_width=3, marker_size=8)
    fig.update_yaxes(title="Finish Time (Minutes)")
    fig.update_xaxes(title="Race Date")
    fig.update_layout(**plotly_chart_defaults(), margin=dict(t=50, b=20, l=20, r=20))
    st.plotly_chart(fig, width='stretch', theme=None)
    st.markdown("---")

def display_athlete_races(username, season):
    st.subheader(f"Race Results: {season}")
    u_races = races_data[(races_data["Username"] == username) & (races_data["Active"].isin(ACTIVE_FLAGS)) & (races_data["Season"] == season)].copy()
    if u_races.empty:
        st.info("No races recorded for this season.")
        return
    u_races["Time_Sec"] = u_races["Total_Time"].apply(time_to_seconds)
    plot_athlete_progress(u_races)

    def calc_avg_pace(row):
        if not str(row.get("Total_Time", "")).strip(): return ""
        try:
            dist = 3.10686 if str(row["Distance"]).upper() == "5K" else 2.0
            avg_sec = row["Time_Sec"] / dist
            return f"{int(avg_sec // 60)}:{int(avg_sec % 60):02d}"
        except: return ""

    display_df = u_races[["Date", "Meet_Name", "Distance", "Mile_1", "Mile_2", "Total_Time", "Time_Sec"]].copy()
    display_df["Avg_Pace"] = display_df.apply(calc_avg_pace, axis=1)
    display_df.rename(columns={"Meet_Name": "Meet", "Mile_1": "Mile 1", "Mile_2": "Mile 2", "Total_Time": "Finish Time", "Avg_Pace": "Avg Pace"}, inplace=True)

    for dist in display_df["Distance"].unique():
        st.subheader(f"{dist} Races")
        dist_df = display_df[display_df["Distance"] == dist]
        cols = ["Date", "Meet", "Distance", "Mile 1", "Mile 2", "Finish Time", "Avg Pace"] if str(dist).upper() == "5K" else ["Date", "Meet", "Distance", "Mile 1", "Finish Time", "Avg Pace"]
        st.dataframe(dist_df[cols], hide_index=True, width='stretch')
        st.markdown("<br>", unsafe_allow_html=True)

def display_athlete_workouts(target_username, target_season):
    user_workouts = workouts_data[(workouts_data["Username"] == target_username) & (workouts_data["Season"] == target_season)].copy()
    if user_workouts.empty: return st.info("No workout data found for this season.")
    user_workouts["Date_Obj"] = pd.to_datetime(user_workouts["Date"], errors="coerce")
    user_workouts = user_workouts.sort_values("Date_Obj", ascending=False)
    for idx, row in user_workouts.iterrows():
        if not str(row["Weather"]).strip():
            user_workouts.at[idx, "Weather"] = get_weather_for_date(row["Date"])
    user_workouts["Date_Formatted"] = user_workouts["Date_Obj"].dt.strftime("%m/%d/%Y").fillna("Unknown")
    user_workouts["Combo"] = user_workouts["Workout_Type"] + " (" + user_workouts["Rep_Distance"] + ")"
    present_w = user_workouts[user_workouts["Status"] == "Present"]
    tab_log, tab_spread, tab_trend = st.tabs(["Workout Log", "Specific Session Variance", "Specific Workout Trends"])

    with tab_log:
        st.markdown("### Master Workout Log")
        st.dataframe(user_workouts[["Date_Formatted", "Workout_Type", "Rep_Distance", "Status", "Splits", "Weather"]].rename(
            columns={"Date_Formatted": "Date", "Workout_Type": "Type", "Rep_Distance": "Details"}), hide_index=True, width='stretch')

    with tab_spread:
        st.markdown("### Specific Session Variance")
        st.markdown("Analyze how steady your pacing was for a specific workout. **(Lower standard deviation = highly consistent pacing!)**")
        if present_w.empty:
            st.info("No completed workouts found to analyze.")
        else:
            col_w1, _ = st.columns([1, 2])
            with col_w1:
                w_opts = {idx: f"{row['Date_Formatted']} | {row['Workout_Type']} ({row['Rep_Distance']})" for idx, row in present_w.iterrows()}
                selected_w_idx = st.selectbox("Select a Workout to Analyze:", options=list(w_opts.keys()), format_func=lambda x: w_opts[x])
            w_row = present_w.loc[selected_w_idx]
            sec_splits = [time_to_seconds(s.strip()) for s in str(w_row["Splits"]).split(",") if time_to_seconds(s.strip()) > 0]
            if len(sec_splits) > 1:
                avg_sec, std_sec = np.mean(sec_splits), np.std(sec_splits, ddof=1)
                col_m1, col_m2 = st.columns(2)
                col_m1.metric("Average Pace", seconds_to_time(avg_sec))
                col_m2.metric("Consistency Variance (Standard Dev)", f"± {std_sec:.1f} sec")
                gdf = pd.DataFrame([{"Rep Number": f"Rep {i+1}", "Split Time": s, "Formatted": seconds_to_time(s)} for i, s in enumerate(sec_splits)])
                fig = px.scatter(gdf, x="Rep Number", y="Split Time", title="Interval Pacing Variance", hover_data={"Split Time": False, "Formatted": True})
                fig.update_traces(marker=dict(size=14, color=get_theme_val("line"), line=dict(width=2, color="DarkSlateGrey")))
                fig.update_layout(**plotly_chart_defaults())
                st.plotly_chart(fig, width='stretch', theme=None)
            else:
                st.info("This workout does not have enough split data to analyze variance.")

    with tab_trend:
        st.markdown("### Specific Workout Trends")
        st.markdown("Select a specific workout and distance to view your average pace dropping across the season.")
        if present_w.empty:
            st.info("No completed workouts found to analyze.")
        else:
            col_t1, _ = st.columns([1, 2])
            with col_t1:
                sel_combo = st.selectbox("Select Specific Workout to Compare:", present_w["Combo"].unique().tolist())
            type_w = present_w[present_w["Combo"] == sel_combo].sort_values("Date_Obj")
            trend_data = [{"Date": row["Date_Obj"], "Avg_Sec": np.mean(sl := [time_to_seconds(s.strip()) for s in str(row["Splits"]).split(",") if time_to_seconds(s.strip()) > 0]), "Formatted": seconds_to_time(np.mean(sl))}
                          for _, row in type_w.iterrows() if [s for s in str(row["Splits"]).split(",") if time_to_seconds(s.strip()) > 0]]
            if len(trend_data) > 1:
                tdf = pd.DataFrame(trend_data)
                tdf["Avg_Min"] = tdf["Avg_Sec"] / 60.0
                fig2 = px.line(tdf, x="Date", y="Avg_Min", markers=True, title=f"Average Pace Over Time: {sel_combo}", hover_data={"Date": "|%b %d", "Avg_Min": False, "Formatted": True})
                fig2.update_traces(line_color=get_theme_val("line"), line_width=3, marker_size=10)
                fig2.update_layout(**plotly_chart_defaults())
                st.plotly_chart(fig2, width='stretch', theme=None)
            else:
                st.info("You need to complete this specific workout at least twice to generate a trend line!")

# ==========================================
# 6. LOGIN & SECURITY PAGES
# ==========================================
def login_page():
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        st.title("MCXC Team Dashboard")
        st.markdown("Please log in to access your training data.")
        with st.form("login_form"):
            username = st.text_input("Username", autocomplete="off")
            password = st.text_input("Password", type="password", autocomplete="new-password")
            if st.form_submit_button("Log In", width='stretch'):
                user_row = roster_data[roster_data["Username"] == username]
                if user_row.empty:
                    st.error("Username not found.")
                else:
                    row = user_row.iloc[0]
                    if not str(row.get("Active", "TRUE")).strip().upper() in ACTIVE_FLAGS:
                        st.error("This account is no longer active.")
                    elif password == str(row["Password"]):
                        st.session_state.update({"logged_in": True, "username": username, "first_name": row["First_Name"],
                                                  "last_name": row["Last_Name"], "role": row["Role"],
                                                  "first_login": str(row["First_Login"]).strip().upper() in ACTIVE_FLAGS})
                        st.rerun()
                    else:
                        st.error("Incorrect password.")

def password_reset_page():
    _, col2, _ = st.columns([1, 1.5, 1])
    with col2:
        st.title("Welcome to the Team")
        st.markdown("Please create a new, secure password to continue.")
        with st.form("reset_password_form"):
            new_password = st.text_input("New Password", type="password", autocomplete="new-password")
            confirm_password = st.text_input("Confirm New Password", type="password", autocomplete="new-password")
            if st.form_submit_button("Update Password", width='stretch'):
                if len(new_password) < 4: st.error("Password must be at least 4 characters long.")
                elif new_password != confirm_password: st.error("Passwords do not match.")
                else:
                    idx = roster_data.index[roster_data["Username"] == st.session_state["username"]].tolist()[0]
                    roster_data.at[idx, "Password"] = new_password
                    roster_data.at[idx, "First_Login"] = "FALSE"
                    with st.spinner("Updating account..."): save_to_sheet("Roster", roster_data)
                    st.session_state["first_login"] = False
                    st.rerun()

# ==========================================
# 7. HOME PAGE ROUTER
# ==========================================

def _render_settings_overlay():
    """
    A fully custom settings panel that replaces st.sidebar entirely.

    WHY we stopped using st.sidebar:
      Streamlit's native sidebar is collapsed and hidden off-screen on mobile.
      There is no reliable, version-stable way to programmatically open it via
      JavaScript — Streamlit Cloud updates break selectors regularly, and
      st.markdown scripts can't guarantee timing vs DOM readiness.

    HOW this works instead:
      - A branded gradient bar sits pinned at the top of every logged-in page.
      - It contains a single Streamlit button: "⚙️ Settings" / "✖ Close".
      - Clicking it flips session_state["settings_open"] True/False and reruns.
      - When open, a styled container renders BELOW the bar with theme + logout.
      - On desktop this is a minor change in appearance (panel at top instead
        of left) but is still clean and fast.
      - On mobile it works perfectly — no sidebar clipping, no JS, no iframes.

    The theme selectbox and logout button only exist once on the page
    (inside this function), so there are zero duplicate-key risks.
    """
    if "settings_open" not in st.session_state:
        st.session_state["settings_open"] = False

    # --- Gradient bar with toggle button ---
    btn_label = "✖ Close Settings" if st.session_state["settings_open"] else "⚙️ Settings"
    bar_col, btn_col = st.columns([6, 1])
    with bar_col:
        st.markdown(f"""
            <div style="
                background: linear-gradient(to right, {MCXC_CRIMSON}, {MCXC_NAVY});
                height: 38px;
                border-radius: 0 0 8px 0;
                margin-top: -4px;
            "></div>
        """, unsafe_allow_html=True)
    with btn_col:
        if st.button(btn_label, key="settings_toggle_btn", width='stretch'):
            st.session_state["settings_open"] = not st.session_state["settings_open"]
            st.rerun()

    # --- Collapsible settings panel ---
    if st.session_state["settings_open"]:
        panel_bg     = THEMES[st.session_state["theme"]]["sidebar_bg"]
        panel_border = THEMES[st.session_state["theme"]]["metric_border"]
        panel_text   = THEMES[st.session_state["theme"]]["text"]

        st.markdown(f"""
            <div style="
                background-color: {panel_bg};
                border: 1px solid {panel_border};
                border-radius: 8px;
                padding: 18px 24px 12px 24px;
                margin-bottom: 16px;
            ">
                <p style="margin:0 0 12px 0; font-weight:700;
                           font-size:16px; color:{panel_text};">
                    ⚙️ Settings
                </p>
            </div>
        """, unsafe_allow_html=True)

        # Narrow centre column so the panel doesn't stretch full-width on desktop
        _, mid, _ = st.columns([1, 2, 1])
        with mid:
            theme_keys = list(THEMES.keys())
            chosen = st.selectbox(
                "App Theme",
                theme_keys,
                index=theme_keys.index(st.session_state["theme"]),
                key="settings_theme_select"
            )
            if chosen != st.session_state["theme"]:
                st.session_state["theme"] = chosen
                st.rerun()

            st.markdown("<br>", unsafe_allow_html=True)
            st.button(
                "Log Out",
                on_click=logout,
                width='stretch',
                key="settings_logout_btn"
            )
        st.markdown("---")


def home_page():
    """
    Main page router — shown after login.

    Settings are handled entirely by _render_settings_overlay(), which renders
    a branded bar + collapsible panel at the top of the page. st.sidebar is no
    longer used, eliminating all mobile clipping issues.
    """
    user_role = str(st.session_state["role"]).capitalize()

    # --- Settings bar (top of page, works on every screen size) ---
    _render_settings_overlay()

    st.title(f"{user_role}: {st.session_state['first_name']} {st.session_state['last_name']}")
    st.markdown("---")

    if user_role.upper() == "COACH":
        _coach_view()
    else:
        _athlete_view()


# ==========================================
# COACH TAB: ATHLETE LOOKUP
# ==========================================
def _tab_athlete_lookup():
    """View any athlete's full race and workout history, paces, and career PRs."""
    st.subheader("Athlete Lookup")
    col1, col2, col3 = st.columns(3)
    filter_status = col1.selectbox("Filter by Status:", ["Active", "Archived", "All"])
    filter_gender = col2.selectbox("Filter by Gender:", ["All", "Male", "Female"])
    filter_grade  = col3.selectbox("Filter by Grade:", ["All", "9th", "10th", "11th", "12th", "Middle School"])

    base = roster_data[roster_data["Role"].str.upper() == "ATHLETE"].copy()
    if filter_status == "Active":
        base = base[base["Active_Clean"].isin(ACTIVE_FLAGS)]
    elif filter_status == "Archived":
        base = base[~base["Active_Clean"].isin(ACTIVE_FLAGS)]

    base["Grade"] = base.get("Grad_Year", "Unknown").apply(get_grade_level)
    if filter_gender != "All": base = base[base["Gender"].str.title() == filter_gender]
    if filter_grade  != "All": base = base[base["Grade"] == filter_grade]
    base = base.sort_values(["Last_Name", "First_Name"])
    athlete_dict = {row["Username"]: f"{row['Last_Name']}, {row['First_Name']} - {row['Grade']}"
                    for _, row in base.iterrows()}

    if not athlete_dict:
        st.info("No athletes match this filter.")
        return

    col_sel1, _ = st.columns([1, 2])
    with col_sel1:
        selected_username = st.selectbox("Select an Athlete:", options=list(athlete_dict.keys()),
                                          format_func=lambda x: athlete_dict[x])
    if selected_username:
        st.markdown("---")
        target = base[base["Username"] == selected_username].iloc[0]
        st.markdown(f"### {target['First_Name']} {target['Last_Name']} ({target['Grade']})")
        u_races = races_data[races_data["Username"] == selected_username]
        u_works = workouts_data[workouts_data["Username"] == selected_username]
        athlete_seasons = sorted(set(u_races["Season"].tolist() + u_works["Season"].tolist()), reverse=True) or [CURRENT_SEASON]
        col_s1, _ = st.columns([1, 3])
        with col_s1:
            sel_season = st.selectbox("View Season:", athlete_seasons, key="coach_athlete_season")
        sub1, sub2, sub3, sub4 = st.tabs(["Race Results", "Workouts", "Training Paces", "Career PRs"])
        with sub1: display_athlete_races(selected_username, sel_season)
        with sub2: display_athlete_workouts(selected_username, sel_season)
        with sub3: display_suggested_paces(selected_username)
        with sub4: display_career_history(selected_username)


# ==========================================
# COACH TAB: ROSTER MANAGEMENT
# ==========================================
def _tab_roster_management():
    """Add, edit, archive, and restore team members."""
    st.subheader("Roster Management")
    roster_action = st.radio(
        "Choose an action:",
        ["View Current Roster", "Add New Member", "Edit Member", "Archive / Restore"],
        horizontal=True
    )
    st.markdown("---")

    if roster_action == "View Current Roster":
        active_roster = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)].copy()
        if "Grad_Year" in active_roster.columns:
            active_roster["Grade"] = active_roster["Grad_Year"].apply(get_grade_level)
            display_roster = active_roster[["First_Name", "Last_Name", "Gender", "Grade", "Grad_Year", "Role"]].copy()
            display_roster["Grad_Year"] = display_roster["Grad_Year"].astype(str)  # prevent Arrow int64 cast error
            display_roster["Sort_Year"] = pd.to_numeric(display_roster["Grad_Year"], errors="coerce").fillna(9999)
            display_roster = display_roster.sort_values(["Role", "Sort_Year", "Gender", "Last_Name"]).drop(columns=["Sort_Year"])
            st.dataframe(display_roster, hide_index=True, width='stretch')
        else:
            st.dataframe(active_roster[["First_Name", "Last_Name", "Role"]].sort_values("Last_Name"), hide_index=True)

    elif roster_action == "Add New Member":
        # Show success banner from previous submit (survives st.rerun)
        if st.session_state.get("roster_added"):
            name, un = st.session_state["roster_added"]
            st.success(f"Added {name}. Username: '{un}'. Default password: 'changeme'.")
            st.session_state["roster_added"] = None

        # Role selector lives OUTSIDE the form so changing it rerenders the page
        # and can show/hide the athlete-only fields dynamically.
        r3, _ = st.columns([1, 2])
        with r3:
            new_role = st.selectbox("Role", ["Athlete", "Coach"], key="new_member_role")

        with st.form("add_member_form", clear_on_submit=True):
            r1, r2 = st.columns(2)
            new_first = r1.text_input("First Name", autocomplete="off")
            new_last  = r2.text_input("Last Name", autocomplete="off")

            # Only show Grad Year and Gender for athletes — coaches don't need them
            if new_role == "Athlete":
                r4, r5 = st.columns(2)
                new_grad_year = r4.text_input("Grad Year (e.g., 2028)", autocomplete="off")
                new_gender    = r5.selectbox("Gender", ["Male", "Female", "N/A"])
            else:
                new_grad_year = "Coach"
                new_gender    = "N/A"
                st.caption("Grad Year and Gender are set to N/A automatically for coaches.")

            if st.form_submit_button("Add to Roster"):
                if not new_first or not new_last:
                    st.error("First and Last name are required.")
                else:
                    if new_role == "Coach":
                        final_grad_year = "Coach"
                        final_gender    = "N/A"
                        # Coaches get "coach.lastname" username format
                        base_un = f"coach.{new_last.lower()}".replace(" ", "")
                    else:
                        final_grad_year = new_grad_year.strip()
                        final_gender    = new_gender
                        if not final_grad_year.isdigit() or len(final_grad_year) != 4:
                            st.error("Graduation Year must be a 4-digit number.")
                            st.stop()
                        base_un = f"{new_first.lower()}.{new_last.lower()}".replace(" ", "")

                    # Ensure username is unique
                    gen_un, suffix = base_un, 1
                    while gen_un in roster_data["Username"].tolist():
                        gen_un = f"{base_un}{suffix}"; suffix += 1

                    new_row = pd.DataFrame([{
                        "Username":    gen_un,
                        "Password":    "changeme",
                        "First_Name":  new_first,
                        "Last_Name":   new_last,
                        "Role":        new_role,
                        "First_Login": "TRUE",
                        "Active":      "TRUE",
                        "Grad_Year":   final_grad_year,
                        "Gender":      final_gender
                    }])
                    push = roster_data.drop(columns=["Active_Clean"]) if "Active_Clean" in roster_data.columns else roster_data
                    updated = pd.concat([push, new_row], ignore_index=True)
                    with st.spinner("Adding new member..."):
                        conn.update(worksheet="Roster", data=updated)
                    # Store in session state so success message survives rerun
                    st.session_state["roster_added"] = (f"{new_first} {new_last}", gen_un)
                    invalidate_roster()
                    st.rerun()

    elif roster_action == "Edit Member":
        st.info("Note: Usernames cannot be changed.")
        active = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)]
        edit_dict = {row["Username"]: f"{row['First_Name']} {row['Last_Name']} ({row.get('Role','')})"
                     for _, row in active.iterrows()}
        if not edit_dict:
            st.info("No active members to edit.")
        else:
            col_e1, _ = st.columns([1, 1])
            with col_e1:
                user_to_edit = st.selectbox("Select Member to Edit:", options=list(edit_dict.keys()),
                                             format_func=lambda x: edit_dict[x])
            if user_to_edit:
                target_row = roster_data[roster_data["Username"] == user_to_edit].iloc[0]
                with st.form("edit_member_form"):
                    e1, e2 = st.columns(2)
                    edit_first = e1.text_input("First Name", value=target_row["First_Name"], autocomplete="off")
                    edit_last  = e2.text_input("Last Name",  value=target_row["Last_Name"],  autocomplete="off")
                    e3, e4 = st.columns(2)
                    role_index = 0 if str(target_row["Role"]).title() == "Athlete" else 1
                    edit_role      = e3.selectbox("Role", ["Athlete", "Coach"], index=role_index)
                    edit_grad_year = e4.text_input("Grad Year", value=str(target_row.get("Grad_Year", "")), autocomplete="off")
                    e5, _ = st.columns(2)
                    gender_val  = str(target_row.get("Gender", "N/A")).title()
                    gender_opts = ["Male", "Female", "N/A"]
                    g_index     = gender_opts.index(gender_val) if gender_val in gender_opts else 2
                    edit_gender = e5.selectbox("Gender", gender_opts, index=g_index)
                    if st.form_submit_button("Save Changes"):
                        if edit_role != "Coach" and (not edit_grad_year.strip().isdigit() or len(edit_grad_year.strip()) != 4):
                            st.error("Graduation Year must be a 4-digit number.")
                            st.stop()
                        idx = roster_data.index[roster_data["Username"] == user_to_edit].tolist()[0]
                        roster_data.at[idx, "First_Name"] = edit_first
                        roster_data.at[idx, "Last_Name"]  = edit_last
                        roster_data.at[idx, "Role"]       = edit_role
                        roster_data.at[idx, "Grad_Year"]  = "Coach" if edit_role == "Coach" else edit_grad_year.strip()
                        roster_data.at[idx, "Gender"]     = "N/A"   if edit_role == "Coach" else edit_gender
                        with st.spinner("Saving changes..."): save_to_sheet("Roster", roster_data)
                        st.success("Member updated successfully."); st.rerun()

    elif roster_action == "Archive / Restore":
        arc_tab1, arc_tab2, arc_tab3 = st.tabs(["Archive Individual", "Restore Member", "Graduate Seniors"])
        with arc_tab1:
            active = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)]
            arc_dict = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}" for _, row in active.iterrows()}
            if not arc_dict:
                st.info("No active members to archive.")
            else:
                col1, _ = st.columns([1, 2])
                with col1:
                    user_to_archive = st.selectbox("Select Member to Archive:", options=list(arc_dict.keys()),
                                                    format_func=lambda x: arc_dict[x])
                if st.button("Archive Member"):
                    idx = roster_data.index[roster_data["Username"] == user_to_archive].tolist()[0]
                    roster_data.at[idx, "Active"] = "FALSE"
                    save_to_sheet("Roster", roster_data); st.rerun()

        with arc_tab2:
            inactive = roster_data[~roster_data["Active_Clean"].isin(ACTIVE_FLAGS)]
            restore_dict = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}" for _, row in inactive.iterrows()}
            if not restore_dict:
                st.info("There are no archived members to restore.")
            else:
                col1, _ = st.columns([1, 2])
                with col1:
                    user_to_restore = st.selectbox("Select Member to Restore:", options=list(restore_dict.keys()),
                                                    format_func=lambda x: restore_dict[x])
                if st.button("Restore Member"):
                    idx = roster_data.index[roster_data["Username"] == user_to_restore].tolist()[0]
                    roster_data.at[idx, "Active"] = "TRUE"
                    save_to_sheet("Roster", roster_data); st.rerun()

        with arc_tab3:
            st.warning("This will archive all active runners currently calculated as 12th grade.")
            active_df = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)].copy()
            active_df["Grade"] = active_df.get("Grad_Year", "Unknown").apply(get_grade_level)
            seniors = active_df[active_df["Grade"] == "12th"]
            if seniors.empty:
                st.info("No active seniors found.")
            else:
                for _, s in seniors.iterrows():
                    st.markdown(f"- {s['First_Name']} {s['Last_Name']}")
                if st.button("Confirm: Archive All Seniors"):
                    for _, s in seniors.iterrows():
                        idx = roster_data.index[roster_data["Username"] == s["Username"]].tolist()[0]
                        roster_data.at[idx, "Active"] = "FALSE"
                    with st.spinner("Archiving seniors..."): save_to_sheet("Roster", roster_data)
                    st.rerun()


# ---- COACH VIEW ----
def _coach_view():
    """
    Coach tab structure:
      1. Athlete Lookup  — view any athlete's stats
      2. Printables      — create/print meet sheets, workout sheets, attendance
      3. Data Entry      — enter race results and workout splits after the event
      4. Rankings        — team leaderboard and master grid
      5. Roster          — manage members
      6. Manage          — meet weights, archive, VDOT/rest tables, documents
    """
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "Athlete Lookup",
        "Printables",
        "Data Entry",
        "Rankings",
        "Roster",
        "Manage",
    ])
    with tab1: _tab_athlete_lookup()
    with tab2: _tab_printables()
    with tab3: _tab_data_entry()
    with tab4: show_rankings_tab()
    with tab5: _tab_roster_management()
    with tab6: _tab_manage()

# ==========================================
# COACH TAB: PRINTABLES
# ==========================================
def _tab_printables():
    """
    Everything the coach touches BEFORE a practice or meet:
      - Meet Sheets: create new meet + print, or reprint an existing one
      - Workout Sheets: configure and print a blank workout clipboard sheet
      - Attendance Sheets: blank weekly sign-in grids
    """
    st.subheader("Printables")
    st.markdown("Generate sheets to bring to practice or a meet. Data entry happens in the **Data Entry** tab after the event.")
    action = st.radio(
        "What do you need?",
        ["Meet Sheet — Create New", "Meet Sheet — Reprint Existing", "Workout Sheet", "Attendance Sheet"],
        horizontal=True
    )
    st.markdown("---")

    if action == "Meet Sheet — Create New":
        _printable_new_meet()
    elif action == "Meet Sheet — Reprint Existing":
        _printable_reprint_meet()
    elif action == "Workout Sheet":
        _printable_workout_sheet()
    elif action == "Attendance Sheet":
        _printable_attendance()


def _printable_new_meet():
    """
    Coach fills in meet name, date, optional prior-year meet link, and assigns
    runners to each race.

    Prior Meet Name logic:
    - A dropdown shows all distinct meet names from previous seasons.
    - If selected, the split sheet pulls Prior Best times from BOTH the current
      meet name AND the linked prior name, so year-to-year name changes like
      "Great American XC 2025" -> "Great American XC 2026" don't break history.
    - The prior name is stored as Prior_Meet_Name on every row for this meet
      so the reprint function can use it too without re-asking.
    """
    st.markdown("### Create New Meet & Print Split Sheet")
    st.markdown("Assign runners to each race below. This saves the meet to the database so you can enter times in **Data Entry** after the meet.")

    c_m1, c_m2 = st.columns(2)
    with c_m1: p_meet = st.text_input("Meet Name", placeholder="e.g. Great American XC 2026", autocomplete="off")
    with c_m2: p_date = st.date_input("Meet Date")

    # Prior meet name — all unique meet names from past seasons
    past_meets = sorted(
        races_data[races_data["Season"] != CURRENT_SEASON]["Meet_Name"]
        .dropna().unique().tolist()
    )
    st.markdown("**Link to Previous Year's Meet** *(optional — pulls prior PRs even if the meet name changed)*")
    col_pm, _ = st.columns([1, 2])
    with col_pm:
        prior_opts = ["None (brand new meet)"] + past_meets
        prior_meet_sel = st.selectbox(
            "Previous year's version of this meet:",
            prior_opts,
            key="new_meet_prior"
        )
    prior_meet_name = None if prior_meet_sel == "None (brand new meet)" else prior_meet_sel
    if prior_meet_name:
        st.caption(f"Prior Best times will be pulled from both \"{p_meet}\" and \"{prior_meet_name}\".")

    st.markdown("---")
    race_count = st.number_input("How many separate races?", min_value=1, max_value=10, value=2)

    active_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") &
                                   (roster_data["Active_Clean"].isin(ACTIVE_FLAGS))].copy()
    assigned_runners = set()
    for j in range(race_count):
        assigned_runners.update(st.session_state.get(f"rrunners_{j}", []))

    races_to_print = []
    for i in range(race_count):
        st.markdown(f"**Race {i+1}**")
        r_col1, r_col2, r_col3 = st.columns([2, 1, 1])
        with r_col1: r_name = st.text_input("Race Title", placeholder="e.g. Boys Varsity", key=f"rname_{i}", autocomplete="off")
        with r_col2: r_dist = st.selectbox("Distance", ["5K", "2 Mile", "Other"], key=f"rdist_{i}")
        with r_col3: r_filter = st.selectbox("Filter Runners", ["All", "Boys", "Girls"], key=f"rfilt_{i}")
        avail = active_athletes.copy()
        if r_filter == "Boys": avail = avail[avail["Gender"].str.title() == "Male"]
        elif r_filter == "Girls": avail = avail[avail["Gender"].str.title() == "Female"]
        other = assigned_runners - set(st.session_state.get(f"rrunners_{i}", []))
        avail = avail[~avail["Username"].isin(other)]
        opts = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}"
                for _, row in avail.sort_values("Last_Name").iterrows()}
        r_runners = st.multiselect("Select Runners", options=list(opts.keys()),
                                   format_func=lambda x: opts[x], key=f"rrunners_{i}")
        if r_name and r_runners:
            races_to_print.append({"name": r_name, "dist": r_dist, "runners": r_runners})
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("💾 Save Meet & Generate Sheet", type="primary"):
        if not p_meet:
            st.error("Please enter a Meet Name.")
        elif not races_to_print:
            st.warning("Please configure at least one race with runners.")
        else:
            formatted_date = pd.to_datetime(p_date).strftime("%Y-%m-%d")
            season = calculate_season(formatted_date)
            new_rows = [
                {"Date": formatted_date, "Meet_Name": p_meet, "Race_Name": race["name"],
                 "Distance": race["dist"], "Username": uname, "Mile_1": "", "Mile_2": "",
                 "Total_Time": "", "Weight": 1.0, "Active": "TRUE", "Season": season,
                 "Prior_Meet_Name": prior_meet_name or ""}
                for race in races_to_print for uname in race["runners"]
                if races_data[(races_data["Meet_Name"] == p_meet) &
                              (races_data["Race_Name"] == race["name"]) &
                              (races_data["Username"] == uname)].empty
            ]
            if new_rows:
                updated = pd.concat([races_data, pd.DataFrame(new_rows)], ignore_index=True)
                with st.spinner("Saving meet to database..."):
                    conn.update(worksheet="Races", data=updated)
                invalidate_races()
            html_body = _build_split_sheet_html(
                p_meet, races_data, roster_data, races_to_print,
                meet_date=p_date, prior_meet_name=prior_meet_name
            )
            final_html = wrap_html_for_print(f"{p_meet} Split Sheet", html_body)
            st.success(f"'{p_meet}' saved! Download your sheet below, then enter times in **Data Entry** after the meet.")
            st.download_button(
                label="⬇️ Download Split Sheet (HTML)",
                data=final_html,
                file_name=f"{p_meet.replace(' ', '_')}_{pd.to_datetime(p_date).strftime('%Y-%m-%d')}_SplitSheet.html",
                mime="text/html"
            )
def _printable_reprint_meet():
    """
    Reprint the split sheet for any existing active meet.

    Two modes:
    - Blank: empty time columns — use as a clipboard sheet at the meet.
    - Filled: actual recorded times shown, runners sorted by finish time.
      Use this to review results or share a printed summary after the meet.
    """
    st.markdown("### Reprint Existing Meet Split Sheet")
    active_meets = races_data[races_data["Active"].isin(ACTIVE_FLAGS)]["Meet_Name"].dropna().unique().tolist()
    if not active_meets:
        st.info("No active meets found. Create one under 'Meet Sheet — Create New'.")
        return

    col1, col2 = st.columns([1, 1])
    with col1:
        p_meet = st.selectbox("Select Meet", ["-- Select --"] + active_meets)
    with col2:
        sheet_mode = st.radio(
            "Sheet Type",
            ["Blank (clipboard)", "Filled (with results)"],
            horizontal=True,
            key="reprint_mode"
        )

    if p_meet == "-- Select --":
        return

    meet_rows  = races_data[races_data["Meet_Name"] == p_meet]
    meet_date  = meet_rows["Date"].iloc[0] if not meet_rows.empty else None
    filled     = sheet_mode == "Filled (with results)"

    # Check if any times exist when filled mode is selected
    if filled:
        has_times = meet_rows["Total_Time"].str.strip().ne("").any()
        if not has_times:
            st.warning("No finish times have been entered for this meet yet. "
                       "The filled sheet will show blank time columns. "
                       "Enter times in Data Entry → Race Results first.")

    # Recover stored Prior_Meet_Name
    stored_prior = ""
    if "Prior_Meet_Name" in meet_rows.columns:
        vals = meet_rows["Prior_Meet_Name"].dropna().unique().tolist()
        stored_prior = vals[0] if vals else ""
    stored_prior = stored_prior if stored_prior and stored_prior != "nan" else ""
    if stored_prior:
        st.caption(f'Prior Best times will be pulled from this meet AND "{stored_prior}".')

    btn_label = "Generate Results Sheet" if filled else "Generate Blank Sheet"
    if st.button(btn_label, type="primary"):
        try:
            date_str = pd.to_datetime(meet_date).strftime('%Y-%m-%d')
        except:
            date_str = str(meet_date or "")
        html_body = _build_split_sheet_html(
            p_meet, races_data, roster_data,
            meet_date=meet_date, prior_meet_name=stored_prior or None,
            filled=filled
        )
        sheet_label = "Results" if filled else "SplitSheet"
        final_html  = wrap_html_for_print(
            f"{p_meet} {'Results' if filled else 'Split Sheet'}",
            html_body
        )
        st.success("Sheet ready!")
        st.download_button(
            label=f"⬇️ Download {'Results' if filled else 'Blank Split'} Sheet (HTML)",
            data=final_html,
            file_name=f"{p_meet.replace(' ', '_')}_{date_str}_{sheet_label}.html",
            mime="text/html"
        )


def _printable_workout_sheet():
    """
    Workout sheet printer with two modes:

    Blank  — blank rep columns, rest cycle table at bottom.
             Use before practice as the clipboard recording sheet.
    Filled — actual recorded splits shown per athlete per rep.
             Use after practice to review or file results on paper.

    The filled sheet is generated from the Workouts Google Sheet, so
    times must be entered in Data Entry → Workouts first.
    """
    st.markdown("### Print Workout Sheet")

    w_col0, w_col1_pad = st.columns([2, 3])
    with w_col0:
        sheet_mode = st.radio(
            "Sheet Type",
            ["Blank (before practice)", "Filled (with results)"],
            horizontal=True, key="ws_mode"
        )
    st.markdown("---")
    filled = sheet_mode == "Filled (with results)"

    w_col1, w_col2, w_col3 = st.columns(3)

    with w_col1:
        w_date = st.date_input("Workout Date", key="ws_date")

    if filled:
        # Filled mode: just needs the date — pulls all workouts for that day
        with w_col2:
            day_str = pd.to_datetime(w_date).strftime("%Y-%m-%d")
            day_workouts = workouts_data[workouts_data["Date"] == day_str]
            if day_workouts.empty:
                st.info("No workouts logged for this date yet.")
            else:
                combos = day_workouts[["Workout_Type","Rep_Distance"]].drop_duplicates()
                st.markdown("**Found on this date:**")
                for _, row in combos.iterrows():
                    st.markdown(f"- {row['Workout_Type']} ({row['Rep_Distance']})")

        if st.button("Generate Filled Workout Sheet", type="primary"):
            day_str = pd.to_datetime(w_date).strftime("%Y-%m-%d")
            html_body, force_landscape = _build_filled_workout_sheet_html(
                day_str, workouts_data, roster_data, races_data
            )
            final_html = wrap_html_for_print(
                f"Workout Results — {w_date.strftime('%Y-%m-%d')}",
                html_body,
                force_landscape=force_landscape
            )
            orient = "landscape" if force_landscape else "portrait"
            st.success(f"Filled workout sheet ready! ({orient})")
            st.download_button(
                label="⬇️ Download Filled Workout Sheet (HTML)",
                data=final_html,
                file_name=f"Workout_Results_{w_date.strftime('%Y-%m-%d')}.html",
                mime="text/html"
            )
    else:
        # Blank mode: needs workout type, distance, rep count
        with w_col1:
            w_type = st.selectbox("Workout Type", ["Intervals", "Tempo", "Hills", "Other"], key="ws_type")
        with w_col2:
            dist_opts_map = {
                "Intervals": ["400m", "800m", "1000m", "1200m", "1 Mile", "Custom"],
                "Tempo":     ["400m", "Miles", "Split", "Custom"],
                "Hills":     ["400m", "800m", "Short Sprints", "Custom"],
                "Other":     ["Custom"],
            }
            dist_options = dist_opts_map.get(w_type, ["Custom"])
            sel_dist = st.selectbox("Rep Distance", dist_options, key="ws_dist")
            if sel_dist == "Custom":
                w_dist = st.text_input("Specify distance/details", placeholder="e.g. 2+1 mile", autocomplete="off", key="ws_custom_dist")
            else:
                w_dist = sel_dist
            rep_count = st.number_input("Number of Rep Columns", min_value=1, max_value=20, value=5, key="ws_reps")
        with w_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            orient_note = "landscape" if rep_count > 7 else "portrait"
            st.info(f"{rep_count} rep columns → **{orient_note}**")

        if st.button("Generate Blank Workout Sheet", type="primary"):
            if not w_dist:
                st.error("Please specify the rep distance/details.")
                return
            html_body, force_landscape = _build_workout_sheet_html(
                w_type, w_dist, w_date, rep_count,
                roster_data, races_data, rest_data
            )
            final_html = wrap_html_for_print(
                f"Workout Sheet — {w_type} {w_dist}",
                html_body,
                force_landscape=force_landscape
            )
            st.success(f"Blank workout sheet ready! ({orient_note} — Boys and Girls on separate pages)")
            st.download_button(
                label="⬇️ Download Blank Workout Sheet (HTML)",
                data=final_html,
                file_name=f"Workout_{w_type}_{w_dist.replace(' ','_')}_{w_date.strftime('%Y-%m-%d')}.html",
                mime="text/html"
            )


def _printable_attendance():
    """
    Blank weekly attendance sign-in sheet. Always portrait, always one page.

    Design decisions:
    - The attendance sheet gets its OWN wrap function (_wrap_attendance) instead
      of wrap_html_for_print because it needs a completely different CSS
      strategy: aggressive font/padding compression and @page zoom to guarantee
      a single page up to ~45 athletes.
    - Name column is narrow (fixed at 130px) — just enough for "Last, First".
    - Check columns are 28px wide — only need to hold a tick mark.
    - Row height is 18px printed — tight but readable for a checkbox list.
    - @page uses size:portrait and zoom:0.85 so even a 40-runner roster fits.
      For 50+ it will spill to a second page naturally rather than break layout.
    - Alternating day shading (not row shading) so it's easy to track columns.
    """
    st.markdown("### Print Attendance Sheet")
    col_a1, col_a2, col_a3 = st.columns(3)
    p_gender = col_a1.selectbox("Team", ["Boys", "Girls"], key="att_gender")
    p_type   = col_a2.selectbox("Season Type", ["Summer", "School Year"], key="att_type")
    p_week   = col_a3.text_input("Week Of (e.g., Aug 12–16)", key="att_week")

    if st.button("Generate Attendance Sheet", type="primary"):
        target_gender = "Male" if p_gender == "Boys" else "Female"
        athletes = roster_data[
            (roster_data["Role"].str.upper() == "ATHLETE") &
            (roster_data["Active_Clean"].isin(ACTIVE_FLAGS)) &
            (roster_data["Gender"].str.title() == target_gender)
        ].sort_values("Last_Name")

        if p_type == "Summer":
            cols_data = [("Mon In",True),("Mon Out",True),
                         ("Tues In",False),("Tues Out",False),
                         ("Thur In",True),("Thur Out",True)]
        else:
            cols_data = [("Mon In",True),("Mon Out",True),
                         ("Tues In",False),("Tues Out",False),
                         ("Wed In",True),("Wed Out",True),
                         ("Thurs In",False),("Thurs Out",False),
                         ("Fri In",True),("Fri Out",True)]

        n_athletes = len(athletes)
        # Scale down slightly for larger rosters to keep on one page.
        # 30 or fewer: full size. 31-40: 90%. 41-50: 80%. 50+: 72% (may spill).
        if n_athletes <= 30:   zoom = 1.0
        elif n_athletes <= 40: zoom = 0.90
        elif n_athletes <= 50: zoom = 0.80
        else:                  zoom = 0.72

        week_line = f"Week of: {p_week} &nbsp;|&nbsp; {p_type}" if p_week else p_type

        # Build table rows
        rows_html = ""
        for _, row in athletes.iterrows():
            rows_html += '<tr>'
            rows_html += f'<td class="name-col">{row["Last_Name"]}, {row["First_Name"]}</td>'
            for _, shaded in cols_data:
                bg = "#eef1f5" if shaded else "#ffffff"
                rows_html += f'<td style="background:{bg};"></td>'
            rows_html += '</tr>'

        # Column headers
        headers_html = '<th class="name-col">Runner</th>'
        for c_text, shaded in cols_data:
            bg = "#d4dae3" if shaded else "#f0f2f5"
            headers_html += f'<th style="background:{bg};">{c_text}</th>'

        final_html = f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{p_gender} Attendance</title>
<style>
    :root {{
        --border: #b0b8c4;
        --crimson: #8B2331;
        --navy: #0C223F;
        --font: 'Inter', system-ui, -apple-system, sans-serif;
    }}
    body {{
        font-family: var(--font);
        margin: 0;
        padding: 12px 14px;
        background: #fff;
        color: #1e293b;
    }}
    @page {{
        size: portrait;
        margin: 0;
    }}
    /* Scale the entire page body at print time to fit the roster */
    @media print {{
        .no-print {{ display: none !important; }}
        body {{
            padding: 0.3in 0.35in;
            zoom: {zoom};
            -webkit-print-color-adjust: exact !important;
            print-color-adjust: exact !important;
        }}
    }}

    /* Header */
    .att-header {{
        border-left: 5px solid var(--crimson);
        padding: 4px 0 4px 10px;
        margin-bottom: 10px;
    }}
    .att-header h1 {{
        margin: 0; font-size: 15px; font-weight: 700;
        color: var(--navy);
    }}
    .att-header p {{
        margin: 1px 0 0 0; font-size: 10px; color: #64748b;
    }}

    /* Table */
    table {{
        width: 100%;
        border-collapse: collapse;
        table-layout: fixed;
    }}
    th, td {{
        border: 1px solid var(--border);
        font-size: 9px;
        text-align: center;
        padding: 0;
        height: 18px;
        overflow: hidden;
        white-space: nowrap;
    }}
    th {{
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.3px;
        font-size: 8px;
        height: 20px;
        color: #334155;
    }}
    th.name-col, td.name-col {{
        text-align: left;
        padding-left: 6px;
        width: 130px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 9.5px;
    }}
    tr:nth-child(even) td.name-col {{
        background: #fafafa;
    }}

    /* Print button */
    .no-print {{
        text-align: center;
        margin-bottom: 16px;
        padding: 12px;
        background: #f0f4f8;
        border-radius: 8px;
        border: 1px solid #cbd5e1;
    }}
    .print-btn {{
        background: var(--crimson); color: #fff; border: none;
        padding: 8px 20px; border-radius: 5px; font-size: 13px;
        font-weight: 600; cursor: pointer; text-transform: uppercase;
        letter-spacing: 0.4px;
    }}
</style>
</head><body>
<div class="no-print">
    <button class="print-btn" onclick="window.print()">Print / Save as PDF</button>
    <p style="font-size:12px;color:#64748b;margin:6px 0 0 0;">
        Uncheck <em>Headers and Footers</em> in the print dialog to remove browser date/URL.
    </p>
</div>
<div class="att-header">
    <h1>{p_gender} Attendance</h1>
    <p>{week_line}</p>
</div>
<table>
    <tr>{headers_html}</tr>
    {rows_html}
</table>
</body></html>"""

        st.success(f"Sheet ready! ({n_athletes} athletes)")
        st.download_button(
            label="⬇️ Download Attendance Sheet (HTML)",
            data=final_html,
            file_name=f"{p_gender}_Attendance_{pd.Timestamp.now(tz='America/New_York').strftime('%Y-%m-%d')}.html",
            mime="text/html"
        )

# ==========================================
# COACH TAB: DATA ENTRY
# ==========================================
def _tab_data_entry():
    """
    Everything the coach touches AFTER a practice or meet.

    Race Results sub-options:
      - Enter / Edit Times  : type finish times for a race
      - Edit Meet Details   : rename meet, change date, rename races,
                              change distance, remove runners from a race
    Workouts sub-options:
      - Log New Workout     : enter splits from today's practice
      - Edit / Delete       : fix an existing session or remove an athlete row
    """
    st.subheader("Data Entry")
    st.markdown("Enter results after the event. To create a new meet or print a workout sheet, use the **Printables** tab.")
    de_type = st.radio("Entry Type:", ["Race Results", "Workouts"], horizontal=True)
    st.markdown("---")

    if de_type == "Race Results":
        race_action = st.radio(
            "Action:",
            ["Enter / Edit Times", "Import from Timer", "Edit Meet Details"],
            horizontal=True,
            key="race_action_radio"
        )
        st.markdown("---")
        if race_action == "Enter / Edit Times":
            _de_race_results()
        elif race_action == "Import from Timer":
            _de_import_from_timer()
        elif race_action == "Edit Meet Details":
            _de_edit_meet()

    elif de_type == "Workouts":
        _de_workouts()


def _de_import_from_timer():
    """
    Accepts the JSON exported from timer.html and writes splits into the
    Races sheet for the CURRENT SEASON only.

    Flow:
      1. Coach pastes JSON → click Preview
      2. A table shows each runner: new time from timer, existing time in Sheet,
         and a status (New / Conflict / No match). Conflicts show both values
         side by side so the coach can decide per-runner.
      3. Coach checks/unchecks individual runners to override conflicts.
      4. Click Confirm Import to write only the selected rows.

    Season safety: the mask always includes Season == CURRENT_SEASON so a
    meet that ran in multiple years never gets times written to the wrong year.
    """
    st.subheader("Import from Race Timer")
    st.info(
        "Paste the JSON copied from the timer tool's Export button. "
        "Click **Preview** to review times before committing anything to the database."
    )

    json_input = st.text_area(
        "Paste timer JSON here",
        height=180,
        placeholder='{"meet": "...", "race": "...", "splits": {...}}',
        key="timer_json_input"
    )

    # ── Step 1: Parse and preview ─────────────────────────────────────────────
    if st.button("Preview Times", type="primary", key="timer_preview_btn"):
        if not json_input.strip():
            st.error("Please paste the JSON from the timer tool.")
            return
        try:
            data = json.loads(json_input.strip())
        except Exception:
            st.error("Invalid JSON — make sure you copied the full export from the timer.")
            return

        meet_name = data.get("meet", "")
        race_name = data.get("race", "")
        splits    = data.get("splits", {})

        if not meet_name or not splits:
            st.error("JSON is missing meet name or splits data.")
            return

        # Season-safe mask: only match rows from the CURRENT SEASON.
        # Also handles older rows where Season may be blank by checking the
        # date falls within the current season's July-cutoff year range.
        race_base = race_name.split("(")[0].strip() if race_name else ""
        season_col = races_data["Season"].astype(str).str.strip()
        mask = (
            (races_data["Meet_Name"] == meet_name) &
            (season_col == CURRENT_SEASON)
        )
        if race_base:
            mask = mask & races_data["Race_Name"].str.startswith(race_base)

        matched_rows = races_data[mask]
        if matched_rows.empty:
            st.warning(
                f"No rows found for meet '{meet_name}' / race '{race_base}' "
                f"in the {CURRENT_SEASON} season. "
                "Make sure the meet was created in Streamlit this season."
            )
            return

        # Build preview rows
        preview = []
        for username, sd in splits.items():
            row_mask   = mask & (races_data["Username"] == username)
            sheet_rows = races_data[row_mask]
            name       = sd.get("name", username)

            new_m1  = sd.get("mile1",  "").strip()
            new_m2  = sd.get("mile2",  "").strip()
            new_fin = sd.get("finish", "").strip()

            if sheet_rows.empty:
                status = "No match in sheet"
                ex_m1 = ex_m2 = ex_fin = ""
            else:
                ex_m1  = str(sheet_rows["Mile_1"].iloc[0]).strip()
                ex_m2  = str(sheet_rows["Mile_2"].iloc[0]).strip()
                ex_fin = str(sheet_rows["Total_Time"].iloc[0]).strip()
                has_conflict = any([
                    new_m1  and ex_m1  and new_m1  != ex_m1,
                    new_m2  and ex_m2  and new_m2  != ex_m2,
                    new_fin and ex_fin and new_fin != ex_fin,
                ])
                has_new = any([
                    new_m1  and not ex_m1,
                    new_m2  and not ex_m2,
                    new_fin and not ex_fin,
                ])
                status = "Conflict" if has_conflict else ("New data" if has_new else "No change")

            preview.append({
                "username": username,
                "Athlete":  name,
                "Timer M1": new_m1  or "—",
                "Sheet M1": ex_m1   or "—",
                "Timer M2": new_m2  or "—",
                "Sheet M2": ex_m2   or "—",
                "Timer Fin": new_fin or "—",
                "Sheet Fin": ex_fin  or "—",
                "Status":   status,
            })

        # Store preview in session state for the confirm step
        st.session_state["timer_preview"]   = preview
        st.session_state["timer_meet_name"] = meet_name
        st.session_state["timer_race_base"] = race_base
        st.session_state["timer_splits"]    = splits
        st.session_state["timer_mask_season"] = CURRENT_SEASON

    # ── Step 2: Show preview and per-runner override checkboxes ──────────────
    if "timer_preview" in st.session_state and st.session_state["timer_preview"]:
        preview   = st.session_state["timer_preview"]
        meet_name = st.session_state["timer_meet_name"]
        race_base = st.session_state["timer_race_base"]
        splits    = st.session_state["timer_splits"]

        st.markdown(f"### Preview — {meet_name} / {race_base} ({CURRENT_SEASON})")

        conflicts  = [r for r in preview if r["Status"] == "Conflict"]
        new_data   = [r for r in preview if r["Status"] == "New data"]
        no_change  = [r for r in preview if r["Status"] == "No change"]
        no_match   = [r for r in preview if r["Status"] == "No match in sheet"]

        st.markdown(
            f"**{len(new_data)}** new &nbsp;|&nbsp; "
            f"**{len(conflicts)}** conflicts &nbsp;|&nbsp; "
            f"**{len(no_change)}** no change &nbsp;|&nbsp; "
            f"**{len(no_match)}** not in sheet"
        )

        # New data rows — always import, no checkbox needed
        if new_data:
            st.markdown("#### New times (will be imported)")
            disp = pd.DataFrame(new_data)[["Athlete","Timer M1","Timer M2","Timer Fin"]]
            disp.columns = ["Athlete","Mile 1","Mile 2","Finish"]
            st.dataframe(disp, hide_index=True, width="stretch")

        # Conflict rows — show side by side with per-runner override checkbox
        override_usernames = set()
        if conflicts:
            st.markdown("#### Conflicts — timer vs sheet (choose which to keep)")
            st.caption("Check the box next to a runner to use the timer time and overwrite the sheet value.")
            for row in conflicts:
                col_name, col_times, col_check = st.columns([2, 4, 1])
                with col_name:
                    st.markdown(f"**{row['Athlete']}**")
                with col_times:
                    parts = []
                    if row["Timer M1"] != "—" or row["Sheet M1"] != "—":
                        parts.append(f"M1: **{row['Timer M1']}** (sheet: {row['Sheet M1']})")
                    if row["Timer M2"] != "—" or row["Sheet M2"] != "—":
                        parts.append(f"M2: **{row['Timer M2']}** (sheet: {row['Sheet M2']})")
                    if row["Timer Fin"] != "—" or row["Sheet Fin"] != "—":
                        parts.append(f"Fin: **{row['Timer Fin']}** (sheet: {row['Sheet Fin']})")
                    st.markdown(" &nbsp;|&nbsp; ".join(parts))
                with col_check:
                    if st.checkbox("Override", key=f"override_{row['username']}", label_visibility="collapsed"):
                        override_usernames.add(row["username"])

        # No-match rows — informational only
        if no_match:
            with st.expander(f"{len(no_match)} runner(s) in timer data not found in sheet"):
                for row in no_match:
                    st.markdown(f"- {row['Athlete']} (`{row['username']}`)")
                st.caption("These runners may not have been added to the race in Streamlit. Add them via Data Entry → Race Results → Add Walk-On first.")

        # ── Step 3: Confirm import ────────────────────────────────────────────
        st.markdown("---")
        if st.button("Confirm Import", type="primary", key="timer_confirm_btn"):
            season_col2 = races_data["Season"].astype(str).str.strip()
            mask = (
                (races_data["Meet_Name"] == meet_name) &
                (season_col2 == CURRENT_SEASON)
            )
            if race_base:
                mask = mask & races_data["Race_Name"].str.startswith(race_base)

            updates = 0
            skipped = 0
            for username, sd in splits.items():
                row_mask = mask & (races_data["Username"] == username)
                if races_data[row_mask].empty:
                    continue
                for col, field in [("Mile_1","mile1"),("Mile_2","mile2"),("Total_Time","finish")]:
                    new_val = sd.get(field, "").strip()
                    if not new_val:
                        continue
                    existing = str(races_data.loc[row_mask, col].iloc[0]).strip()
                    if existing and username not in override_usernames:
                        skipped += 1
                        continue
                    races_data.loc[row_mask, col] = new_val
                    updates += 1

            if updates == 0:
                st.warning("Nothing was imported. Check override boxes for any conflicts you want to overwrite.")
                return

            with st.spinner("Saving to database..."):
                conn.update(worksheet="Races", data=races_data)
            invalidate_races()

            msg = f"Imported {updates} time(s) for the {CURRENT_SEASON} season."
            if skipped: msg += f" {skipped} skipped (existing data kept)."
            st.success(msg)
            # Clear preview state
            for key in ["timer_preview","timer_meet_name","timer_race_base","timer_splits","timer_mask_season"]:
                st.session_state.pop(key, None)
            st.rerun()


def _de_race_results():
    """Enter or edit race times for an existing meet."""
    active_races = races_data[races_data["Active"].isin(ACTIVE_FLAGS)]
    existing_meets = active_races["Meet_Name"].dropna().unique().tolist()

    col_m1, col_m2 = st.columns(2)
    with col_m1: sel_meet = st.selectbox("1. Choose Meet", ["-- Select --"] + existing_meets)
    with col_m2:
        if sel_meet != "-- Select --":
            meet_races = active_races[active_races["Meet_Name"] == sel_meet]["Race_Name"].dropna().unique().tolist()
            sel_race = st.selectbox("2. Choose Race", ["-- Select --"] + meet_races)
        else:
            sel_race = "-- Select --"

    if sel_meet == "-- Select --" or sel_race == "-- Select --":
        return

    st.markdown("---")
    target_rows = active_races[(active_races["Meet_Name"] == sel_meet) &
                               (active_races["Race_Name"] == sel_race)].copy()
    all_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") &
                               (roster_data["Active_Clean"].isin(ACTIVE_FLAGS))]
    unassigned = all_athletes[~all_athletes["Username"].isin(target_rows["Username"])]
    un_opts = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}"
               for _, row in unassigned.sort_values("Last_Name").iterrows()}

    if un_opts:
        with st.expander("Add Walk-On / Missing Runner to this Race"):
            add_runners = st.multiselect("Select runners to add:",
                                         options=list(un_opts.keys()),
                                         format_func=lambda x: un_opts[x])
            if st.button("Add to Race Roster"):
                date_val = target_rows["Date"].iloc[0] if not target_rows.empty else pd.to_datetime("today").strftime("%Y-%m-%d")
                dist_val = target_rows["Distance"].iloc[0] if not target_rows.empty else "5K"
                new_r = [{"Date": date_val, "Meet_Name": sel_meet, "Race_Name": sel_race,
                           "Distance": dist_val, "Username": u, "Mile_1": "", "Mile_2": "",
                           "Total_Time": "", "Weight": 1.0, "Active": "TRUE",
                           "Season": calculate_season(date_val)} for u in add_runners]
                updated = pd.concat([races_data, pd.DataFrame(new_r)], ignore_index=True)
                with st.spinner("Adding runners..."): conn.update(worksheet="Races", data=updated)
                invalidate_roster(); st.rerun()

    st.markdown(f"### {sel_race} — Enter Times")
    grid_data = []
    for _, r in target_rows.iterrows():
        match = roster_data[roster_data["Username"] == r["Username"]]
        a_name = f"{match.iloc[0]['First_Name']} {match.iloc[0]['Last_Name']}" if not match.empty else r["Username"]
        grid_data.append({"Username": r["Username"], "Athlete Name": a_name,
                           "Mile 1": r.get("Mile_1",""), "Mile 2": r.get("Mile_2",""),
                           "Total Time": r.get("Total_Time","")})

    col_config = {
        "Username": None,
        "Athlete Name": st.column_config.TextColumn("Athlete Name", disabled=True),
        "Mile 1":       st.column_config.TextColumn("Mile 1 Split"),
        "Mile 2":       st.column_config.TextColumn("Mile 2 Split"),
        "Total Time":   st.column_config.TextColumn("Total Finish Time"),
    }
    st.caption("Type times as-is (e.g. 18:45). Blank rows are ignored in rankings.")
    edited_df = st.data_editor(pd.DataFrame(grid_data), hide_index=True,
                                column_config=col_config, width='stretch',
                                key="race_results_editor")

    col_save, col_del = st.columns(2)
    with col_save:
        if st.button("💾 Save All Race Results", type="primary", width='stretch'):
            for _, row in edited_df.iterrows():
                mask = ((races_data["Meet_Name"] == sel_meet) &
                        (races_data["Race_Name"] == sel_race) &
                        (races_data["Username"] == row["Username"]))
                races_data.loc[mask, "Mile_1"]     = str(row["Mile 1"]).strip()    if pd.notna(row["Mile 1"])    else ""
                races_data.loc[mask, "Mile_2"]     = str(row["Mile 2"]).strip()    if pd.notna(row["Mile 2"])    else ""
                races_data.loc[mask, "Total_Time"] = str(row["Total Time"]).strip() if pd.notna(row["Total Time"]) else ""
            with st.spinner("Saving..."): conn.update(worksheet="Races", data=races_data)
            st.success("Results saved!"); invalidate_races(); st.rerun()
    with col_del:
        if st.button("🗑️ Delete Entire Race", width='stretch'):
            keep = races_data[~((races_data["Meet_Name"] == sel_meet) &
                                (races_data["Race_Name"] == sel_race))]
            with st.spinner("Deleting..."): conn.update(worksheet="Races", data=keep)
            st.success("Race deleted."); invalidate_races(); st.rerun()


def _de_edit_meet():
    """
    Edit meet-level and race-level details after a meet has been created.

    What can be changed here:
      - Meet name (renames all rows for that meet in the Races sheet)
      - Meet date (updates all rows for that meet)
      - Per race: race title, distance
      - Per race: remove specific runners (their row is deleted from Races)

    What cannot be changed here (intentionally):
      - Individual split/finish times — use Enter / Edit Times for that
      - Meet weights — use Manage tab
    """
    st.subheader("Edit Meet Details")
    active_races = races_data[races_data["Active"].isin(ACTIVE_FLAGS)]
    existing_meets = active_races["Meet_Name"].dropna().unique().tolist()

    if not existing_meets:
        st.info("No active meets found.")
        return

    col1, _ = st.columns([1, 2])
    with col1:
        sel_meet = st.selectbox("Select Meet to Edit", ["-- Select --"] + existing_meets,
                                key="edit_meet_select")
    if sel_meet == "-- Select --":
        return

    meet_rows = races_data[races_data["Meet_Name"] == sel_meet].copy()
    cur_date  = meet_rows["Date"].iloc[0] if not meet_rows.empty else None

    st.markdown("---")
    st.markdown("### Meet Header")

    h1, h2 = st.columns(2)
    with h1:
        new_meet_name = st.text_input("Meet Name", value=sel_meet,
                                       key="edit_meet_name", autocomplete="off")
    with h2:
        try:   date_val = pd.to_datetime(cur_date).date()
        except: date_val = datetime.date.today()
        new_date = st.date_input("Meet Date", value=date_val, key="edit_meet_date")

    if st.button("💾 Save Meet Name & Date", key="save_meet_header"):
        formatted_new_date = pd.to_datetime(new_date).strftime("%Y-%m-%d")
        new_season = calculate_season(formatted_new_date)
        mask = races_data["Meet_Name"] == sel_meet
        races_data.loc[mask, "Meet_Name"] = new_meet_name
        races_data.loc[mask, "Date"]      = formatted_new_date
        races_data.loc[mask, "Season"]    = new_season
        with st.spinner("Saving..."): conn.update(worksheet="Races", data=races_data)
        st.success(f"Meet updated to '{new_meet_name}' on {formatted_new_date}.")
        invalidate_races(); st.rerun()

    st.markdown("---")
    st.markdown("### Races Within This Meet")
    st.markdown("Expand each race to rename it, change the distance, or remove runners.")

    race_names = meet_rows["Race_Name"].dropna().unique().tolist()

    for race_name in race_names:
        race_rows = meet_rows[meet_rows["Race_Name"] == race_name]
        cur_dist  = race_rows["Distance"].iloc[0] if not race_rows.empty else "5K"

        with st.expander(f"{race_name}  ({cur_dist})  — {len(race_rows)} runner(s)"):

            # --- Rename race / change distance ---
            rc1, rc2 = st.columns(2)
            new_race_name = rc1.text_input("Race Title",    value=race_name, key=f"rname_{race_name}", autocomplete="off")
            new_dist      = rc2.text_input("Distance",      value=cur_dist,  key=f"rdist_{race_name}", autocomplete="off")

            if st.button("💾 Save Race Title & Distance", key=f"save_race_{race_name}"):
                mask = ((races_data["Meet_Name"]  == sel_meet) &
                        (races_data["Race_Name"]  == race_name))
                races_data.loc[mask, "Race_Name"] = new_race_name
                races_data.loc[mask, "Distance"]  = new_dist
                with st.spinner("Saving..."): conn.update(worksheet="Races", data=races_data)
                st.success(f"Race updated to '{new_race_name}' ({new_dist}).")
                invalidate_races(); st.rerun()

            st.markdown("**Remove Runners from this Race**")
            st.caption("Removing a runner deletes their entry row entirely. Their times are lost if already entered.")

            runner_opts = {}
            for _, r in race_rows.iterrows():
                match = roster_data[roster_data["Username"] == r["Username"]]
                name  = f"{match.iloc[0]['First_Name']} {match.iloc[0]['Last_Name']}" if not match.empty else r["Username"]
                runner_opts[r["Username"]] = name

            runners_to_remove = st.multiselect(
                "Select runners to remove:",
                options=list(runner_opts.keys()),
                format_func=lambda x: runner_opts[x],
                key=f"remove_runners_{race_name}"
            )
            if runners_to_remove:
                if st.button("🗑️ Remove Selected Runners", key=f"remove_btn_{race_name}"):
                    keep = races_data[~(
                        (races_data["Meet_Name"] == sel_meet) &
                        (races_data["Race_Name"] == race_name) &
                        (races_data["Username"].isin(runners_to_remove))
                    )]
                    with st.spinner("Removing runners..."):
                        conn.update(worksheet="Races", data=keep)
                    st.success(f"Removed {len(runners_to_remove)} runner(s) from {race_name}.")
                    invalidate_races(); st.rerun()

def _de_workouts():
    """Log new workout splits or edit/delete an existing workout session."""
    workout_action = st.radio("Action:", ["Log New Workout", "Edit / Delete Existing"], horizontal=True)

    if workout_action == "Log New Workout":
        if st.session_state["workout_saved"]:
            st.success("Workout saved to the database!")
            if st.button("Log Another Workout"):
                st.session_state["workout_saved"] = False; st.rerun()
            return

        st.subheader("Log Workout Splits")
        st.markdown("Enter the splits from today's practice. **Tip:** use the workout sheet you printed beforehand to transfer times quickly.")

        w_col1, w_col2, w_col3 = st.columns(3)
        with w_col1:
            w_date = st.date_input("Workout Date", key="de_w_date")
            w_type = st.selectbox("Workout Type", ["Tempo","Intervals","Hills","Other"], key="de_w_type")
        with w_col2:
            dist_opts_map = {
                "Tempo":     ["400m","Miles","Split","Other"],
                "Intervals": ["400m","800m","1000m","1200m","1 Mile","Custom/Other"],
                "Hills":     ["400m","800m","Short Sprints","Custom/Other"],
            }
            dist_options  = dist_opts_map.get(w_type, ["Custom/Other"])
            selected_dist = st.selectbox("Distance/Rep Details", dist_options, key="de_w_dist_sel")
            if selected_dist in ["Custom/Other","Other","Split"]:
                w_dist = st.text_input("Specify Details", placeholder="e.g. 2+1, 8x400m", autocomplete="off", key="de_w_dist_txt")
            else:
                w_dist = selected_dist
            w_reps = st.number_input("Max Reps/Segments", min_value=1, max_value=20, value=6, key="de_w_reps")
        with w_col3:
            calc_mode  = st.radio("Time Entry Mode:", ["Individual Splits","Continuous Clock (Elapsed)"], key="de_w_calcmode")
            restart_rep = 0
            if calc_mode == "Continuous Clock (Elapsed)" and selected_dist == "Split":
                restart_rep = st.number_input("Restart clock at Rep #", min_value=0, max_value=20, value=0,
                                               help="e.g. for a 2+1 set this to 3", key="de_w_restart")

        st.markdown("---")
        st.markdown("**Number-Only Entry Format**")
        time_entry_format = st.radio(
            "How to read numbers typed without a colon?",
            ["Mins/Secs (e.g. 104 = 1:04)", "Total Seconds (e.g. 82 = 1:22)"],
            horizontal=True, key="de_w_fmt"
        )
        st.caption("Leave blank to skip. Select 'Not Assigned' to record intentional exclusion.")

        active_athletes = roster_data[
            (roster_data["Role"].str.upper() == "ATHLETE") &
            (roster_data["Active_Clean"].isin(ACTIVE_FLAGS))
        ].copy().sort_values(["Gender","Last_Name"])

        grid_data = [{"Username": row["Username"],
                      "Athlete Name": f"{row['First_Name']} {row['Last_Name']}",
                      "Status": "Present",
                      **{f"Rep {i}": "" for i in range(1, w_reps+1)}}
                     for _, row in active_athletes.iterrows()]

        col_config = {
            "Username": None,
            "Athlete Name": st.column_config.TextColumn("Athlete Name", disabled=True),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=["Present","Not Assigned","Sick","Injured","Unexcused"], required=True),
        }
        for i in range(1, w_reps+1):
            col_config[f"Rep {i}"] = st.column_config.TextColumn(f"Rep {i}")

        edited_df = st.data_editor(pd.DataFrame(grid_data), hide_index=True,
                                    column_config=col_config, width='stretch',
                                    key="new_workout_editor")

        if st.button("💾 Save Workout Data", type="primary"):
            if not w_dist:
                st.error("Please enter Distance/Rep Details before saving.")
                return
            formatted_date = pd.to_datetime(w_date).strftime("%Y-%m-%d")
            w_weather = get_weather_for_date(formatted_date)
            season    = calculate_season(formatted_date)
            new_rows  = []
            for _, row in edited_df.iterrows():
                status    = row["Status"]
                raw_times = [str(row[f"Rep {i}"]).strip() for i in range(1, w_reps+1)
                             if str(row[f"Rep {i}"]).strip()]
                if status != "Present" and not raw_times:
                    new_rows.append({"Date": formatted_date, "Workout_Type": w_type,
                                     "Rep_Distance": w_dist, "Weather": w_weather,
                                     "Username": row["Username"], "Status": status,
                                     "Splits": "", "Season": season})
                    continue
                if raw_times:
                    parsed = [time_to_seconds(parse_fast_time(t, time_entry_format)) for t in raw_times]
                    if calc_mode == "Continuous Clock (Elapsed)":
                        splits = [seconds_to_time(parsed[i])
                                  if i == 0 or (restart_rep > 0 and (i+1) == restart_rep)
                                  else seconds_to_time(parsed[i] - parsed[i-1])
                                  for i in range(len(parsed))]
                    else:
                        splits = [seconds_to_time(s) for s in parsed]
                    new_rows.append({"Date": formatted_date, "Workout_Type": w_type,
                                     "Rep_Distance": w_dist, "Weather": w_weather,
                                     "Username": row["Username"], "Status": status,
                                     "Splits": ", ".join(s for s in splits if s),
                                     "Season": season})
            if new_rows:
                updated = pd.concat([workouts_data, pd.DataFrame(new_rows)], ignore_index=True)
                with st.spinner("Saving..."): conn.update(worksheet="Workouts", data=updated)
                st.session_state["workout_saved"] = True; invalidate_workouts(); st.rerun()

    elif workout_action == "Edit / Delete Existing":
        st.subheader("Edit / Delete Existing Workout")
        if workouts_data.empty or workouts_data["Date"].isna().all():
            st.info("No workout data has been logged yet.")
            return

        unique_w = (workouts_data[["Date","Workout_Type","Rep_Distance"]]
                    .dropna(subset=["Date","Workout_Type"]).drop_duplicates())
        unique_w["Date_Obj"] = pd.to_datetime(unique_w["Date"], errors="coerce")
        unique_w = unique_w.sort_values("Date_Obj", ascending=False)

        w_opts = {}
        for _, row in unique_w.iterrows():
            key = f"{row['Date']}|{row['Workout_Type']}"
            try: nice = row["Date_Obj"].strftime("%b %d, %Y")
            except: nice = str(row["Date"])
            w_opts[key] = f"{nice} — {row['Workout_Type']} [{row.get('Rep_Distance','No Details')}]"

        if not w_opts:
            st.info("No valid workouts found.")
            return

        col1, _ = st.columns([1,1])
        with col1:
            sel_key = st.selectbox("Select Workout:", options=list(w_opts.keys()),
                                    format_func=lambda x: w_opts[x])
        old_date, old_type = sel_key.split("|")
        target_rows = workouts_data[(workouts_data["Date"] == old_date) &
                                     (workouts_data["Workout_Type"] == old_type)].copy()
        if target_rows.empty:
            st.info("No data found for that workout.")
            return

        st.markdown("### Update Workout Header")
        cur_date    = pd.to_datetime(target_rows.iloc[0]["Date"], errors="coerce").date()
        cur_type    = target_rows.iloc[0]["Workout_Type"]
        cur_dist    = target_rows.iloc[0]["Rep_Distance"]
        cur_weather = target_rows.iloc[0]["Weather"]
        type_opts   = ["Tempo","Intervals","Hills","Other"]

        h1, h2 = st.columns(2)
        with h1:
            new_date = st.date_input("Workout Date", value=cur_date, key="edit_w_date")
            new_type = st.selectbox("Workout Type", type_opts,
                                     index=type_opts.index(cur_type) if cur_type in type_opts else 3,
                                     key="edit_w_type")
            st.markdown(f"**Current Weather:** {cur_weather}")
        with h2:
            new_dist = st.text_input("Distance/Rep Details", value=cur_dist, autocomplete="off", key="edit_w_dist")

        st.markdown("### Update Athlete Splits")
        max_reps = max(
            (len([s.strip() for s in str(r.get("Splits","")).split(",") if s.strip()])
             for _, r in target_rows.iterrows()),
            default=1
        )
        grid_data = []
        for _, r in target_rows.iterrows():
            match  = roster_data[roster_data["Username"] == r["Username"]]
            a_name = f"{match.iloc[0]['First_Name']} {match.iloc[0]['Last_Name']}" if not match.empty else r["Username"]
            splits = [s.strip() for s in str(r.get("Splits","")).split(",") if s.strip()]
            grid_data.append({"Username": r["Username"], "Athlete Name": a_name,
                               "Status": r["Status"],
                               **{f"Rep {i}": splits[i-1] if i <= len(splits) else ""
                                  for i in range(1, max_reps+1)}})

        col_config = {
            "Username": None,
            "Athlete Name": st.column_config.TextColumn("Athlete Name", disabled=True),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=["Present","Not Assigned","Sick","Injured","Unexcused"], required=True),
        }
        for i in range(1, max_reps+1):
            col_config[f"Rep {i}"] = st.column_config.TextColumn(f"Rep {i}")
        st.caption("Edit splits directly. Type the corrected time (e.g. 1:04).")
        edited_df = st.data_editor(pd.DataFrame(grid_data), hide_index=True,
                                    column_config=col_config, width='stretch',
                                    key="edit_workout_editor")

        col_save, col_del = st.columns(2)
        with col_save:
            if st.button("💾 Save All Edits", type="primary", width='stretch'):
                keep = workouts_data[~((workouts_data["Date"] == old_date) &
                                       (workouts_data["Workout_Type"] == old_type))]
                fmt_date = pd.to_datetime(new_date).strftime("%Y-%m-%d")
                final_weather = (get_weather_for_date(fmt_date)
                                 if fmt_date != old_date or not cur_weather or "Can't" in cur_weather
                                 else cur_weather)
                new_rows = [{"Date": fmt_date, "Workout_Type": new_type, "Rep_Distance": new_dist,
                              "Weather": final_weather, "Username": row["Username"], "Status": row["Status"],
                              "Splits": ", ".join(str(row[f"Rep {i}"]).strip()
                                                   for i in range(1, max_reps+1)
                                                   if str(row[f"Rep {i}"]).strip()),
                              "Season": calculate_season(fmt_date)}
                             for _, row in edited_df.iterrows()]
                updated = pd.concat([keep, pd.DataFrame(new_rows)], ignore_index=True)
                with st.spinner("Updating..."): conn.update(worksheet="Workouts", data=updated)
                st.success("Workout updated!"); invalidate_workouts(); st.rerun()
        with col_del:
            if st.button("🗑️ Delete This Workout", width='stretch'):
                keep = workouts_data[~((workouts_data["Date"] == old_date) &
                                       (workouts_data["Workout_Type"] == old_type))]
                with st.spinner("Deleting..."): conn.update(worksheet="Workouts", data=keep)
                st.success("Workout deleted!"); invalidate_workouts(); st.rerun()


# ==========================================
# COACH TAB: MANAGE (infrequent admin)
# ==========================================
def _tab_manage():
    """
    Infrequent admin tasks:
      - Meet Weights: adjust ranking multipliers per meet
      - Archive Meet: hide a meet from the active dashboard
      - Pacing & Rest: edit VDOT table and rest cycle table
      - Team Documents: manage embedded Google Doc links
    """
    st.subheader("Manage")
    action = st.radio(
        "Select task:",
        ["Announcements", "Meet Weights", "Archive a Meet", "Pacing & Rest Tables", "Team Documents", "Race Timer Sync"],
        horizontal=True
    )
    st.markdown("---")

    if action == "Announcements":
        _manage_announcements()

    elif action == "Meet Weights":
        st.subheader("Meet Multipliers & Weights")
        st.info(f"Adjusting weights for the **{CURRENT_SEASON}** season. Weight 0 = excluded from rankings.")
        active_races  = races_data[(races_data["Active"].isin(ACTIVE_FLAGS)) &
                                    (races_data["Season"] == CURRENT_SEASON)]
        unique_meets  = active_races[["Meet_Name","Date","Weight"]].drop_duplicates(subset=["Meet_Name","Date"])
        if unique_meets.empty or unique_meets["Meet_Name"].isna().all():
            st.info("No meets logged yet for the current season.")
        else:
            with st.form("weights_form"):
                updated = {}
                for idx, row in unique_meets.iterrows():
                    label = f"{pd.to_datetime(row['Date'], errors='coerce').strftime('%m/%d/%Y')} | {row['Meet_Name']}"
                    updated[(row["Meet_Name"], row["Date"])] = st.number_input(
                        label, value=float(row["Weight"]), step=0.5, min_value=0.0,
                        key=f"wt_{idx}")
                if st.form_submit_button("💾 Save Weights", type="primary"):
                    for (m, d), w in updated.items():
                        races_data.loc[(races_data["Meet_Name"] == m) &
                                       (races_data["Date"] == d), "Weight"] = w
                    with st.spinner("Saving..."): conn.update(worksheet="Races", data=races_data)
                    st.success("Weights saved!"); invalidate_races(); st.rerun()

    elif action == "Archive a Meet":
        st.subheader("Archive a Meet")
        st.markdown("Hides the meet from rankings and athlete views. Data is preserved and can be restored by editing the sheet directly.")
        active_meets = races_data[races_data["Active"].isin(ACTIVE_FLAGS)][["Meet_Name","Date"]].drop_duplicates()
        if active_meets.empty:
            st.info("No active meets to archive.")
        else:
            meet_opts = {f"{row['Meet_Name']}|{row['Date']}":
                         f"{pd.to_datetime(row['Date'], errors='coerce').strftime('%m/%d/%Y')} | {row['Meet_Name']}"
                         for _, row in active_meets.iterrows()}
            with st.form("archive_meet_form"):
                col1, _ = st.columns([1,1])
                with col1:
                    to_archive = st.selectbox("Select Meet", options=list(meet_opts.keys()),
                                               format_func=lambda x: meet_opts[x])
                if st.form_submit_button("Archive Meet"):
                    m_name, m_date = to_archive.split("|")
                    races_data.loc[(races_data["Meet_Name"] == m_name) &
                                   (races_data["Date"] == m_date), "Active"] = "FALSE"
                    with st.spinner("Archiving..."): conn.update(worksheet="Races", data=races_data)
                    st.success(f"'{m_name}' archived."); invalidate_races(); st.rerun()

    elif action == "Pacing & Rest Tables":
        st.subheader("VDOT Paces & Rest Cycles")
        st.info("These tables drive the personalized pace calculator shown to athletes. Edit carefully — changes take effect immediately.")
        t1, t2 = st.tabs(["VDOT Pace Chart", "Rest Cycles"])
        with t1:
            edited_vdot = st.data_editor(vdot_data, num_rows="dynamic", width='stretch')
            if st.button("💾 Save Pace Chart", type="primary"):
                try:
                    with st.spinner("Saving..."): conn.update(worksheet="VDOT", data=edited_vdot)
                    st.success("Pace chart saved!"); invalidate_vdot()
                except Exception:
                    st.error("Missing tab — add a sheet named **VDOT** in your Google Sheet.")
        with t2:
            edited_rest = st.data_editor(rest_data, num_rows="dynamic", width='stretch')
            if st.button("💾 Save Rest Cycles", type="primary"):
                try:
                    with st.spinner("Saving..."): conn.update(worksheet="Rest", data=edited_rest)
                    st.success("Rest cycles saved!"); invalidate_rest()
                except Exception:
                    st.error("Missing tab — add a sheet named **Rest** in your Google Sheet.")

    elif action == "Team Documents":
        st.subheader("Team Documents")
        st.info("Paste 'Publish to Web' links from Google Docs. They appear on every athlete's Team Resources tab. (File → Share → Publish to Web → Copy Link)")
        edited_docs = st.data_editor(docs_data, num_rows="dynamic", width='stretch')
        if st.button("💾 Save Documents", type="primary"):
            try:
                with st.spinner("Saving..."): conn.update(worksheet="Documents", data=edited_docs)
                st.success("Documents updated!"); invalidate_docs(); st.rerun()
            except Exception:
                st.error("Missing tab — add a sheet named **Documents** in your Google Sheet.")
        st.markdown("---")
        display_team_resources()

    elif action == "Race Timer Sync":
        _manage_timer_sync()


# ==========================================
# ANNOUNCEMENTS — SHARED DISPLAY HELPER
# ==========================================

def _render_announcement_card(row, show_controls=False):
    """
    Renders a single announcement as a styled card.

    Fixes vs original:
    - Date_Posted now stores full datetime string (YYYY-MM-DD HH:MM), so both
      date and time are shown on the card.
    - link_label is HTML-escaped before injection to prevent raw HTML from
      leaking into the card if the field contains special characters or was
      accidentally left as the placeholder text.
    - show_controls=False (athlete view) renders no buttons at all.
    """
    import html as html_lib
    T = THEMES[st.session_state["theme"]]
    is_active = str(row.get("Active", "TRUE")).strip().upper() in ACTIVE_FLAGS

    opacity      = "1.0" if is_active else "0.55"
    border_color = T["metric_border"] if is_active else "#888888"

    # Parse stored datetime — show date + time if available
    raw_posted = str(row.get("Date_Posted", ""))
    try:
        dt = pd.to_datetime(raw_posted)
        posted_display = dt.strftime("%b %d, %Y at %I:%M %p").replace(" 0", " ")
    except:
        posted_display = raw_posted

    # Sanitize every field that goes into the HTML to prevent injection
    title     = html_lib.escape(str(row.get("Title",     "")).strip())
    message   = html_lib.escape(str(row.get("Message",   "")).strip())
    posted_by = html_lib.escape(str(row.get("Posted_By", "Coach")).strip())
    link      = str(row.get("Link", "")).strip()            # URL — not escaped (needs to stay valid)
    raw_label = str(row.get("Link_Label", "")).strip()
    if raw_label:
        label = html_lib.escape(raw_label)
    elif link.startswith("http"):
        # Show a shortened URL so athletes know what they are clicking
        from urllib.parse import urlparse
        parsed = urlparse(link)
        label = html_lib.escape(parsed.netloc or link[:40])
    else:
        label = "View Link"

    # Only render a link if the URL actually looks like one
    link_html = ""
    if link.startswith("http"):
        link_html = (
            f'<a href="{link}" target="_blank" rel="noopener noreferrer" '            f'style="display:inline-block;margin-top:10px;font-size:13px;'            f'color:{T["line"]};font-weight:600;text-decoration:none;">'            f'{label} &rarr;</a>'
        )

    archived_badge = (
        "" if is_active
        else "<span style='font-size:11px;color:#888;margin-left:8px;'>(Archived)</span>"
    )

    st.markdown(f"""
    <div style="background-color:{T['metric_bg']};border:1px solid {border_color};
                border-left:4px solid {T['line']};border-radius:8px;
                padding:16px 20px 12px 20px;margin-bottom:14px;opacity:{opacity};">
        <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <span style="font-size:15px;font-weight:700;color:{T['header']};">
                {title}{archived_badge}
            </span>
            <span style="font-size:11px;color:{T['text']};opacity:0.6;
                         white-space:nowrap;margin-left:12px;">
                {posted_display} &bull; {posted_by}
            </span>
        </div>
        <p style="margin:8px 0 0 0;font-size:13px;color:{T['text']};line-height:1.6;">
            {message}
        </p>
        {link_html}
    </div>
    """, unsafe_allow_html=True)

    if show_controls:
        ann_id = str(row.get("ID", ""))
        if is_active:
            if st.button("Archive", key=f"ann_archive_{ann_id}"):
                announcements_data.loc[announcements_data["ID"] == ann_id, "Active"] = "FALSE"
                with st.spinner("Archiving..."):
                    conn.update(worksheet="Announcements", data=announcements_data)
                invalidate_announcements(); st.rerun()
        else:
            col_r, col_d = st.columns([1, 4])
            with col_r:
                if st.button("Restore", key=f"ann_restore_{ann_id}"):
                    announcements_data.loc[announcements_data["ID"] == ann_id, "Active"] = "TRUE"
                    with st.spinner("Restoring..."):
                        conn.update(worksheet="Announcements", data=announcements_data)
                    invalidate_announcements(); st.rerun()
            with col_d:
                if st.button("🗑️ Delete Permanently", key=f"ann_delete_{ann_id}"):
                    keep = announcements_data[announcements_data["ID"] != ann_id]
                    with st.spinner("Deleting..."):
                        conn.update(worksheet="Announcements", data=keep)
                    invalidate_announcements(); st.rerun()
        st.markdown("<div style='margin-bottom:4px;'></div>", unsafe_allow_html=True)


# ==========================================
# ANNOUNCEMENTS — COACH MANAGE SECTION
# ==========================================

def _manage_announcements():
    """
    Coach interface for announcements inside the Manage tab.

    Fixes vs original:
    - Date_Posted now stores full datetime (YYYY-MM-DD HH:MM) so time shows on card.
    - Post confirmation uses session state flag so it survives the st.rerun()
      and displays on the next render cycle instead of flashing and vanishing.
    - Fields clear automatically because st.rerun() re-renders the empty form.
    """
    st.subheader("Announcements")

    # Session state flag: show confirmation banner after a successful post
    if "ann_posted" not in st.session_state:
        st.session_state["ann_posted"] = ""

    ann_action = st.radio(
        "Action:",
        ["Post New Announcement", "Manage Existing"],
        horizontal=True,
        key="ann_action_radio"
    )
    st.markdown("---")

    if ann_action == "Post New Announcement":
        # Show confirmation banner from the previous submit (survives rerun)
        if st.session_state["ann_posted"]:
            st.success(f"Announcement \"{st.session_state['ann_posted']}\" posted successfully.")
            st.session_state["ann_posted"] = ""

        st.markdown("### New Announcement")
        with st.form("new_announcement_form", clear_on_submit=True):
            title   = st.text_input("Title", placeholder="e.g. Practice cancelled Thursday", autocomplete="off")
            message = st.text_area("Message", placeholder="Full details here...", height=120)
            st.markdown("**Optional Link**")
            lc1, lc2 = st.columns(2)
            link       = lc1.text_input("URL", placeholder="https://...", autocomplete="off")
            link_label = lc2.text_input("Link Label", placeholder="e.g. View Meet Info", autocomplete="off")

            if st.form_submit_button("Post Announcement"):
                if not title.strip():
                    st.error("A title is required.")
                elif not message.strip():
                    st.error("A message body is required.")
                else:
                    new_id = str(int(pd.Timestamp.now(tz="America/New_York").timestamp()))
                    new_row = pd.DataFrame([{
                        "ID":          new_id,
                        "Title":       title.strip(),
                        "Message":     message.strip(),
                        "Link":        link.strip(),
                        "Link_Label":  link_label.strip(),
                        "Posted_By":   f"{st.session_state['first_name']} {st.session_state['last_name']}",
                        # Store full datetime so time is available on the card
                        "Date_Posted": pd.Timestamp.now(tz="America/New_York").strftime("%Y-%m-%d %H:%M"),
                        "Active":      "TRUE",
                    }])
                    updated = pd.concat([announcements_data, new_row], ignore_index=True)
                    with st.spinner("Posting..."):
                        conn.update(worksheet="Announcements", data=updated)
                    # Store title in session state so confirmation survives the rerun
                    st.session_state["ann_posted"] = title.strip()
                    invalidate_announcements()
                    st.rerun()

    elif ann_action == "Manage Existing":
        st.markdown("### All Announcements")
        if announcements_data.empty:
            st.info("No announcements have been posted yet.")
            return

        df = announcements_data.copy()
        df["Date_Obj"] = pd.to_datetime(df["Date_Posted"], errors="coerce")
        df = df.sort_values("Date_Obj", ascending=False)

        active_df   = df[df["Active"].astype(str).str.upper().isin(ACTIVE_FLAGS)]
        archived_df = df[~df["Active"].astype(str).str.upper().isin(ACTIVE_FLAGS)]

        st.markdown(f"**Active ({len(active_df)})**")
        if active_df.empty:
            st.info("No active announcements.")
        else:
            for _, row in active_df.iterrows():
                _render_announcement_card(row, show_controls=True)

        if not archived_df.empty:
            with st.expander(f"Archived ({len(archived_df)})"):
                for _, row in archived_df.iterrows():
                    _render_announcement_card(row, show_controls=True)


# ==========================================
# ANNOUNCEMENTS — ATHLETE FEED
# ==========================================

def _athlete_announcements_tab():
    """
    Read-only announcement feed shown to athletes.
    Displays all active announcements newest first.
    No controls — athletes cannot archive or delete.
    """
    st.subheader("Announcements")

    active = announcements_data[
        announcements_data["Active"].astype(str).str.upper().isin(ACTIVE_FLAGS)
    ].copy()

    if active.empty:
        st.info("No announcements from your coaches at this time. Check back soon.")
        return

    active["Date_Obj"] = pd.to_datetime(active["Date_Posted"], errors="coerce")
    active = active.sort_values("Date_Obj", ascending=False)

    for _, row in active.iterrows():
        _render_announcement_card(row, show_controls=False)


def _manage_timer_sync():
    """
    Syncs current-season meets from Google Sheets into Firebase so they
    appear in the race timer dropdown.

    Why this exists:
    - Meets created BEFORE the Firebase push code was added won't be in Firebase.
    - This one-time (or occasional) sync button catches them all up.
    - Only pushes CURRENT_SEASON meets so the timer dropdown stays clean.
    - Safe to run multiple times — Firebase uses PUT which overwrites cleanly.
    - Test meets can be deleted individually using the Delete button below.

    After syncing, only current-season meets appear in the timer because
    timer.html filters by season === CURRENT_SEASON on load.
    """
    st.subheader("Race Timer Sync")
    st.markdown(
        "This panel syncs your current-season meets into Firebase so they appear "
        "in the race timer dropdown. New meets you create automatically sync — "
        "use this only to push **existing** meets that were created before this "
        "feature was added."
    )

    # ── Show what's currently in Firebase ────────────────────────────────────
    db_url  = st.secrets.get("firebase_db_url",  "https://mcxc-timer-default-rtdb.firebaseio.com")
    api_key = st.secrets.get("firebase_api_key", "AIzaSyAKFLshFCubsJtJ5TTb7FFWB2kUl-wph_c")

    st.markdown("### Current Season Meets in Google Sheet")
    current_meets = (
        races_data[
            (races_data["Active"].isin(ACTIVE_FLAGS)) &
            (races_data["Season"] == CURRENT_SEASON)
        ]["Meet_Name"].dropna().unique().tolist()
    )

    if not current_meets:
        st.info(f"No active meets found for the {CURRENT_SEASON} season.")
    else:
        st.markdown(f"Found **{len(current_meets)}** meet(s) for {CURRENT_SEASON}:")
        for m in sorted(current_meets):
            st.markdown(f"- {m}")

        if st.button("Sync All Current Season Meets to Timer", type="primary"):
            pushed, failed = 0, 0
            with st.spinner("Syncing meets to Firebase..."):
                for meet_name in current_meets:
                    meet_rows = races_data[races_data["Meet_Name"] == meet_name]
                    meet_date = meet_rows["Date"].iloc[0] if not meet_rows.empty else ""
                    race_names = meet_rows["Race_Name"].dropna().unique().tolist()

                    firebase_races = []
                    for race_name in race_names:
                        race_rows = meet_rows[meet_rows["Race_Name"] == race_name]
                        dist = race_rows["Distance"].iloc[0] if not race_rows.empty else "5K"
                        runner_list = []
                        seen_unames = set()
                        for _, r in race_rows.iterrows():
                            uname = r["Username"]
                            if not uname or uname in seen_unames:
                                continue
                            seen_unames.add(uname)
                            match = roster_data[roster_data["Username"] == uname]
                            rname = (f"{match.iloc[0]['First_Name']} {match.iloc[0]['Last_Name']}"
                                     if not match.empty else uname)
                            pr_time, _ = _get_athlete_pr(uname, races_data, season=CURRENT_SEASON)
                            runner_list.append({"username": uname, "name": rname, "pr": pr_time or ""})
                        firebase_races.append({"name": race_name, "dist": dist, "runners": runner_list})

                    ok = _push_meet_to_firebase(meet_name, meet_date, firebase_races)
                    if ok: pushed += 1
                    else:  failed += 1

            if failed == 0:
                st.success(f"Synced {pushed} meet(s) to Firebase successfully.")
            else:
                st.warning(f"Synced {pushed} meet(s). {failed} failed — check your Firebase secrets.")

    st.markdown("---")
    st.markdown("### Delete a Meet from Firebase")
    st.markdown(
        "Use this to remove test meets or old entries that shouldn't appear "
        "in the timer dropdown. This only removes from Firebase — "
        "your Google Sheet data is untouched."
    )

    col1, _ = st.columns([1, 2])
    with col1:
        del_meet_key = st.text_input(
            "Firebase meet key to delete",
            placeholder="e.g. Great_American_XC_20260912",
            autocomplete="off",
            key="del_firebase_key"
        )
    st.caption(
        "The key is the meet name with spaces replaced by underscores + the date (no dashes). "
        "You can find it in your Firebase console under the 'meets' node."
    )
    if del_meet_key and st.button("Delete from Firebase", key="del_fb_btn"):
        try:
            url  = f"{db_url}/meets/{del_meet_key}.json"
            resp = requests.delete(url, timeout=5)
            if resp.status_code == 200:
                st.success(f"Deleted '{del_meet_key}' from Firebase.")
            else:
                st.error(f"Delete failed (HTTP {resp.status_code}). Check the key and try again.")
        except Exception as e:
            st.error(f"Could not connect to Firebase: {e}")


# ---- ATHLETE VIEW ----
def _athlete_view():
    """
    Athlete dashboard tabs:
      - Announcements : active coach announcements, newest first
      - My Season     : race results, workouts, paces, career PRs
      - Team Rankings : leaderboard and master grid
      - Team Resources: embedded Google Docs
    Announcements is placed first so athletes see it immediately on login.
    """
    st.header("Training Dashboard")
    tab_announce, tab_dash, tab_rankings, tab_resources = st.tabs([
        "Announcements", "My Season", "Team Rankings", "Team Resources"
    ])

    with tab_announce:
        _athlete_announcements_tab()

    with tab_dash:
        u_races = races_data[races_data["Username"] == st.session_state["username"]]
        u_works = workouts_data[workouts_data["Username"] == st.session_state["username"]]
        athlete_seasons = sorted(set(u_races["Season"].tolist() + u_works["Season"].tolist()), reverse=True) or [CURRENT_SEASON]
        col_s1, _ = st.columns([1, 3])
        with col_s1:
            sel_season = st.selectbox("View Season:", athlete_seasons, key="athlete_dash_season")
        st.markdown("---")
        user_races    = u_races[(u_races["Active"].isin(ACTIVE_FLAGS)) & (u_races["Season"] == sel_season)].copy()
        user_workouts = u_works[u_works["Season"] == sel_season].copy()
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(label=f"Races Completed ({sel_season})",
                      value=len(user_races[user_races["Total_Time"].str.strip() != ""]))
        col_m2.metric(label=f"Workouts Logged ({sel_season})",
                      value=len(user_workouts[user_workouts["Status"] == "Present"]))
        fastest_5k = "N/A"
        if not user_races.empty:
            five_k = user_races[user_races["Distance"].str.upper() == "5K"]
            if not five_k.empty:
                fastest_sec = five_k["Total_Time"].apply(time_to_seconds).replace(0, float("inf")).min()
                if fastest_sec != float("inf"): fastest_5k = seconds_to_time(fastest_sec)
        col_m3.metric(label=f"5K PR ({sel_season})", value=fastest_5k)
        st.markdown("<br>", unsafe_allow_html=True)
        sub_races, sub_workouts, sub_paces, sub_career = st.tabs([
            "Race Results", "Workouts", "Training Paces", "Career PRs"
        ])
        with sub_races:    display_athlete_races(st.session_state["username"], sel_season)
        with sub_workouts: display_athlete_workouts(st.session_state["username"], sel_season)
        with sub_paces:    display_suggested_paces(st.session_state["username"])
        with sub_career:   display_career_history(st.session_state["username"])

    with tab_rankings:
        show_rankings_tab()
    with tab_resources:
        display_team_resources()

# ==========================================
# 8. APP ENTRY POINT
# ==========================================
if not st.session_state["logged_in"]:
    login_page()
elif st.session_state["first_login"]:
    password_reset_page()
else:
    home_page()
