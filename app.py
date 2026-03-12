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

def wrap_html_for_print(title, body_content, is_attendance=False):
    page_settings = "size: portrait;" if is_attendance else "size: auto;"
    return f"""<!DOCTYPE html>
<html><head><meta charset="UTF-8"><title>{title}</title>
<style>
    :root {{ --border-color: #cbd5e1; --text-main: #1e293b; --text-muted: #64748b; --font-family: 'Inter', system-ui, -apple-system, sans-serif; --mcxc-crimson: #8B2331; }}
    body {{ font-family: var(--font-family); padding: 20px; margin: 0; color: var(--text-main); background-color: #ffffff; }}
    @page {{ margin: 0; {page_settings} }}
    h2 {{ margin: 0 0 10px 0; font-size: 22px; font-weight: 700; text-align: center; color: var(--text-main); letter-spacing: -0.5px; page-break-after: avoid; break-after: avoid; }}
    h3 {{ margin: 15px 0 0 0; font-size: 14px; font-weight: 600; background-color: #f8fafc; padding: 10px 15px; border: 1px solid var(--border-color); border-radius: 8px 8px 0 0; border-bottom: none; color: var(--text-main); page-break-after: avoid; break-after: avoid; }}
    table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; page-break-inside: avoid; break-inside: avoid; border: 1px solid var(--border-color); }}
    tr {{ page-break-inside: avoid; page-break-after: auto; }}
    th, td {{ padding: 10px 4px; border: 1px solid var(--border-color); text-align: center; font-size: 12px; }}
    th:first-child, td:first-child {{ text-align: left; padding-left: 12px; }}
    th {{ color: var(--text-muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; font-size: 11px; background: #f8fafc; }}
    .print-btn {{ background: var(--mcxc-crimson); color: #ffffff; border: none; padding: 12px 24px; border-radius: 6px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; text-transform: uppercase; letter-spacing: 0.5px; box-shadow: 0 4px 6px -1px rgba(139, 35, 49, 0.3); margin-bottom: 10px; }}
    .print-btn:hover {{ filter: brightness(1.1); transform: translateY(-1px); }}
    .keep-together {{ page-break-inside: avoid; break-inside: avoid; margin-bottom: 25px; }}
    .no-print-container {{ text-align: center; margin-bottom: 30px; padding: 20px; background: #f0f4f8; border-radius: 12px; border: 1px solid var(--border-color); }}
    @media print {{ .no-print {{ display: none !important; }} body {{ padding: 0.5in; }} * {{ -webkit-print-color-adjust: exact !important; print-color-adjust: exact !important; }} }}
</style>
</head><body>
    <div class="no-print no-print-container">
        <button class="print-btn" onclick="window.print()">🖨️ Click Here to Print / Save as PDF</button>
        <p style="color: var(--text-muted); font-size: 13px; margin: 10px 0 0 0;"><strong>Pro Tip:</strong> For large rosters, set your printer "Scale" to <i>Fit to Page</i>.</p>
        <p style="color: var(--text-muted); font-size: 13px; margin: 5px 0 0 0;"><i>If you still see dates/URLs on the print preview, uncheck "Headers and Footers" in your print dialog box!</i></p>
    </div>
    {body_content}
</body></html>"""

# ==========================================
# 3. DATABASE CONNECTION & CLEANUP
# ==========================================
conn = st.connection("gsheets", type=GSheetsConnection)

roster_data = conn.read(worksheet="Roster", ttl=600).dropna(how="all")
races_data = conn.read(worksheet="Races", ttl=600).dropna(how="all")
workouts_data = conn.read(worksheet="Workouts", ttl=600).dropna(how="all")

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

def _read_sheet(worksheet, default_df, required_col):
    try:
        df = conn.read(worksheet=worksheet, ttl=600).dropna(how="all")
        return df if required_col in df.columns else default_df
    except: return default_df

vdot_data = _read_sheet("VDOT", DEFAULT_VDOT, "5K_Time")
rest_data = _read_sheet("Rest", DEFAULT_REST, "Workout")
docs_data = _read_sheet("Documents", DEFAULT_DOCS, "Title")

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
    st.cache_data.clear()

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
        st.dataframe(vdot_df[["VDOT"] + pace_cols].rename(columns=col_rename), hide_index=True, use_container_width=True)
        st.markdown("### Master Rest Cycles")
        st.dataframe(rest_data, hide_index=True, use_container_width=True)
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
    st.dataframe(bracket_df[["VDOT"] + pace_cols].rename(columns=col_rename).style.apply(highlight_match, axis=1), hide_index=True, use_container_width=True)
    st.markdown("### Master Rest Cycles")
    st.dataframe(rest_data, hide_index=True, use_container_width=True)

def display_team_resources():
    st.subheader("Team Resources")
    if docs_data.empty:
        st.info("No documents have been uploaded by the coaches yet.")
        return
    has_valid = False
    for _, row in docs_data.iterrows():
        url = str(row.get("URL", "")).strip()
        if pd.notna(row.get("URL")) and url.startswith("http"):
            has_valid = True
            if "edit" in url and "pub" not in url: url = url.replace("edit", "preview")
            st.markdown(f"#### {row['Title']}")
            st.markdown(f'<iframe src="{url}" width="100%" height="850px" style="border: 1px solid #ccc; border-radius: 8px;"></iframe>', unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
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
            st.plotly_chart(fig, use_container_width=True, theme=None)
        st.dataframe(prs[["Season", "Total_Time", "Meet_Name", "Date"]].rename(columns={"Total_Time": "PR Time", "Meet_Name": "Meet", "Date": "Date Achieved"}), hide_index=True, use_container_width=True)
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
                    (merged["Gender"].str.title() == target_gender) & (merged["Distance"].str.upper() == r_dist.upper()) & (merged["Season"] == r_season)]

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
                st.dataframe(rank_df[["Rank", "Athlete", "Mark"]].rename(columns={"Mark": label}), hide_index=True, use_container_width=True)

    with tab_grid:
        st.markdown(f"### Master {r_dist} Grid")
        grid_df = merged.copy()
        grid_df["Athlete"] = grid_df["First_Name"] + " " + grid_df["Last_Name"]
        grid_df["Date_Obj"] = pd.to_datetime(grid_df["Date"], errors="coerce")
        grid_df = grid_df.sort_values("Date_Obj")
        grid_df["Race_Col"] = grid_df["Meet_Name"] + " (" + grid_df["Date_Obj"].dt.strftime("%m/%d").fillna("") + ") [" + grid_df["Weight"].apply(lambda x: f"{float(x):.1f}") + "x]"
        ordered_cols = grid_df["Race_Col"].unique().tolist()
        pivot_df = grid_df.pivot_table(index="Athlete", columns="Race_Col", values="Total_Time", aggfunc="first").reindex(columns=ordered_cols).fillna("-").reset_index()
        st.dataframe(pivot_df, hide_index=True, use_container_width=True)

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
    st.plotly_chart(fig, use_container_width=True, theme=None)
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
        st.dataframe(dist_df[cols], hide_index=True, use_container_width=True)
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
            columns={"Date_Formatted": "Date", "Workout_Type": "Type", "Rep_Distance": "Details"}), hide_index=True, use_container_width=True)

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
                st.plotly_chart(fig, use_container_width=True, theme=None)
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
                st.plotly_chart(fig2, use_container_width=True, theme=None)
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
            if st.form_submit_button("Log In", use_container_width=True):
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
            if st.form_submit_button("Update Password", use_container_width=True):
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
def home_page():
    user_role = str(st.session_state["role"]).capitalize()

    with st.sidebar:
        st.subheader("⚙️ Settings")
        selected_theme = st.selectbox("App Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state["theme"]))
        if selected_theme != st.session_state["theme"]:
            st.session_state["theme"] = selected_theme
            st.rerun()
        st.markdown("---")
        st.button("Log Out", on_click=logout, use_container_width=True)

    st.title(f"{user_role}: {st.session_state['first_name']} {st.session_state['last_name']}")
    st.markdown("---")

    if user_role.upper() == "COACH":
        _coach_view()
    else:
        _athlete_view()

# ---- COACH VIEW ----
def _coach_view():
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Athlete Lookup", "Roster Management", "Data Entry", "Team Rankings", "Meet Setup & Printables", "Team Resources"])

    with tab1:
        _tab_athlete_lookup()
    with tab2:
        _tab_roster_management()
    with tab3:
        _tab_data_entry()
    with tab4:
        show_rankings_tab()
    with tab5:
        _tab_meet_setup()
    with tab6:
        st.subheader("Manage Team Documents")
        st.info("Paste the 'Publish to Web' link of your Google Docs below. They will be beautifully embedded on every athlete's dashboard. (To get this link: Open your Google Doc → File → Share → Publish to Web → Copy Link)")
        edited_docs = st.data_editor(docs_data, num_rows="dynamic", use_container_width=True)
        if st.button("💾 Save Documents", type="primary"):
            try:
                with st.spinner("Saving documents..."): conn.update(worksheet="Documents", data=edited_docs)
                st.success("Documents updated successfully!")
                st.cache_data.clear()
                st.rerun()
            except Exception:
                st.error("Missing Tab: Open your Google Sheet, click the '+' at the bottom to add a new tab, name it exactly **Documents**, and try saving again.")
        st.markdown("---")
        display_team_resources()

def _tab_athlete_lookup():
    st.subheader("Athlete Lookup")
    col1, col2, col3 = st.columns(3)
    filter_status = col1.selectbox("Filter by Status:", ["Active", "Archived", "All"])
    filter_gender = col2.selectbox("Filter by Gender:", ["All", "Male", "Female"])
    filter_grade = col3.selectbox("Filter by Grade:", ["All", "9th", "10th", "11th", "12th", "Middle School"])

    base = roster_data[roster_data["Role"].str.upper() == "ATHLETE"].copy()
    if filter_status == "Active": base = base[base["Active_Clean"].isin(ACTIVE_FLAGS)]
    elif filter_status == "Archived": base = base[~base["Active_Clean"].isin(ACTIVE_FLAGS)]
    base["Grade"] = base.get("Grad_Year", "Unknown").apply(get_grade_level)
    if filter_gender != "All": base = base[base["Gender"].str.title() == filter_gender]
    if filter_grade != "All": base = base[base["Grade"] == filter_grade]
    base = base.sort_values(["Last_Name", "First_Name"])
    athlete_dict = {row["Username"]: f"{row['Last_Name']}, {row['First_Name']} - {row['Grade']}" for _, row in base.iterrows()}

    if not athlete_dict:
        st.info("No athletes match this filter.")
        return

    col_sel1, _ = st.columns([1, 2])
    with col_sel1:
        selected_username = st.selectbox("Select an Athlete:", options=list(athlete_dict.keys()), format_func=lambda x: athlete_dict[x])

    if selected_username:
        st.markdown("---")
        target = base[base["Username"] == selected_username].iloc[0]
        st.markdown(f"### {target['First_Name']} {target['Last_Name']} ({target['Grade']})")
        u_races = races_data[races_data["Username"] == selected_username]
        u_works = workouts_data[workouts_data["Username"] == selected_username]
        athlete_seasons = sorted(set(u_races["Season"].tolist() + u_works["Season"].tolist()), reverse=True) or [CURRENT_SEASON]
        col_s1, _ = st.columns([1, 3])
        with col_s1: sel_season = st.selectbox("View Season:", athlete_seasons, key="coach_athlete_season")
        sub1, sub2, sub3, sub4 = st.tabs(["Race Results", "Workouts", "Training Paces", "Career PRs"])
        with sub1: display_athlete_races(selected_username, sel_season)
        with sub2: display_athlete_workouts(selected_username, sel_season)
        with sub3: display_suggested_paces(selected_username)
        with sub4: display_career_history(selected_username)

def _tab_roster_management():
    st.subheader("Roster Management")
    roster_action = st.radio("Choose an action:", ["View Current Roster", "Add New Member", "Edit Member", "Archive / Restore"], horizontal=True)
    st.markdown("---")

    if roster_action == "View Current Roster":
        active_roster = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)].copy()
        if "Grad_Year" in active_roster.columns:
            active_roster["Grade"] = active_roster["Grad_Year"].apply(get_grade_level)
            display_roster = active_roster[["First_Name", "Last_Name", "Gender", "Grade", "Grad_Year", "Role"]].copy()
            display_roster["Sort_Year"] = pd.to_numeric(display_roster["Grad_Year"], errors="coerce").fillna(9999)
            display_roster = display_roster.sort_values(["Role", "Sort_Year", "Gender", "Last_Name"]).drop(columns=["Sort_Year"])
            st.dataframe(display_roster, hide_index=True, use_container_width=True)
        else:
            st.dataframe(active_roster[["First_Name", "Last_Name", "Role"]].sort_values("Last_Name"), hide_index=True)

    elif roster_action == "Add New Member":
        with st.form("add_member_form"):
            r1, r2 = st.columns(2)
            new_first = r1.text_input("First Name", autocomplete="off")
            new_last = r2.text_input("Last Name", autocomplete="off")
            r3, r4 = st.columns(2)
            new_role = r3.selectbox("Role", ["Athlete", "Coach"])
            new_grad_year = r4.text_input("Grad Year (e.g., 2028)", autocomplete="off")
            r5, _ = st.columns(2)
            new_gender = r5.selectbox("Gender", ["Male", "Female", "N/A"])
            if st.form_submit_button("Add to Roster"):
                if not new_first or not new_last:
                    st.error("First and Last name are required.")
                else:
                    if new_role == "Coach":
                        final_grad_year, final_gender = "Coach", "N/A"
                    else:
                        final_grad_year, final_gender = new_grad_year.strip(), new_gender
                        if not final_grad_year.isdigit() or len(final_grad_year) != 4:
                            st.error("Data Error: Graduation Year must be a 4-digit number.")
                            st.stop()
                    base_un = f"{new_first.lower()}.{new_last.lower()}".replace(" ", "")
                    gen_un, suffix = base_un, 1
                    while gen_un in roster_data["Username"].tolist():
                        gen_un = f"{base_un}{suffix}"; suffix += 1
                    new_row = pd.DataFrame([{"Username": gen_un, "Password": "changeme", "First_Name": new_first, "Last_Name": new_last,
                                             "Role": new_role, "First_Login": "TRUE", "Active": "TRUE", "Grad_Year": final_grad_year, "Gender": final_gender}])
                    push = roster_data.drop(columns=["Active_Clean"]) if "Active_Clean" in roster_data.columns else roster_data
                    updated = pd.concat([push, new_row], ignore_index=True)
                    with st.spinner("Adding new member..."): conn.update(worksheet="Roster", data=updated)
                    st.success(f"Added {new_first} {new_last}! Username: '{gen_un}'.")
                    st.cache_data.clear(); st.rerun()

    elif roster_action == "Edit Member":
        st.info("Note: You cannot edit Usernames.")
        active = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)]
        edit_dict = {row["Username"]: f"{row['First_Name']} {row['Last_Name']} ({row.get('Role', '')})" for _, row in active.iterrows()}
        if not edit_dict:
            st.info("No active members to edit.")
        else:
            col_e1, _ = st.columns([1, 1])
            with col_e1: user_to_edit = st.selectbox("Select Member to Edit:", options=list(edit_dict.keys()), format_func=lambda x: edit_dict[x])
            if user_to_edit:
                target_row = roster_data[roster_data["Username"] == user_to_edit].iloc[0]
                with st.form("edit_member_form"):
                    e1, e2 = st.columns(2)
                    edit_first = e1.text_input("First Name", value=target_row["First_Name"], autocomplete="off")
                    edit_last = e2.text_input("Last Name", value=target_row["Last_Name"], autocomplete="off")
                    e3, e4 = st.columns(2)
                    role_index = 0 if str(target_row["Role"]).title() == "Athlete" else 1
                    edit_role = e3.selectbox("Role", ["Athlete", "Coach"], index=role_index)
                    edit_grad_year = e4.text_input("Grad Year", value=str(target_row.get("Grad_Year", "")), autocomplete="off")
                    e5, _ = st.columns(2)
                    gender_val = str(target_row.get("Gender", "N/A")).title()
                    gender_opts = ["Male", "Female", "N/A"]
                    g_index = gender_opts.index(gender_val) if gender_val in gender_opts else 2
                    edit_gender = e5.selectbox("Gender", gender_opts, index=g_index)
                    if st.form_submit_button("Save Changes"):
                        if edit_role != "Coach" and (not edit_grad_year.strip().isdigit() or len(edit_grad_year.strip()) != 4):
                            st.error("Data Error: Graduation Year must be a 4-digit number.")
                            st.stop()
                        idx = roster_data.index[roster_data["Username"] == user_to_edit].tolist()[0]
                        roster_data.at[idx, "First_Name"] = edit_first
                        roster_data.at[idx, "Last_Name"] = edit_last
                        roster_data.at[idx, "Role"] = edit_role
                        roster_data.at[idx, "Grad_Year"] = "Coach" if edit_role == "Coach" else edit_grad_year.strip()
                        roster_data.at[idx, "Gender"] = "N/A" if edit_role == "Coach" else edit_gender
                        with st.spinner("Saving changes..."): save_to_sheet("Roster", roster_data)
                        st.success("Member updated successfully!"); st.rerun()

    elif roster_action == "Archive / Restore":
        arc_tab1, arc_tab2, arc_tab3 = st.tabs(["Archive Individual", "Restore Member", "Graduate Seniors"])
        with arc_tab1:
            active = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)]
            arc_dict = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}" for _, row in active.iterrows()}
            if not arc_dict:
                st.info("No active members to archive.")
            else:
                c_a1, _ = st.columns([1, 2])
                with c_a1: user_to_archive = st.selectbox("Select Member to Archive:", options=list(arc_dict.keys()), format_func=lambda x: arc_dict[x])
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
                c_r1, _ = st.columns([1, 2])
                with c_r1: user_to_restore = st.selectbox("Select Member to Restore:", options=list(restore_dict.keys()), format_func=lambda x: restore_dict[x])
                if st.button("Restore Member"):
                    idx = roster_data.index[roster_data["Username"] == user_to_restore].tolist()[0]
                    roster_data.at[idx, "Active"] = "TRUE"
                    save_to_sheet("Roster", roster_data); st.rerun()

        with arc_tab3:
            st.warning("This will archive all active runners whose Grade Level is calculated as '12th'.")
            active_df = roster_data[roster_data["Active_Clean"].isin(ACTIVE_FLAGS)].copy()
            active_df["Grade"] = active_df.get("Grad_Year", "Unknown").apply(get_grade_level)
            seniors = active_df[active_df["Grade"] == "12th"]
            if seniors.empty:
                st.info("No active seniors found.")
            else:
                for _, s in seniors.iterrows(): st.markdown(f"- {s['First_Name']} {s['Last_Name']}")
                if st.button("Confirm: Archive All Seniors"):
                    for _, s in seniors.iterrows():
                        idx = roster_data.index[roster_data["Username"] == s["Username"]].tolist()[0]
                        roster_data.at[idx, "Active"] = "FALSE"
                    with st.spinner("Archiving seniors..."): save_to_sheet("Roster", roster_data)
                    st.rerun()

def _tab_data_entry():
    de_type = st.radio("Select Entry Mode", ["Race Results", "Workouts", "Manage Meet Weights", "Manage Pacing & Rest", "Archive Specific Meet"], horizontal=True)
    st.markdown("---")

    if de_type == "Manage Pacing & Rest":
        st.subheader("Manage VDOT Paces & Rest Cycles")
        st.info("These tables control the recommended paces and rest metrics automatically displayed to your athletes. You can change these targets mid-season if needed.")
        edit_tab1, edit_tab2 = st.tabs(["VDOT Pace Chart", "Rest Cycles"])
        with edit_tab1:
            st.markdown("**Editable Pace Chart**")
            edited_vdot = st.data_editor(vdot_data, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Save Pace Chart", type="primary"):
                try:
                    with st.spinner("Updating database..."): conn.update(worksheet="VDOT", data=edited_vdot)
                    st.success("Pace Chart updated!"); st.cache_data.clear()
                except Exception:
                    st.error("Missing Tab: Open your Google Sheet, click the '+' to add a new tab, name it exactly **VDOT**, and try again.")
        with edit_tab2:
            st.markdown("**Editable Rest Cycles**")
            edited_rest = st.data_editor(rest_data, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Save Rest Cycles", type="primary"):
                try:
                    with st.spinner("Updating database..."): conn.update(worksheet="Rest", data=edited_rest)
                    st.success("Rest Cycles updated!"); st.cache_data.clear()
                except Exception:
                    st.error("Missing Tab: Open your Google Sheet, click the '+' to add a new tab, name it exactly **Rest**, and try again.")

    elif de_type == "Archive Specific Meet":
        st.subheader("Archive a Single Meet")
        st.markdown("Hiding a meet from the active dashboard. Data remains in the database.")
        active_meets = races_data[races_data["Active"].isin(ACTIVE_FLAGS)][["Meet_Name", "Date"]].drop_duplicates()
        if active_meets.empty:
            st.info("No active meets available to archive.")
        else:
            meet_options = {f"{row['Meet_Name']}|{row['Date']}": f"{pd.to_datetime(row['Date'], errors='coerce').strftime('%m/%d/%Y')} | {row['Meet_Name']}" for _, row in active_meets.iterrows()}
            with st.form("archive_meet_form"):
                col1, _ = st.columns([1, 1])
                with col1: meet_to_archive = st.selectbox("Select Meet", options=list(meet_options.keys()), format_func=lambda x: meet_options[x])
                if st.form_submit_button("Archive Meet"):
                    m_name, m_date = meet_to_archive.split("|")
                    races_data.loc[(races_data["Meet_Name"] == m_name) & (races_data["Date"] == m_date), "Active"] = "FALSE"
                    with st.spinner("Archiving..."):
                        conn.update(worksheet="Races", data=races_data)
                    st.success(f"Archived {m_name}!"); st.cache_data.clear(); st.rerun()

    elif de_type == "Manage Meet Weights":
        st.subheader("Manage Meet Multipliers & Weights")
        st.info(f"Currently managing weights for the **{CURRENT_SEASON}** season.")
        active_races = races_data[(races_data["Active"].isin(ACTIVE_FLAGS)) & (races_data["Season"] == CURRENT_SEASON)]
        unique_meets = active_races[["Meet_Name", "Date", "Weight"]].drop_duplicates(subset=["Meet_Name", "Date"])
        if unique_meets.empty or unique_meets["Meet_Name"].isna().all():
            st.info("No meets logged yet for the current season.")
        else:
            with st.form("weights_form"):
                updated_weights = {}
                for index, row in unique_meets.iterrows():
                    label = f"{pd.to_datetime(row['Date'], errors='coerce').strftime('%m/%d/%Y')} | {row['Meet_Name']}"
                    updated_weights[(row["Meet_Name"], row["Date"])] = st.number_input(label, value=float(row["Weight"]), step=0.5, min_value=0.0, key=f"weight_input_{index}")
                if st.form_submit_button("Save Weights", type="primary"):
                    for (m, d), w in updated_weights.items():
                        races_data.loc[(races_data["Meet_Name"] == m) & (races_data["Date"] == d), "Weight"] = w
                    with st.spinner("Updating database..."): conn.update(worksheet="Races", data=races_data)
                    st.success("Meet Weights updated successfully!"); st.cache_data.clear(); st.rerun()

    elif de_type == "Race Results":
        st.subheader("Race Data Entry")
        st.markdown("Select an existing meet to enter times in bulk.")
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

        if sel_meet != "-- Select --" and sel_race != "-- Select --":
            st.markdown("---")
            target_rows = active_races[(active_races["Meet_Name"] == sel_meet) & (active_races["Race_Name"] == sel_race)].copy()
            all_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") & (roster_data["Active_Clean"].isin(ACTIVE_FLAGS))]
            unassigned = all_athletes[~all_athletes["Username"].isin(target_rows["Username"])]
            un_opts = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}" for _, row in unassigned.sort_values("Last_Name").iterrows()}
            if un_opts:
                with st.expander("Add Walk-On / Missing Runners to this Race"):
                    add_runners = st.multiselect("Select Runners:", options=list(un_opts.keys()), format_func=lambda x: un_opts[x])
                    if st.button("Add to Race Roster"):
                        date_val = target_rows["Date"].iloc[0] if not target_rows.empty else pd.to_datetime("today").strftime("%Y-%m-%d")
                        dist_val = target_rows["Distance"].iloc[0] if not target_rows.empty else "5K"
                        new_r = [{"Date": date_val, "Meet_Name": sel_meet, "Race_Name": sel_race, "Distance": dist_val, "Username": u, "Mile_1": "", "Mile_2": "", "Total_Time": "", "Weight": 1.0, "Active": "TRUE", "Season": calculate_season(date_val)} for u in add_runners]
                        updated = pd.concat([races_data, pd.DataFrame(new_r)], ignore_index=True)
                        with st.spinner("Adding runners..."): conn.update(worksheet="Races", data=updated)
                        st.cache_data.clear(); st.rerun()

            st.markdown(f"### {sel_race} Results")
            grid_data = []
            for _, r in target_rows.iterrows():
                match = roster_data[roster_data["Username"] == r["Username"]]
                a_name = f"{match.iloc[0]['First_Name']} {match.iloc[0]['Last_Name']}" if not match.empty else r["Username"]
                grid_data.append({"Username": r["Username"], "Athlete Name": a_name, "Mile 1": r.get("Mile_1", ""), "Mile 2": r.get("Mile_2", ""), "Total Time": r.get("Total_Time", "")})

            col_config = {"Username": None, "Athlete Name": st.column_config.TextColumn("Athlete Name", disabled=True),
                          "Mile 1": st.column_config.TextColumn("Mile 1 Split"), "Mile 2": st.column_config.TextColumn("Mile 2 Split"),
                          "Total Time": st.column_config.TextColumn("Total Finish Time")}
            st.caption("Type times exactly as you want them to appear (e.g., 18:45). Runners left blank will be ignored in rankings.")
            edited_df = st.data_editor(pd.DataFrame(grid_data), hide_index=True, column_config=col_config, use_container_width=True, key="race_results_editor")

            col_save, col_del = st.columns(2)
            with col_save:
                if st.button("💾 Save All Race Results", type="primary", use_container_width=True):
                    for _, row in edited_df.iterrows():
                        mask = (races_data["Meet_Name"] == sel_meet) & (races_data["Race_Name"] == sel_race) & (races_data["Username"] == row["Username"])
                        races_data.loc[mask, "Mile_1"] = str(row["Mile 1"]).strip() if pd.notna(row["Mile 1"]) else ""
                        races_data.loc[mask, "Mile_2"] = str(row["Mile 2"]).strip() if pd.notna(row["Mile 2"]) else ""
                        races_data.loc[mask, "Total_Time"] = str(row["Total Time"]).strip() if pd.notna(row["Total Time"]) else ""
                    with st.spinner("Saving results..."): conn.update(worksheet="Races", data=races_data)
                    st.success("Results updated!"); st.cache_data.clear(); st.rerun()
            with col_del:
                if st.button("🗑️ Delete Entire Race", use_container_width=True):
                    keep = races_data[~((races_data["Meet_Name"] == sel_meet) & (races_data["Race_Name"] == sel_race))]
                    with st.spinner("Deleting..."): conn.update(worksheet="Races", data=keep)
                    st.success("Race deleted."); st.cache_data.clear(); st.rerun()

    elif de_type == "Workouts":
        workout_action = st.radio("Action:", ["Log New Workout", "Edit/Delete Existing Workout"], horizontal=True)
        if workout_action == "Log New Workout":
            if st.session_state["workout_saved"]:
                st.success("Workout saved successfully to the database!")
                if st.button("Log Another Workout"):
                    st.session_state["workout_saved"] = False; st.rerun()
            else:
                st.subheader("Workout Data Entry")
                w_col1, w_col2, w_col3 = st.columns(3)
                with w_col1:
                    w_date = st.date_input("Workout Date")
                    w_type = st.selectbox("Workout Type", ["Tempo", "Intervals", "Hills", "Other"])
                with w_col2:
                    dist_opts_map = {"Tempo": ["400m", "Miles", "Split", "Other"], "Intervals": ["400m", "800m", "1000m", "1200m", "1 Mile", "Custom/Other"], "Hills": ["400m", "800m", "Short Sprints", "Custom/Other"]}
                    dist_options = dist_opts_map.get(w_type, ["Custom/Other"])
                    selected_dist = st.selectbox("Distance/Rep Details", dist_options)
                    if selected_dist in ["Custom/Other", "Other", "Split"]: w_dist = st.text_input("Specify Distance/Details", placeholder="e.g., 2+1, 8x400m", autocomplete="off")
                    else: w_dist = selected_dist
                    w_reps = st.number_input("Total Max Intervals/Segments Today", min_value=1, max_value=20, value=6)
                with w_col3:
                    calc_mode = st.radio("Time Entry Mode:", ["Individual Splits", "Continuous Clock (Elapsed)"], index=0)
                    restart_rep = 0
                    if calc_mode == "Continuous Clock (Elapsed)" and selected_dist == "Split":
                        restart_rep = st.number_input("Restart clock at Rep # (0 = never)", min_value=0, max_value=20, value=0, help="For a 2+1 split (3 total segments), set this to 3 so the 3rd column starts from 0.")

                st.markdown("---")
                st.markdown("**Number-Only Entry Format**")
                time_entry_format = st.radio("How should the app read numbers typed without a colon?", ["Mins/Secs (e.g., 104 = 1:04, 530 = 5:30)", "Total Seconds (e.g., 82 = 1:22, 104 = 1:44)"], horizontal=True)
                st.caption("Leave cells blank to skip an athlete. Select 'Not Assigned' to record they were intentionally excluded.")

                active_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") & (roster_data["Active_Clean"].isin(ACTIVE_FLAGS))].copy().sort_values(["Gender", "Last_Name"])
                grid_data = [{"Username": row["Username"], "Athlete Name": f"{row['First_Name']} {row['Last_Name']}", "Status": "Present", **{f"Rep {i}": "" for i in range(1, w_reps + 1)}} for _, row in active_athletes.iterrows()]
                column_config = {"Username": None, "Athlete Name": st.column_config.TextColumn("Athlete Name", disabled=True), "Status": st.column_config.SelectboxColumn("Status", options=["Present", "Not Assigned", "Sick", "Injured", "Unexcused"], required=True)}
                for i in range(1, w_reps + 1): column_config[f"Rep {i}"] = st.column_config.TextColumn(f"Rep {i}")
                edited_df = st.data_editor(pd.DataFrame(grid_data), hide_index=True, column_config=column_config, use_container_width=True, key="new_workout_editor")

                if st.button("Save Workout Data", type="primary"):
                    if not w_dist:
                        st.error("Please enter Distance/Rep Details before saving.")
                    else:
                        formatted_date = pd.to_datetime(w_date).strftime("%Y-%m-%d")
                        w_weather = get_weather_for_date(formatted_date)
                        season = calculate_season(formatted_date)
                        new_workout_rows = []
                        for _, row in edited_df.iterrows():
                            status = row["Status"]
                            raw_times = [str(row[f"Rep {i}"]).strip() for i in range(1, w_reps + 1) if str(row[f"Rep {i}"]).strip()]
                            if status != "Present" and not raw_times:
                                new_workout_rows.append({"Date": formatted_date, "Workout_Type": w_type, "Rep_Distance": w_dist, "Weather": w_weather, "Username": row["Username"], "Status": status, "Splits": "", "Season": season})
                                continue
                            if raw_times:
                                parsed_seconds = [time_to_seconds(parse_fast_time(t, time_entry_format)) for t in raw_times]
                                if calc_mode == "Continuous Clock (Elapsed)":
                                    final_splits = [seconds_to_time(parsed_seconds[i]) if i == 0 or (restart_rep > 0 and (i + 1) == restart_rep) else seconds_to_time(parsed_seconds[i] - parsed_seconds[i-1]) for i in range(len(parsed_seconds))]
                                else:
                                    final_splits = [seconds_to_time(s) for s in parsed_seconds]
                                split_string = ", ".join([s for s in final_splits if s])
                                new_workout_rows.append({"Date": formatted_date, "Workout_Type": w_type, "Rep_Distance": w_dist, "Weather": w_weather, "Username": row["Username"], "Status": status, "Splits": split_string, "Season": season})
                        if new_workout_rows:
                            updated = pd.concat([workouts_data, pd.DataFrame(new_workout_rows)], ignore_index=True)
                            with st.spinner("Saving workout..."): conn.update(worksheet="Workouts", data=updated)
                            st.session_state["workout_saved"] = True; st.cache_data.clear(); st.rerun()

        elif workout_action == "Edit/Delete Existing Workout":
            st.subheader("Edit / Fix Existing Workout")
            if workouts_data.empty or workouts_data["Date"].isna().all():
                st.info("No workout data has been logged yet.")
            else:
                unique_workouts = workouts_data[["Date", "Workout_Type", "Rep_Distance"]].dropna(subset=["Date", "Workout_Type"]).drop_duplicates()
                unique_workouts["Date_Obj"] = pd.to_datetime(unique_workouts["Date"], errors="coerce")
                unique_workouts = unique_workouts.sort_values("Date_Obj", ascending=False)
                workout_options = {}
                for _, row in unique_workouts.iterrows():
                    key = f"{row['Date']}|{row['Workout_Type']}"
                    try: nice_date = row["Date_Obj"].strftime("%b %d, %Y")
                    except: nice_date = str(row["Date"])
                    workout_options[key] = f"{nice_date} - {row['Workout_Type']} [{row.get('Rep_Distance', 'No Details')}]"
                if not workout_options:
                    st.info("No valid workouts found to edit.")
                else:
                    col_w1, _ = st.columns([1, 1])
                    with col_w1: selected_key = st.selectbox("Select Workout to Edit:", options=list(workout_options.keys()), format_func=lambda x: workout_options[x])
                    old_date, old_type = selected_key.split("|")
                    target_rows = workouts_data[(workouts_data["Date"] == old_date) & (workouts_data["Workout_Type"] == old_type)].copy()
                    if not target_rows.empty:
                        st.markdown("### Update Workout Details")
                        current_date_val = pd.to_datetime(target_rows.iloc[0]["Date"], errors="coerce").date()
                        current_type = target_rows.iloc[0]["Workout_Type"]
                        current_dist = target_rows.iloc[0]["Rep_Distance"]
                        current_weather = target_rows.iloc[0]["Weather"]
                        type_options = ["Tempo", "Intervals", "Hills", "Other"]
                        h1, h2 = st.columns(2)
                        with h1:
                            new_w_date = st.date_input("Workout Date", value=current_date_val)
                            new_w_type = st.selectbox("Workout Type", type_options, index=type_options.index(current_type) if current_type in type_options else 3)
                            st.markdown(f"**Current Weather:** {current_weather}")
                        with h2:
                            new_w_dist = st.text_input("Distance/Rep Details", value=current_dist, autocomplete="off")
                        st.markdown("### Update Athlete Splits")
                        max_reps = max((len([s.strip() for s in str(r.get("Splits", "")).split(",") if s.strip()]) for _, r in target_rows.iterrows()), default=1)
                        grid_data = []
                        for _, r in target_rows.iterrows():
                            match = roster_data[roster_data["Username"] == r["Username"]]
                            a_name = f"{match.iloc[0]['First_Name']} {match.iloc[0]['Last_Name']}" if not match.empty else r["Username"]
                            splits = [s.strip() for s in str(r.get("Splits", "")).split(",") if s.strip()]
                            entry = {"Username": r["Username"], "Athlete Name": a_name, "Status": r["Status"], **{f"Rep {i}": splits[i-1] if i <= len(splits) else "" for i in range(1, max_reps + 1)}}
                            grid_data.append(entry)
                        column_config = {"Username": None, "Athlete Name": st.column_config.TextColumn("Athlete Name", disabled=True),
                                         "Status": st.column_config.SelectboxColumn("Status", options=["Present", "Not Assigned", "Sick", "Injured", "Unexcused"], required=True)}
                        for i in range(1, max_reps + 1): column_config[f"Rep {i}"] = st.column_config.TextColumn(f"Rep {i}")
                        st.caption("Edit the splits below. Type the exact corrected time (e.g., 1:04).")
                        edited_df = st.data_editor(pd.DataFrame(grid_data), hide_index=True, column_config=column_config, use_container_width=True, key="edit_workout_editor")
                        col_save, col_del = st.columns(2)
                        with col_save:
                            if st.button("💾 Save All Edits", type="primary", use_container_width=True):
                                keep_rows = workouts_data[~((workouts_data["Date"] == old_date) & (workouts_data["Workout_Type"] == old_type))]
                                formatted_new_date = pd.to_datetime(new_w_date).strftime("%Y-%m-%d")
                                final_weather = get_weather_for_date(formatted_new_date) if formatted_new_date != old_date or not current_weather or "Can't" in current_weather else current_weather
                                new_rows = [{"Date": formatted_new_date, "Workout_Type": new_w_type, "Rep_Distance": new_w_dist, "Weather": final_weather, "Username": row["Username"], "Status": row["Status"],
                                             "Splits": ", ".join([str(row[f"Rep {i}"]).strip() for i in range(1, max_reps + 1) if str(row[f"Rep {i}"]).strip()]), "Season": calculate_season(formatted_new_date)} for _, row in edited_df.iterrows()]
                                updated = pd.concat([keep_rows, pd.DataFrame(new_rows)], ignore_index=True)
                                with st.spinner("Updating workout..."): conn.update(worksheet="Workouts", data=updated)
                                st.success("Workout updated successfully!"); st.cache_data.clear(); st.rerun()
                        with col_del:
                            if st.button("🗑️ Delete This Workout Entirely", use_container_width=True):
                                keep = workouts_data[~((workouts_data["Date"] == old_date) & (workouts_data["Workout_Type"] == old_type))]
                                with st.spinner("Deleting workout..."): conn.update(worksheet="Workouts", data=keep)
                                st.success("Workout deleted!"); st.cache_data.clear(); st.rerun()

def _build_split_sheet_html(p_meet, races_df, roster_df, race_list=None):
    """Shared helper: builds HTML body for split sheets (new or reprint)."""
    active_athletes = roster_df[(roster_df["Role"].str.upper() == "ATHLETE")].copy()
    athlete_opts = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}" for _, row in active_athletes.iterrows()}

    def get_prior_time(uname, meet_name):
        prior = races_df[(races_df["Username"] == uname) & (races_df["Meet_Name"] == meet_name) & (races_df["Total_Time"].str.strip() != "")].copy()
        if not prior.empty:
            prior["sec"] = prior["Total_Time"].apply(time_to_seconds)
            prior = prior[prior["sec"] > 0]
            if not prior.empty: return seconds_to_time(prior["sec"].min())
        all_5k = races_df[(races_df["Username"] == uname) & (races_df["Distance"].str.upper() == "5K") & (races_df["Total_Time"].str.strip() != "")].copy()
        if not all_5k.empty:
            all_5k["sec"] = all_5k["Total_Time"].apply(time_to_seconds)
            all_5k = all_5k[all_5k["sec"] > 0]
            if not all_5k.empty: return f"{seconds_to_time(all_5k['sec'].min())} (PR)"
        return ""

    html = f"<h2>{p_meet} - Split Sheet</h2>"
    meet_rows = races_df[races_df["Meet_Name"] == p_meet]
    races_to_show = race_list if race_list else [{"name": rn, "dist": meet_rows[meet_rows["Race_Name"] == rn]["Distance"].iloc[0] if not meet_rows[meet_rows["Race_Name"] == rn].empty else ""} for rn in meet_rows["Race_Name"].unique()]

    for race in races_to_show:
        r_name = race["name"] if isinstance(race, dict) else race
        r_dist = race["dist"] if isinstance(race, dict) else ""
        runners = race.get("runners", meet_rows[meet_rows["Race_Name"] == r_name]["Username"].tolist()) if isinstance(race, dict) else meet_rows[meet_rows["Race_Name"] == r_name]["Username"].tolist()
        html += f"<div class='keep-together'><h3>{r_name} ({r_dist})</h3><table><tr><th>Athlete</th><th>Prior Best at Meet</th><th>1 Mile</th><th>2 Mile</th><th>Finish</th></tr>"
        for uname in runners:
            html += f"<tr><td>{athlete_opts.get(uname, uname)}</td><td>{get_prior_time(uname, p_meet)}</td><td></td><td></td><td></td></tr>"
        html += "</table></div>"
    return html

def _tab_meet_setup():
    st.subheader("Meet Setup & Printables")
    print_action = st.radio("Select Tool:", ["Attendance Sheet", "Create New Meet / Print Sheet", "Re-Print Existing Meet"], horizontal=True)
    st.markdown("---")

    if print_action == "Attendance Sheet":
        col_a1, col_a2, col_a3 = st.columns(3)
        p_gender = col_a1.selectbox("Team", ["Boys", "Girls"])
        p_type = col_a2.selectbox("Season Type", ["Summer", "School Year"])
        p_week = col_a3.text_input("Week Of (e.g., Aug 12 - 16)")
        if st.button("Generate Attendance Sheet", type="primary"):
            target_gender = "Male" if p_gender == "Boys" else "Female"
            active_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") & (roster_data["Active_Clean"].isin(ACTIVE_FLAGS)) & (roster_data["Gender"].str.title() == target_gender)].sort_values("Last_Name")
            if p_type == "Summer":
                columns_data = [("Mon In", True), ("Mon Out", True), ("Tues In", False), ("Tues Out", False), ("Thur In", True), ("Thur Out", True)]
            else:
                columns_data = [("Mon In", True), ("Mon Out", True), ("Tues In", False), ("Tues Out", False), ("Wed In", True), ("Wed Out", True), ("Thurs In", False), ("Thurs Out", False), ("Fri In", True), ("Fri Out", True)]
            html = f"<h2>{p_gender.upper()} {p_type.upper()} ATTENDANCE</h2>"
            if p_week: html += f"<h3>WEEK OF: {p_week}</h3>"
            html += "<table style='table-layout: fixed;'><tr><th style='width: 25%;'>Runner</th>"
            for c_text, is_shaded in columns_data:
                html += f"<th style='background-color: {'#e2e8f0' if is_shaded else '#ffffff'} !important;'>{c_text}</th>"
            html += "</tr>"
            for _, row in active_athletes.iterrows():
                html += f"<tr><td>{row['Last_Name']}, {row['First_Name']}</td>"
                for _, is_shaded in columns_data:
                    html += f"<td style='background-color: {'#f1f5f9' if is_shaded else '#ffffff'} !important;'></td>"
                html += "</tr>"
            html += "</table>"
            final_html = wrap_html_for_print(f"{p_gender} Attendance", html, is_attendance=True)
            st.success("Your printable sheet is ready! Download the HTML file and print it.")
            st.download_button(label="Download Printable HTML Sheet", data=final_html, file_name=f"{p_gender}_Attendance.html", mime="text/html")

    elif print_action == "Create New Meet / Print Sheet":
        st.markdown("Build your race entries here to instantly generate a printable clipboard sheet AND save the pending roster to the database.")
        c_m1, c_m2 = st.columns(2)
        with c_m1: p_meet = st.text_input("New Meet Name", placeholder="e.g. Asics Invitational", autocomplete="off")
        with c_m2: p_date = st.date_input("Meet Date")
        st.markdown("---")
        race_count = st.number_input("How many separate races do you need?", min_value=1, max_value=10, value=2)
        active_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") & (roster_data["Active_Clean"].isin(ACTIVE_FLAGS))].copy()
        assigned_runners = set()
        for j in range(race_count): assigned_runners.update(st.session_state.get(f"rrunners_{j}", []))
        races_to_print = []
        for i in range(race_count):
            st.markdown(f"**Race Block {i+1}**")
            r_col1, r_col2, r_col3 = st.columns([2, 1, 1])
            with r_col1: r_name = st.text_input("Race Title", placeholder="e.g. Boys Champ", key=f"rname_{i}", autocomplete="off")
            with r_col2: r_dist = st.selectbox("Distance", ["5K", "2 Mile", "Other"], key=f"rdist_{i}")
            with r_col3: r_filter = st.selectbox("Filter Runners", ["All", "Boys", "Girls"], key=f"rfilt_{i}")
            avail = active_athletes.copy()
            if r_filter == "Boys": avail = avail[avail["Gender"].str.title() == "Male"]
            elif r_filter == "Girls": avail = avail[avail["Gender"].str.title() == "Female"]
            other_runners = assigned_runners - set(st.session_state.get(f"rrunners_{i}", []))
            avail = avail[~avail["Username"].isin(other_runners)]
            athlete_opts = {row["Username"]: f"{row['First_Name']} {row['Last_Name']}" for _, row in avail.sort_values("Last_Name").iterrows()}
            r_runners = st.multiselect("Select Runners", options=list(athlete_opts.keys()), format_func=lambda x: athlete_opts[x], key=f"rrunners_{i}")
            if r_name and r_runners: races_to_print.append({"name": r_name, "dist": r_dist, "runners": r_runners})
            st.markdown("<br>", unsafe_allow_html=True)

        if st.button("Generate Sheet & Save Meet Setup", type="primary"):
            if not p_meet: st.error("Please enter a Meet Name.")
            elif not races_to_print: st.warning("Please configure at least one race with runners.")
            else:
                formatted_date = pd.to_datetime(p_date).strftime("%Y-%m-%d")
                season = calculate_season(formatted_date)
                new_rows = [{"Date": formatted_date, "Meet_Name": p_meet, "Race_Name": race["name"], "Distance": race["dist"], "Username": uname, "Mile_1": "", "Mile_2": "", "Total_Time": "", "Weight": 1.0, "Active": "TRUE", "Season": season}
                            for race in races_to_print for uname in race["runners"]
                            if races_data[(races_data["Meet_Name"] == p_meet) & (races_data["Race_Name"] == race["name"]) & (races_data["Username"] == uname)].empty]
                if new_rows:
                    updated = pd.concat([races_data, pd.DataFrame(new_rows)], ignore_index=True)
                    with st.spinner("Saving to database..."): conn.update(worksheet="Races", data=updated)
                    st.cache_data.clear()
                html_body = _build_split_sheet_html(p_meet, races_data, roster_data, races_to_print)
                final_html = wrap_html_for_print(f"{p_meet} Split Sheet", html_body)
                st.success(f"Successfully created '{p_meet}'! You can now download the sheet or go to 'Data Entry' to input times.")
                st.download_button(label="Download Printable HTML Sheet", data=final_html, file_name=f"{p_meet.replace(' ', '_')}_Sheet.html", mime="text/html")

    elif print_action == "Re-Print Existing Meet":
        active_meets = races_data[races_data["Active"].isin(ACTIVE_FLAGS)]["Meet_Name"].dropna().unique().tolist()
        col_p1, _ = st.columns([1, 1])
        with col_p1: p_meet = st.selectbox("Select Existing Meet to Print", ["-- Select Meet --"] + active_meets)
        if p_meet != "-- Select Meet --":
            if st.button("Generate Print Sheet", type="primary"):
                html_body = _build_split_sheet_html(p_meet, races_data, roster_data)
                final_html = wrap_html_for_print(f"{p_meet} Split Sheet", html_body)
                st.success("Your printable sheet is ready!")
                st.download_button(label="Download Printable HTML Sheet", data=final_html, file_name=f"{p_meet.replace(' ', '_')}_Sheet.html", mime="text/html")

# ---- ATHLETE VIEW ----
def _athlete_view():
    st.header("Training Dashboard")
    st.markdown("Your historical training and race data is below.")
    tab_dash, tab_rankings, tab_resources = st.tabs(["My Season", "Team Rankings", "Team Resources"])

    with tab_dash:
        u_races = races_data[races_data["Username"] == st.session_state["username"]]
        u_works = workouts_data[workouts_data["Username"] == st.session_state["username"]]
        athlete_seasons = sorted(set(u_races["Season"].tolist() + u_works["Season"].tolist()), reverse=True) or [CURRENT_SEASON]
        col_s1, _ = st.columns([1, 3])
        with col_s1: sel_season = st.selectbox("View Season:", athlete_seasons, key="athlete_dash_season")
        st.markdown("---")
        user_races = u_races[(u_races["Active"].isin(ACTIVE_FLAGS)) & (u_races["Season"] == sel_season)].copy()
        user_workouts = u_works[u_works["Season"] == sel_season].copy()
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric(label=f"Races Completed ({sel_season})", value=len(user_races[user_races["Total_Time"].str.strip() != ""]))
        col_m2.metric(label=f"Workouts Logged ({sel_season})", value=len(user_workouts[user_workouts["Status"] == "Present"]))
        fastest_5k = "N/A"
        if not user_races.empty:
            five_k = user_races[user_races["Distance"].str.upper() == "5K"]
            if not five_k.empty:
                fastest_sec = five_k["Total_Time"].apply(time_to_seconds).replace(0, float("inf")).min()
                if fastest_sec != float("inf"): fastest_5k = seconds_to_time(fastest_sec)
        col_m3.metric(label=f"5K PR ({sel_season})", value=fastest_5k)
        st.markdown("<br>", unsafe_allow_html=True)
        sub_races, sub_workouts, sub_paces, sub_career = st.tabs(["Race Results", "Workouts", "Training Paces", "Career PRs"])
        with sub_races: display_athlete_races(st.session_state["username"], sel_season)
        with sub_workouts: display_athlete_workouts(st.session_state["username"], sel_season)
        with sub_paces: display_suggested_paces(st.session_state["username"])
        with sub_career: display_career_history(st.session_state["username"])

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
