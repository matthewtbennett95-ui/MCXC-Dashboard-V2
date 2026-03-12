import streamlit as st
import pandas as pd
from streamlit_gsheets import GSheetsConnection
from utils_math import add_season_column

# ==========================================
# --- DEFAULT FALLBACK DATA ---
# ==========================================
# If these sheets are accidentally deleted from the Google Sheet, the app will use these.

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
    {"VDOT": 30, "5K_Time": "30:40", "2_Mile_Time": "19:19", "Easy_Pace": "12:17-12:59", "Tempo_Mile": "10:19", "Tempo_400m": "2:34", "Interval_400m": "2:22", "Interval_800m": "4:44", "Interval_1000m": "5:55", "Interval_1200m": "7:06", "Interval_Mile": "9:28"}
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
    {"Workout": "Hills (I Pace)", "Pace / Time": "29:00+ (5K)", "Cycle / Rest": "15 minute cycle"}
])

DEFAULT_DOCS = pd.DataFrame([
    {"Title": "Team Expectations & Rules", "URL": ""},
    {"Title": "Meet Schedule & Location Links", "URL": ""}
])


# ==========================================
# --- DATA LOADING & CACHING FUNCTION ---
# ==========================================

@st.cache_data(ttl=600, show_spinner="Fetching team data...")
def load_and_clean_data():
    """Connects to Google Sheets, loads all tabs, handles fallbacks, and cleans data."""
    conn = st.connection("gsheets", type=GSheetsConnection)

    # 1. Load Main Sheets
    roster_data = conn.read(worksheet="Roster", ttl=600).dropna(how="all")
    races_data = conn.read(worksheet="Races", ttl=600).dropna(how="all")
    workouts_data = conn.read(worksheet="Workouts", ttl=600).dropna(how="all")

    # 2. Load Fallback Sheets (Try-Except block prevents crashes if sheet is missing)
    try:
        vdot_data = conn.read(worksheet="VDOT", ttl=600).dropna(how="all")
        if "5K_Time" not in vdot_data.columns: vdot_data = DEFAULT_VDOT
    except Exception:
        vdot_data = DEFAULT_VDOT

    try:
        rest_data = conn.read(worksheet="Rest", ttl=600).dropna(how="all")
        if "Workout" not in rest_data.columns: rest_data = DEFAULT_REST
    except Exception:
        rest_data = DEFAULT_REST

    try:
        docs_data = conn.read(worksheet="Documents", ttl=600).dropna(how="all")
        if "Title" not in docs_data.columns: docs_data = DEFAULT_DOCS
    except Exception:
        docs_data = DEFAULT_DOCS

    # ==========================================
    # --- DATA CLEANUP & PREP ---
    # ==========================================

    # Ensure required Roster columns exist
    for col in ["Username", "First_Name", "Last_Name", "Grade", "Role", "Password", "Active_Clean"]:
        if col not in roster_data.columns:
            roster_data[col] = ""
    if "Gender" not in roster_data.columns: roster_data["Gender"] = "N/A"

    # Ensure required Races columns exist
    for col in ["Date", "Meet_Name", "Race_Name", "Distance", "Username", "Mile_1", "Mile_2", "Total_Time", "Weight", "Active"]:
        if col not in races_data.columns: 
            races_data[col] = 1.0 if col == "Weight" else "TRUE" if col == "Active" else ""

    # Clean Race column types
    races_data["Weight"] = pd.to_numeric(races_data["Weight"], errors="coerce").fillna(1.0)
    races_data["Active"] = races_data["Active"].astype(str).str.strip().str.upper()
    races_data.loc[races_data["Active"] == "NAN", "Active"] = "TRUE"

    # Ensure required Workouts columns exist
    for col in ["Date", "Workout_Type", "Rep_Distance", "Weather", "Username", "Status", "Splits"]:
        if col not in workouts_data.columns: workouts_data[col] = ""

    # Add vectorized Season column
    races_data = add_season_column(races_data, "Date")
    workouts_data = add_season_column(workouts_data, "Date")

    return roster_data, races_data, workouts_data, vdot_data, rest_data, docs_data
