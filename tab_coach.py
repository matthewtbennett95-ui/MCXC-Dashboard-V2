import streamlit as st
import pandas as pd
import datetime

# Import our math, data, and visual buckets
from utils_math import wrap_html_for_print, get_weather_for_date, calculate_season
from utils_data import load_and_clean_data
from tab_profile import get_athlete_baseline, display_athlete_races, display_athlete_workouts, display_suggested_paces, display_career_history
from tab_rankings import show_rankings_tab
from streamlit_gsheets import GSheetsConnection

# Grab the cached database
roster_data, races_data, workouts_data, vdot_data, rest_data, docs_data = load_and_clean_data()
CURRENT_SEASON = calculate_season(datetime.date.today())

def show_coach_dashboard():
    """Main rendering function for the Coach Dashboard."""
    
    st.markdown("## 📋 Coach Dashboard")
    
    # Create the 6 main coach tabs
    tab_lookup, tab_roster, tab_entry, tab_rankings, tab_print, tab_resources = st.tabs([
        "Athlete Lookup", "Roster Management", "Data Entry", "Team Rankings", "Meet Setup & Printables", "Team Resources"
    ])
    
    # ==========================================
    # --- 1. ATHLETE LOOKUP TAB ---
    # ==========================================
    with tab_lookup:
        st.subheader("Athlete Lookup")
        active_roster = roster_data[roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"])]
        
        if active_roster.empty:
            st.warning("No active athletes found in roster.")
        else:
            athlete_names = (active_roster["First_Name"] + " " + active_roster["Last_Name"] + " (" + active_roster["Username"] + ")").tolist()
            selected_athlete_str = st.selectbox("Search Athlete:", ["-- Select Athlete --"] + athlete_names)
            
            if selected_athlete_str != "-- Select Athlete --":
                # Extract username from the parentheses
                target_username = selected_athlete_str.split("(")[-1].strip(")")
                target_user_info = roster_data[roster_data["Username"] == target_username].iloc[0]
                
                st.markdown(f"### {target_user_info['First_Name']} {target_user_info['Last_Name']} - Grade: {target_user_info['Grade']}")
                
                # Fetch available seasons for this specific athlete
                user_races = races_data[(races_data["Username"] == target_username) & (races_data["Active"].isin(["TRUE", "1", "1.0"]))]
                user_workouts = workouts_data[workouts_data["Username"] == target_username]
                all_seasons = sorted(list(set(user_races["Season"].tolist() + user_workouts["Season"].tolist())), reverse=True)
                if not all_seasons: all_seasons = [CURRENT_SEASON]
                
                sel_season = st.selectbox("View Season:", all_seasons, key="lookup_season")
                
                # Render the Athlete's profile using the functions we built in tab_profile.py!
                sub_races, sub_workouts, sub_paces, sub_career = st.tabs(["Race Results", "Workouts", "Training Paces", "Career PRs"])
                with sub_races: display_athlete_races(target_username, sel_season)
                with sub_workouts: display_athlete_workouts(target_username, sel_season)
                with sub_paces: display_suggested_paces(target_username)
                with sub_career: display_career_history(target_username)

    # ==========================================
    # --- 2. TEAM RANKINGS TAB ---
    # ==========================================
    with tab_rankings:
        # We call the fully modular function we built in tab_rankings.py!
        show_rankings_tab()

    # ==========================================
    # --- 3. ROSTER MANAGEMENT TAB ---
    # ==========================================
    with tab_roster:
        st.subheader("Roster Management")
        # PASTING INSTRUCTION: 
        # Paste your existing "with tab_roster:" st.data_editor and Archive/Restore logic here!

    # ==========================================
    # --- 4. DATA ENTRY TAB ---
    # ==========================================
    with tab_entry:
        st.subheader("Data Entry: Races & Workouts")
        # PASTING INSTRUCTION: 
        # Paste your existing "with tab_entry:" st.radio and form submission logic here!

    # ==========================================
    # --- 5. MEET SETUP & PRINTABLES TAB ---
    # ==========================================
    with tab_print:
        st.subheader("Printables & Sheets")
        # PASTING INSTRUCTION: 
        # Paste your existing "with tab_print:" logic here! 
        # Note: wrap_html_for_print is already imported at the top of this file for you to use!

    # ==========================================
    # --- 6. TEAM RESOURCES TAB ---
    # ==========================================
    with tab_resources:
        st.subheader("Team Resources & Links")
        if not docs_data.empty:
            for _, row in docs_data.iterrows():
                if row["URL"]:
                    st.markdown(f"- [{row['Title']}]({row['URL']})")
                else:
                    st.markdown(f"- {row['Title']} (No Link Provided)")
