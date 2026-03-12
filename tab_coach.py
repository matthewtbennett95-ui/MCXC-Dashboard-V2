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
        st.info("Edit the table below to add, remove, or update athletes. **Check the 'Active_Clean' box** for runners who are currently on the team.")
        
        # We need a clean copy of the roster for the data editor
        display_roster = roster_data.copy()
        
        # Convert Active_Clean to boolean for checkboxes
        display_roster["Active_Clean"] = display_roster["Active_Clean"].isin(["TRUE", "1", "1.0", True])
        
        # Setup the column configuration for the editor
        col_config = {
            "Username": st.column_config.TextColumn("Username (Unique)", required=True),
            "First_Name": st.column_config.TextColumn("First Name", required=True),
            "Last_Name": st.column_config.TextColumn("Last Name", required=True),
            "Gender": st.column_config.SelectboxColumn("Gender", options=["Male", "Female", "N/A"], required=True),
            "Grade": st.column_config.SelectboxColumn("Grade", options=["9th", "10th", "11th", "12th", "Middle School", "Coach", "Alumni"], required=True),
            "Role": st.column_config.SelectboxColumn("Role", options=["Athlete", "Coach"], required=True),
            "Password": st.column_config.TextColumn("Password", required=True),
            "Active_Clean": st.column_config.CheckboxColumn("Active Roster?", default=True)
        }
        
        # Display the data editor
        edited_roster = st.data_editor(
            display_roster,
            column_config=col_config,
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="roster_editor"
        )
        
        # Convert boolean back to "TRUE"/"FALSE" strings before saving
        edited_roster["Active_Clean"] = edited_roster["Active_Clean"].astype(str).str.upper()
        
        # Save changes button
        if st.button("💾 Save Roster Changes", type="primary"):
            try:
                # Use the connection from utils_data (we need to initialize it here for writing)
                conn = st.connection("gsheets", type=GSheetsConnection)
                
                # We need to make sure we don't accidentally drop empty rows in the middle
                # that google sheets might complain about, but the editor usually handles this.
                conn.update(worksheet="Roster", data=edited_roster)
                st.success("✅ Roster updated successfully! The cache will refresh automatically.")
                
                # Clear the Streamlit cache so the next load pulls the fresh data!
                st.cache_data.clear()
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Error saving roster: {e}")
                
        st.markdown("---")
        
        # Archive / Restore Sub-Tabs
        st.markdown("### Advanced Roster Actions")
        tab_archive, tab_restore, tab_graduate = st.tabs(["Archive Individual", "Restore Member", "Graduate Seniors"])
        
        with tab_archive:
            st.markdown("Archiving a member removes them from active dropdowns but keeps their history.")
            active_only = roster_data[roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"])]
            if not active_only.empty:
                archive_names = (active_only["First_Name"] + " " + active_only["Last_Name"] + " (" + active_only["Username"] + ")").tolist()
                to_archive = st.selectbox("Select Member to Archive:", ["-- Select --"] + archive_names, key="archive_select")
                
                if to_archive != "-- Select --" and st.button("Archive Member"):
                    target_user = to_archive.split("(")[-1].strip(")")
                    
                    try:
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        new_roster = roster_data.copy()
                        new_roster.loc[new_roster["Username"] == target_user, "Active_Clean"] = "FALSE"
                        
                        # Set their races to inactive as well
                        new_races = races_data.copy()
                        new_races.loc[new_races["Username"] == target_user, "Active"] = "FALSE"
                        
                        conn.update(worksheet="Roster", data=new_roster)
                        conn.update(worksheet="Races", data=new_races)
                        
                        st.success(f"Archived {to_archive} successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error archiving: {e}")
            else:
                st.info("No active members to archive.")
                
        with tab_restore:
            st.markdown("Restoring a member brings them back to the active roster and re-activates their race data.")
            inactive_only = roster_data[~roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"])]
            if not inactive_only.empty:
                restore_names = (inactive_only["First_Name"] + " " + inactive_only["Last_Name"] + " (" + inactive_only["Username"] + ")").tolist()
                to_restore = st.selectbox("Select Member to Restore:", ["-- Select --"] + restore_names, key="restore_select")
                
                if to_restore != "-- Select --" and st.button("Restore Member"):
                    target_user = to_restore.split("(")[-1].strip(")")
                    
                    try:
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        new_roster = roster_data.copy()
                        new_roster.loc[new_roster["Username"] == target_user, "Active_Clean"] = "TRUE"
                        
                        new_races = races_data.copy()
                        new_races.loc[new_races["Username"] == target_user, "Active"] = "TRUE"
                        
                        conn.update(worksheet="Roster", data=new_roster)
                        conn.update(worksheet="Races", data=new_races)
                        
                        st.success(f"Restored {to_restore} successfully!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error restoring: {e}")
            else:
                st.info("No archived members found.")
                
        with tab_graduate:
            st.warning("⚠️ This will advance all active 9th, 10th, and 11th graders to the next grade. It will also archive all current 12th graders and convert them to 'Alumni'. Use this only once at the end of the school year.")
            
            grad_confirm = st.text_input("Type 'GRADUATE' to confirm:")
            if st.button("Execute Grade Advancement", type="primary", disabled=(grad_confirm != "GRADUATE")):
                try:
                    conn = st.connection("gsheets", type=GSheetsConnection)
                    new_roster = roster_data.copy()
                    
                    # 1. Archive seniors and label them Alumni
                    seniors_mask = (new_roster["Grade"] == "12th") & (new_roster["Active_Clean"].isin(["TRUE", "1", "1.0"]))
                    senior_usernames = new_roster.loc[seniors_mask, "Username"].tolist()
                    
                    new_roster.loc[seniors_mask, "Active_Clean"] = "FALSE"
                    new_roster.loc[seniors_mask, "Grade"] = "Alumni"
                    
                    # Also set their races to inactive
                    new_races = races_data.copy()
                    if senior_usernames:
                        new_races.loc[new_races["Username"].isin(senior_usernames), "Active"] = "FALSE"
                        conn.update(worksheet="Races", data=new_races)
                    
                    # 2. Advance other grades
                    new_roster.loc[(new_roster["Grade"] == "11th") & (new_roster["Active_Clean"].isin(["TRUE", "1", "1.0"])), "Grade"] = "12th"
                    new_roster.loc[(new_roster["Grade"] == "10th") & (new_roster["Active_Clean"].isin(["TRUE", "1", "1.0"])), "Grade"] = "11th"
                    new_roster.loc[(new_roster["Grade"] == "9th") & (new_roster["Active_Clean"].isin(["TRUE", "1", "1.0"])), "Grade"] = "10th"
                    new_roster.loc[(new_roster["Grade"] == "Middle School") & (new_roster["Active_Clean"].isin(["TRUE", "1", "1.0"])), "Grade"] = "9th"
                    
                    conn.update(worksheet="Roster", data=new_roster)
                    st.success("🎉 Roster successfully advanced for the new season!")
                    st.cache_data.clear()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error executing advancement: {e}")

    # ==========================================
    # --- 4. DATA ENTRY TAB ---
    # ==========================================
    with tab_entry:
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
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        with st.spinner("Updating database..."): conn.update(worksheet="VDOT", data=edited_vdot)
                        st.success("✅ Pace Chart Updated!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Error saving: {e}")
                    
            with edit_tab2:
                st.markdown("**Editable Rest Cycles**")
                edited_rest = st.data_editor(rest_data, num_rows="dynamic", use_container_width=True)
                if st.button("💾 Save Rest Cycles", type="primary"):
                    try:
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        with st.spinner("Updating database..."): conn.update(worksheet="Rest", data=edited_rest)
                        st.success("✅ Rest Cycles Updated!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e: st.error(f"Error saving: {e}")

        elif de_type == "Manage Meet Weights":
            st.subheader("Adjust Meet Difficulty Weights")
            st.info("Assign a weight multiplier to a meet. A harder course (e.g. 0.98x) will adjust the athlete's time downward in the 'Weighted Average' rankings so they aren't penalized for tough terrain. Leave at 1.0 for a standard flat course.")
            
            all_meets = sorted(races_data["Meet_Name"].unique().tolist())
            if not all_meets:
                st.warning("No meets found in the database.")
            else:
                sel_meet_weight = st.selectbox("Select Meet to Adjust:", all_meets)
                current_w = races_data[races_data["Meet_Name"] == sel_meet_weight]["Weight"].iloc[0] if not races_data[races_data["Meet_Name"] == sel_meet_weight].empty else 1.0
                
                new_w = st.number_input(f"Multiplier for {sel_meet_weight}", min_value=0.5, max_value=2.0, value=float(current_w), step=0.01)
                st.markdown("*Examples:* \n* `1.0` = Standard (No Change) \n* `0.98` = Tough Course (Time drops by 2%) \n* `1.02` = Fast/Short Course (Time increases by 2%)")
                
                if st.button("💾 Update Meet Weight", type="primary"):
                    try:
                        conn = st.connection("gsheets", type=GSheetsConnection)
                        new_races = races_data.copy()
                        new_races.loc[new_races["Meet_Name"] == sel_meet_weight, "Weight"] = new_w
                        with st.spinner("Updating weight database..."):
                            conn.update(worksheet="Races", data=new_races)
                        st.success(f"✅ Weight for {sel_meet_weight} successfully updated to {new_w}x!")
                        st.cache_data.clear()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error saving weight: {e}")

        elif de_type == "Archive Specific Meet":
            st.subheader("Archive a Specific Meet")
            st.info("If you entered results for the wrong meet or need to hide a meet from the rankings, select it below. This does NOT delete the data, it simply marks the results as inactive.")
            
            # Show meets with active races
            active_meets_df = races_data[races_data["Active"].isin(["TRUE", "1", "1.0"])]
            
            if active_meets_df.empty:
                st.warning("No active meets found in the database.")
            else:
                # Get unique meets for dropdown, sort them
                all_active_meets = sorted(active_meets_df["Meet_Name"].unique().tolist())
                sel_meet_archive = st.selectbox("Select Meet to Archive:", ["-- Select Meet --"] + all_active_meets)
                
                if sel_meet_archive != "-- Select Meet --":
                    st.warning(f"Are you sure you want to archive all results for **{sel_meet_archive}**?")
                    
                    if st.button(f"🗃️ Archive {sel_meet_archive}", type="primary"):
                        try:
                            conn = st.connection("gsheets", type=GSheetsConnection)
                            new_races = races_data.copy()
                            # Find all rows matching the meet and set Active to FALSE
                            new_races.loc[new_races["Meet_Name"] == sel_meet_archive, "Active"] = "FALSE"
                            
                            with st.spinner(f"Archiving {sel_meet_archive}..."):
                                conn.update(worksheet="Races", data=new_races)
                            
                            st.success(f"✅ All results for {sel_meet_archive} have been archived and hidden from team rankings!")
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error archiving meet: {e}")

        elif de_type == "Race Results":
            col_left, col_right = st.columns([1, 1])
            with col_left:
                st.subheader("Meet Setup")
                meet_name = st.text_input("Meet Name:")
                meet_date = st.date_input("Meet Date:", value=datetime.date.today())
                race_name = st.text_input("Race Division (e.g. Boys Varsity):")
                distance = st.selectbox("Distance:", ["5K", "2 Mile"])
                
                gender_filter = st.selectbox("Filter Roster by Gender:", ["All", "Male", "Female"])
                
                active_roster = roster_data[roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"])]
                if gender_filter != "All":
                    active_roster = active_roster[active_roster["Gender"] == gender_filter]
                
                st.markdown("**Select Runners to Enter**")
                available_runners = []
                for _, r in active_roster.iterrows():
                    available_runners.append(f"{r['First_Name']} {r['Last_Name']} ({r['Username']})")
                    
                selected_runners = st.multiselect("Runners:", available_runners)
                
            with col_right:
                if selected_runners and meet_name and race_name:
                    st.subheader("Time Entry")
                    st.info("Enter splits or skip to Total Time. Decimals are fully supported (e.g. 17:30.42).")
                    entry_data = []
                    
                    for runner_str in selected_runners:
                        st.markdown(f"**{runner_str.split('(')[0].strip()}**")
                        c1, c2, c3 = st.columns(3)
                        m1 = c1.text_input(f"Mile 1", key=f"m1_{runner_str}", placeholder="5:30")
                        m2 = c2.text_input(f"Mile 2", key=f"m2_{runner_str}", placeholder="11:15")
                        tt = c3.text_input(f"Total", key=f"tt_{runner_str}", placeholder="17:30.4")
                        st.markdown("<hr style='margin:0.5em 0'>", unsafe_allow_html=True)
                        entry_data.append({"user_str": runner_str, "m1": m1, "m2": m2, "tt": tt})
                        
                    if st.button("💾 Save All Race Results", type="primary", use_container_width=True):
                        new_rows = []
                        for ed in entry_data:
                            uname = ed["user_str"].split("(")[-1].strip(")")
                            
                            # Clean user input strings
                            clean_m1 = parse_fast_time(ed["m1"], "Splits")
                            clean_m2 = parse_fast_time(ed["m2"], "Splits")
                            clean_tt = parse_fast_time(ed["tt"], "Total")
                            
                            if clean_tt: 
                                new_rows.append({
                                    "Date": meet_date.strftime('%Y-%m-%d'),
                                    "Meet_Name": meet_name.strip(),
                                    "Race_Name": race_name.strip(),
                                    "Distance": distance,
                                    "Username": uname,
                                    "Mile_1": clean_m1,
                                    "Mile_2": clean_m2,
                                    "Total_Time": clean_tt,
                                    "Weight": 1.0,
                                    "Active": "TRUE"
                                })
                                
                        if new_rows:
                            try:
                                conn = st.connection("gsheets", type=GSheetsConnection)
                                updated_races = pd.concat([races_data, pd.DataFrame(new_rows)], ignore_index=True)
                                with st.spinner("Saving results to database..."):
                                    conn.update(worksheet="Races", data=updated_races)
                                st.success(f"✅ Saved {len(new_rows)} results successfully!")
                                st.cache_data.clear()
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error saving results: {e}")
                        else:
                            st.warning("No valid Total Times entered. Nothing saved.")
                elif not meet_name or not race_name:
                    st.info("👈 Fill out the Meet Name and Division on the left to unlock Time Entry.")
          elif de_type == "Workouts":
            workout_action = st.radio("Action:", ["Log New Workout", "Edit/Delete Existing Workout"], horizontal=True)
            
            if workout_action == "Log New Workout":
                if st.session_state.get("workout_saved", False):
                    st.success("Workout saved successfully to the database!")
                    if st.button("Log Another Workout"):
                        st.session_state["workout_saved"] = False
                        st.rerun()
                else:
                    st.subheader("Workout Data Entry")
                    w_col1, w_col2, w_col3 = st.columns(3)
                    with w_col1:
                        w_date = st.date_input("Workout Date", value=datetime.date.today())
                        w_type = st.selectbox("Workout Type", ["Tempo", "Intervals", "Hills", "Other"])
                    with w_col2:
                        if w_type == "Tempo": dist_options = ["400m", "Miles", "Split", "Other"]
                        elif w_type == "Intervals": dist_options = ["400m", "800m", "1000m", "1200m", "Mile", "Other"]
                        elif w_type == "Hills": dist_options = ["Repeats", "Circuit", "Other"]
                        else: dist_options = ["N/A"]
                        w_dist = st.selectbox("Rep Distance / Format", dist_options)
                    with w_col3:
                        w_weather = st.text_input("Weather (Optional)", value=get_weather_for_date(w_date))
                        
                    st.markdown("---")
                    st.markdown("### Attendance & Splits")
                    st.info("Mark attendance. For athletes who are 'Present', you can optionally record their average pace or specific splits in the text box. Leave blank if not taking splits.")
                    
                    filter_g = st.selectbox("Filter Roster by Gender:", ["All", "Male", "Female"], key="w_gender_filter")
                    active_r = roster_data[roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"])]
                    if filter_g != "All": active_r = active_r[active_r["Gender"] == filter_g]
                    
                    w_entries = []
                    for _, r in active_r.iterrows():
                        u = r["Username"]
                        name_str = f"{r['First_Name']} {r['Last_Name']} ({r['Grade']})"
                        c_name, c_status, c_split = st.columns([2, 1, 2])
                        c_name.markdown(f"**{name_str}**")
                        
                        stat = c_status.selectbox("Status", ["Present", "Absent", "Excused", "Injured"], key=f"status_{u}")
                        split_val = ""
                        if stat == "Present":
                            split_val = c_split.text_input("Avg Pace / Splits (Optional)", key=f"split_{u}", placeholder="e.g. 5:40 avg, or 1:20/1:22/1:21")
                        st.markdown("<hr style='margin:0.2em 0'>", unsafe_allow_html=True)
                        w_entries.append({"user": u, "status": stat, "splits": split_val})
                        
                    if st.button("💾 Save Entire Workout", type="primary", use_container_width=True):
                        new_rows = []
                        for e in w_entries:
                            new_rows.append({
                                "Date": w_date.strftime('%Y-%m-%d'),
                                "Workout_Type": w_type,
                                "Rep_Distance": w_dist,
                                "Weather": w_weather,
                                "Username": e["user"],
                                "Status": e["status"],
                                "Splits": e["splits"]
                            })
                            
                        try:
                            conn = st.connection("gsheets", type=GSheetsConnection)
                            updated_workouts = pd.concat([workouts_data, pd.DataFrame(new_rows)], ignore_index=True)
                            with st.spinner("Saving workout to database..."):
                                conn.update(worksheet="Workouts", data=updated_workouts)
                            st.session_state["workout_saved"] = True
                            st.cache_data.clear()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error saving workout: {e}")
                            
            elif workout_action == "Edit/Delete Existing Workout":
                st.subheader("Edit or Delete an Existing Workout")
                if workouts_data.empty:
                    st.warning("No workouts found in the database.")
                else:
                    unique_workouts = workouts_data[["Date", "Workout_Type", "Rep_Distance"]].drop_duplicates().sort_values("Date", ascending=False)
                    workout_strs = []
                    for _, r in unique_workouts.iterrows():
                        workout_strs.append(f"{r['Date']} - {r['Workout_Type']} ({r['Rep_Distance']})")
                    
                    sel_workout_str = st.selectbox("Select Workout to Edit/Delete:", ["-- Select --"] + workout_strs)
                    
                    if sel_workout_str != "-- Select --":
                        parts = sel_workout_str.split(" - ")
                        old_date = parts[0]
                        type_dist = parts[1].split(" (")
                        old_type = type_dist[0]
                        
                        target_rows = workouts_data[(workouts_data["Date"] == old_date) & (workouts_data["Workout_Type"] == old_type)].copy()
                        
                        st.markdown(f"**Editing {len(target_rows)} records for {sel_workout_str}**")
                        
                        e_col1, e_col2, e_col3 = st.columns(3)
                        with e_col1: new_date = st.date_input("New Date", pd.to_datetime(old_date))
                        with e_col2: new_type = st.selectbox("New Type", ["Tempo", "Intervals", "Hills", "Other"], index=["Tempo", "Intervals", "Hills", "Other"].index(old_type) if old_type in ["Tempo", "Intervals      
    # ==========================================
    # --- 5. MEET SETUP & PRINTABLES TAB ---
    # ==========================================
    with tab_print:
        st.subheader("Meet Setup & Printables")
        print_action = st.radio("Select Tool:", ["Attendance Sheet", "Create New Meet / Print Sheet", "Re-Print Existing Meet"], horizontal=True)
        st.markdown("---")
        
        if print_action == "Attendance Sheet":
            col_a1, col_a2, col_a3 = st.columns(3)
            with col_a1: p_gender = st.selectbox("Team", ["Boys", "Girls"])
            with col_a2: p_type = st.selectbox("Season Type", ["Summer", "School Year"])
            with col_a3: p_week = st.text_input("Week Of (e.g., Aug 12 - 16)")
            
            if st.button("Generate Attendance Sheet", type="primary"):
                active_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") & (roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"]))].copy()
                target_gender = "Male" if p_gender == "Boys" else "Female"
                active_athletes = active_athletes[active_athletes["Gender"].str.title() == target_gender].sort_values("Last_Name")
                
                html_body = f"<h2>{p_gender} XC Attendance: {p_week} ({p_type})</h2>"
                html_body += "<table><tr><th style='width: 30%'>Name</th>"
                
                headers = ["M", "T", "W", "Th", "F", "Sa"] if p_type == "Summer" else ["M", "T", "W", "Th", "F", "Sa", "Meet"]
                for h in headers: html_body += f"<th>{h}</th>"
                html_body += "<th>Notes</th></tr>"
                
                for _, a in active_athletes.iterrows():
                    html_body += f"<tr><td>{a['Last_Name']}, {a['First_Name']}</td>"
                    for _ in headers: html_body += "<td></td>"
                    html_body += "<td></td></tr>"
                    
                html_body += "</table>"
                final_html = wrap_html_for_print(f"Attendance - {p_gender} - {p_week}", html_body, is_attendance=True)
                
                st.success("Your printable attendance sheet is ready!")
                st.download_button(label="Download HTML Sheet", data=final_html, file_name=f"Attendance_{p_gender}_{p_week.replace(' ', '_')}.html", mime="text/html")
                
        elif print_action == "Create New Meet / Print Sheet":
            st.info("Creating a new Meet here builds a printable split sheet and pre-fills your 'Race Results' dropdowns!")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                p_meet = st.text_input("Meet Name:")
                p_date = st.date_input("Meet Date:", value=datetime.date.today())
                p_races_input = st.text_input("Races (comma separated, e.g. Boys V, Girls V, Boys JV)")
            
            with col_m2:
                p_filter = st.selectbox("Roster Filter:", ["All Active", "Boys Only", "Girls Only"])
                active_athletes = roster_data[(roster_data["Role"].str.upper() == "ATHLETE") & (roster_data["Active_Clean"].isin(["TRUE", "1", "1.0"]))].copy()
                if p_filter == "Boys Only": active_athletes = active_athletes[active_athletes["Gender"].str.title() == "Male"]
                elif p_filter == "Girls Only": active_athletes = active_athletes[active_athletes["Gender"].str.title() == "Female"]
                
                athlete_list = (active_athletes["First_Name"] + " " + active_athletes["Last_Name"] + " (" + active_athletes["Username"] + ")").tolist()
                p_selected = st.multiselect("Select Runners To Print:", athlete_list)
                
            if st.button("Generate Meet Split Sheet", type="primary", use_container_width=True):
                if not p_meet or not p_races_input:
                    st.error("Please provide a Meet Name and at least one Race.")
                else:
                    html = f"<h2>{p_meet} - {p_date.strftime('%B %d, %Y')}</h2>"
                    races = [r.strip() for r in p_races_input.split(",")]
                    
                    for r_name in races:
                        html += f"<h3>{r_name}</h3>"
                        html += "<table><tr><th style='width: 30%'>Athlete</th><th>Target/PR</th><th>Mile 1</th><th>Mile 2</th><th>Finish</th></tr>"
                        
                        for athlete_str in p_selected:
                            uname = athlete_str.split("(")[-1].strip(")")
                            a_name = athlete_str.split("(")[0].strip()
                            
                            prior_time = ""
                            prior_races = races_data[(races_data["Username"] == uname) & (races_data["Meet_Name"] == p_meet) & (races_data["Active"].isin(["TRUE", "1", "1.0"]))]
                            
                            if not prior_races.empty:
                                prior_races["Time_Sec"] = prior_races["Total_Time"].apply(time_to_seconds)
                                prior_races = prior_races[prior_races["Time_Sec"] > 0]
                                if not prior_races.empty:
                                    prior_time = f"{seconds_to_time(prior_races['Time_Sec'].min())} (Course PR)"
                                    
                            if not prior_time:
                                all_5k = races_data[(races_data["Username"] == uname) & (races_data["Distance"].str.upper() == "5K") & (races_data["Active"].isin(["TRUE", "1", "1.0"]))]
                                if not all_5k.empty:
                                    all_5k["Time_Sec"] = all_5k["Total_Time"].apply(time_to_seconds)
                                    all_5k = all_5k[all_5k["Time_Sec"] > 0]
                                    if not all_5k.empty:
                                        prior_time = f"{seconds_to_time(all_5k['Time_Sec'].min())} (Overall PR)"
                                        
                            html += f"<tr><td>{a_name}</td><td>{prior_time}</td><td></td><td></td><td></td></tr>"
                        html += "</table><br>"
                    
                    final_html = wrap_html_for_print(f"{p_meet} Split Sheet", html)
                    st.success("Your printable sheet is ready!")
                    st.download_button(label="Download Printable HTML Sheet", data=final_html, file_name=f"{p_meet.replace(' ', '_')}_Sheet.html", mime="text/html")

        elif print_action == "Re-Print Existing Meet":
            st.info("Select an existing meet from the database to instantly generate a printable split sheet for the athletes who ran it.")
            all_meets = sorted(races_data["Meet_Name"].unique().tolist())
            if not all_meets:
                st.warning("No meets found in the database.")
            else:
                sel_reprint = st.selectbox("Select Meet to Re-Print:", all_meets)
                meet_races = races_data[races_data["Meet_Name"] == sel_reprint].copy()
                
                if st.button("Generate Existing Meet Sheet", type="primary", use_container_width=True):
                    meet_date = meet_races["Date"].iloc[0] if not meet_races.empty else "Unknown Date"
                    html = f"<h2>{sel_reprint} - {meet_date}</h2>"
                    
                    for r_name, group in meet_races.groupby("Race_Name"):
                        html += f"<h3>{r_name}</h3>"
                        html += "<table><tr><th style='width: 30%'>Athlete</th><th>Target/PR</th><th>Mile 1</th><th>Mile 2</th><th>Finish</th></tr>"
                        
                        merged = pd.merge(group, roster_data[["Username", "First_Name", "Last_Name"]], on="Username", how="inner")
                        for _, row in merged.iterrows():
                            uname = row["Username"]
                            a_name = f"{row['First_Name']} {row['Last_Name']}"
                            
                            prior_time = ""
                            prior_course_races = races_data[(races_data["Username"] == uname) & (races_data["Meet_Name"] == sel_reprint) & (races_data["Date"] != meet_date)]
                            if not prior_course_races.empty:
                                prior_course_races["Time_Sec"] = prior_course_races["Total_Time"].apply(time_to_seconds)
                                prior_course_races = prior_course_races[prior_course_races["Time_Sec"] > 0]
                                if not prior_course_races.empty:
                                    prior_time = f"{seconds_to_time(prior_course_races['Time_Sec'].min())} (Course PR)"
                            
                            if not prior_time:
                                all_5k = races_data[(races_data["Username"] == uname) & (races_data["Distance"].str.upper() == "5K") & (races_data["Total_Time"].str.strip() != "")]
                                if not all_5k.empty:
                                    all_5k["Time_Sec"] = all_5k["Total_Time"].apply(time_to_seconds)
                                    all_5k = all_5k[all_5k["Time_Sec"] > 0]
                                    if not all_5k.empty:
                                        prior_time = f"{seconds_to_time(all_5k['Time_Sec'].min())} (PR)"

                            html += f"<tr><td>{a_name}</td><td>{prior_time}</td><td></td><td></td><td></td></tr>"
                        html += "</table><br>"
                    
                    final_html = wrap_html_for_print(f"{sel_reprint} Split Sheet", html)
                    st.success("Your printable sheet is ready!")
                    st.download_button(label="Download Printable HTML Sheet", data=final_html, file_name=f"{sel_reprint.replace(' ', '_')}_Sheet.html", mime="text/html")

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
