import streamlit as st
import pandas as pd
import diag_tool_logic as logic # Import the backend logic
import os
import tempfile
import altair as alt # Added for the pie chart

# --- Page Configuration ---
st.set_page_config(
    page_title="Catapult Device Diagnostic Tool",
    page_icon="📡",
    layout="wide"
)

# --- App State Management ---
if 'devices' not in st.session_state:
    st.session_state.devices = []
if 'scan_errors' not in st.session_state:
    st.session_state.scan_errors = ""
if 'ghz_config' not in st.session_state:
    st.session_state.ghz_config = []
if 'public_keys' not in st.session_state:
    st.session_state.public_keys = []
if 'sessions' not in st.session_state:
    st.session_state.sessions = {}
if 'raw_debug_output' not in st.session_state:
    st.session_state.raw_debug_output = ""
if 'raw_orientation_output' not in st.session_state:
    st.session_state.raw_orientation_output = ""


# --- Helper Functions ---
def refresh_device_data(exe_path):
    """
    Calls all the logic functions to get a fresh snapshot of device data.
    """
    with st.spinner("Scanning for connected devices and info..."):
        devices, errors = logic.get_connected_devices(exe_path)
        st.session_state.devices = devices
        st.session_state.scan_errors = errors
        
        if devices:
            ghz_config, err = logic.get_6_5ghz_config(exe_path)
            if err: st.session_state.scan_errors += f"\n{err}"
            st.session_state.ghz_config = ghz_config
            
            keys, err = logic.get_public_key(exe_path)
            if err: st.session_state.scan_errors += f"\n{err}"
            st.session_state.public_keys = keys

            sessions, err = logic.list_sessions(exe_path)
            if err: st.session_state.scan_errors += f"\n{err}"
            st.session_state.sessions = sessions
            
    st.rerun()


# --- Main App UI ---
st.title("📡 Catapult Device Diagnostic Tool")
st.write("A tool to help support staff diagnose and configure S7 devices.")

# --- Configuration Section ---
with st.expander("Configuration and Settings"):
    st.subheader("Executable Paths")
    
    # Path for ConfigDevices.exe
    exe_path_default = r"C:\Users\Alex Lowthorpe\Desktop\Support Streamlit App\ConfigDevices.exe"
    exe_path = st.text_input("Path to ConfigDevices.exe", value=exe_path_default)

    # Path for viewer.exe
    viewer_exe_default = r"C:\Users\Alex Lowthorpe\Desktop\Support Streamlit App\viewer.exe"
    viewer_exe_path = st.text_input("Path to viewer.exe", value=viewer_exe_default)

    st.subheader("Download Settings")
    # Path for Session Downloads
    download_folder_default = r"C:\Users\Alex Lowthorpe\Desktop\Catapult_Downloads"
    download_folder = st.text_input("Session Download Folder", value=download_folder_default)


# --- Main TABS ---
tab_device_manager, tab_raw_viewer = st.tabs(
    ["Device Manager", "Raw File Viewer"]
)

# --- TAB 1: DEVICE MANAGER ---
with tab_device_manager:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.image("https://placehold.co/400x200/272727/FFFFFF?text=Device+Manager", width='stretch')
        st.button("Scan for Devices & Refresh All Data", on_click=refresh_device_data, args=(exe_path,), width='stretch', type="primary")

    with col2:
        st.subheader("Device Connection Status")
        if not st.session_state.devices and not st.session_state.scan_errors:
            st.info("Click 'Scan for Devices' to begin.")
        elif st.session_state.devices:
            st.success(f"Found {len(st.session_state.devices)} device(s).")
        else:
            st.warning("No devices found. Check connections and paths.")

        if st.session_state.scan_errors:
            st.error(f"Scan Errors:\n{st.session_state.scan_errors}", icon="⚠️")

    if st.session_state.devices:
        st.divider()
        st.header("Device Details")

        # Create tabs for each device
        device_tabs = st.tabs([f"Device ID: {d['id']}" for d in st.session_state.devices])
        
        for i, (device_tab, device) in enumerate(zip(device_tabs, st.session_state.devices)):
            with device_tab:
                st.subheader(f"Device: {device['id']} ({device['type']})")
                
                # --- Device Sub-Tabs ---
                tab_summary, tab_bits, tab_hr, tab_ghz, tab_key, tab_sessions = st.tabs(
                    ["Summary", "Bit Settings", "HR Config", "6.5 GHz Config", "Encryption Key", "Download Sessions"]
                )
                
                # --- Summary Tab ---
                with tab_summary:
                    st.metric("Device ID", device['id'])
                    st.metric("Firmware", device['firmware'])
                    st.metric("Device Type", device['type'])
                    st.code(f"Full Flags: {device['flags']}", language="text")

                # --- Bit Settings Tab ---
                with tab_bits:
                    st.subheader("Key Bit Status")
                    bit_df = pd.DataFrame([device['bit_status']])
                    st.dataframe(bit_df, width='stretch')
                    
                    with st.expander("Show All 64 Bits"):
                        all_bits_df = pd.DataFrame(device['all_bits'])
                        st.dataframe(all_bits_df, width='stretch', height=400)

                # --- HR Config Tab ---
                with tab_hr:
                    st.subheader("Heart Rate Configuration")
                    st.metric("Current HR Mode", device['hr_mode'])
                    
                    st.write("Set New HR Mode:")
                    hr_mode_choice = st.selectbox(
                        "Select HR Mode",
                        ["Polar Strap", "Integrated HR", "Bluetooth HR"],
                        key=f"hr_select_{device['id']}"
                    )
                    
                    if st.button(f"Apply HR Setting to Device {device['id']}", key=f"hr_btn_{device['id']}"):
                        with st.spinner(f"Setting {hr_mode_choice} on device {device['id']}..."):
                            log = logic.set_hr_mode(exe_path, hr_mode_choice)
                            st.code(log, language="log")
                            # Refresh data to show new mode
                            refresh_device_data(exe_path)

                # --- 6.5 GHz Config Tab ---
                with tab_ghz:
                    st.subheader("6.5 GHz Configuration")
                    device_ghz_config = next((item for item in st.session_state.ghz_config if item["id"] == device["id"]), None)
                    
                    if device_ghz_config:
                        st.metric("Current Config", device_ghz_config['config_type'])
                        st.code(device_ghz_config['raw'], language="text")
                    else:
                        st.warning("Could not find 6.5 GHz config for this device.")

                    st.write("Set New 6.5 GHz Config:")
                    col_def, col_alt = st.columns(2)
                    if col_def.button(f"Set to Default", key=f"ghz_def_{device['id']}"):
                        with st.spinner("Setting Default Config..."):
                            log = logic.set_6_5ghz_config(exe_path, "Default")
                            st.code(log, language="log")
                            refresh_device_data(exe_path)
                    
                    if col_alt.button(f"Set to Alternative", key=f"ghz_alt_{device['id']}"):
                        with st.spinner("Setting Alternative Config..."):
                            log = logic.set_6_5ghz_config(exe_path, "Alternative")
                            st.code(log, language="log")
                            refresh_device_data(exe_path)

                # --- Encryption Key Tab ---
                with tab_key:
                    st.subheader("Encryption Key")
                    device_key = next((item for item in st.session_state.public_keys if item["id"] == device["id"]), None)
                    
                    if device_key:
                        st.text_input("Public Key Hash", value=device_key['key_hash'], disabled=True)
                    else:
                        st.warning("Could not find public key for this device.")

                # --- Download Sessions Tab ---
                with tab_sessions:
                    st.subheader("Download Device Sessions")
                    device_sessions = st.session_state.sessions.get(device['id'], [])
                    
                    if not device_sessions:
                        st.warning("No sessions found for this device.")
                    else:
                        st.write(f"Found {len(device_sessions)} sessions.")
                        
                        # Use st.data_editor to create a selectable table
                        sessions_df = pd.DataFrame(device_sessions)
                        # Reorder columns to put 'Select' first
                        cols = ['Select', 'num', 'length', 'duration', 'time']
                        sessions_df = sessions_df[cols]
                        
                        edited_df = st.data_editor(
                            sessions_df,
                            key=f"session_editor_{device['id']}",
                            disabled=['num', 'length', 'duration', 'time'],
                            width='stretch',
                            height=400
                        )
                        
                        selected_sessions = edited_df[edited_df['Select'] == True]
                        
                        if st.button(f"Download Selected Sessions ({len(selected_sessions)})", key=f"dl_btn_{device['id']}"):
                            if selected_sessions.empty:
                                st.warning("No sessions selected.")
                            else:
                                session_nums_to_dl = selected_sessions['num'].tolist()
                                device_download_path = os.path.join(download_folder, device['id'])
                                
                                st.info(f"Downloading {len(session_nums_to_dl)} sessions to:\n{device_download_path}")
                                with st.spinner("Downloading..."):
                                    log = logic.download_sessions(exe_path, device['id'], session_nums_to_dl, device_download_path)
                                    st.code(log, language="log")

# --- TAB 2: RAW FILE VIEWER ---
with tab_raw_viewer:
    st.header("Raw File Viewer")
    st.write("Upload a `.raw` session file to analyze its contents.")
    
    uploaded_file = st.file_uploader("Upload a .raw file", type=["raw"])
    
    if uploaded_file is not None:
        if st.button("Run Analysis on File"):
            # --- NEW FILE HANDLING LOGIC ---
            # Get the directory where viewer.exe lives
            viewer_dir = os.path.dirname(viewer_exe_path)
            # Create the full path for the temporary file, using the *original* name
            temp_file_path = os.path.join(viewer_dir, uploaded_file.name)
            
            # Write the uploaded content to this new path
            try:
                with open(temp_file_path, "wb") as f:
                    f.write(uploaded_file.getvalue())
                st.info(f"File saved to: {temp_file_path}")
            except Exception as e:
                st.error(f"Failed to save temporary file: {e}")
                st.stop()
            # --- END NEW FILE HANDLING LOGIC ---

            
            # Run Debug Analysis
            with st.spinner("Running debug analysis (-d)..."):
                # Pass just the original filename, logic handles the rest
                success_d, out_d, err_d = logic.run_raw_file_viewer(viewer_exe_path, uploaded_file.name, "-d")
                if success_d:
                    st.session_state.raw_debug_output = out_d
                else:
                    st.session_state.raw_debug_output = f"Error running -d:\n{out_d}" # Show output even on error

            # Run Orientation Analysis
            with st.spinner("Running orientation analysis (-R)..."):
                # Pass just the original filename, logic handles the rest
                success_r, out_r, err_r = logic.run_raw_file_viewer(viewer_exe_path, uploaded_file.name, "-R")
                if success_r:
                    st.session_state.raw_orientation_output = out_r
                else:
                    st.session_state.raw_orientation_output = f"Error running -R:\n{out_r}" # Show output even on error
            
            # Clean up the temporary file
            try:
                os.remove(temp_file_path)
                st.info(f"Temporary file '{temp_file_path}' removed.")
            except Exception as e:
                st.warning(f"Could not remove temporary file: {e}")
            
            st.success("Analysis complete!")
            st.rerun() # Rerun to update tabs with new data

    # --- Display Analysis Results in Sub-Tabs ---
    if st.session_state.raw_debug_output or st.session_state.raw_orientation_output:
        
        tab_battery, tab_orientation, tab_debug_log = st.tabs(
            ["Battery Degradation", "Device Orientation", "Raw Debug Log"]
        )

        # --- Battery Degradation Tab ---
        with tab_battery:
            st.subheader("Battery Degradation Analysis")
            if not st.session_state.raw_debug_output:
                st.warning("No debug output found to analyze.")
            elif st.session_state.raw_debug_output.startswith("Error"):
                st.error("Could not analyze battery. Raw file viewer returned an error:")
                st.code(st.session_state.raw_debug_output, language="log")
            else:
                summary, data_points = logic.parse_debug_data(st.session_state.raw_debug_output)
                
                if "error" in summary:
                    st.error(summary['error'])
                elif not data_points:
                    st.warning("No battery data points found in the debug log.")
                else:
                    st.subheader("Summary")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Turn On %", summary['first_reading'])
                    col2.metric("Turn Off %", summary['last_reading'])
                    col3.metric("Time Elapsed (HH:MM)", summary['time_elapsed_str'])
                    col4.metric("Total % Drop", summary['percent_drop'])
                    
                    st.subheader("Battery % over Time (minutes)")
                    # Convert to DataFrame for charting
                    chart_df = pd.DataFrame(data_points)
                    # Create Time (minutes) column for a more readable X-axis
                    chart_df["Time (minutes)"] = chart_df["Time (s)"] / 60
                    chart_df = chart_df.set_index("Time (minutes)")
                    st.line_chart(chart_df["Battery %"])
                    
                    with st.expander("Show Raw Battery Data"):
                        st.dataframe(chart_df, width='stretch')

        # --- Device Orientation Tab ---
        with tab_orientation:
            st.subheader("Device Orientation Analysis")
            if not st.session_state.raw_orientation_output:
                st.warning("No orientation output found to analyze.")
            elif st.session_state.raw_orientation_output.startswith("Error"):
                st.error("Could not analyze orientation. Raw file viewer returned an error:")
                st.code(st.session_state.raw_orientation_output, language="log")
            else:
                orientation_str, counts, correct_pct = logic.parse_orientation_data(st.session_state.raw_orientation_output)
                
                if not orientation_str:
                    st.error("Could not parse orientation data from output.")
                    st.code(st.session_state.raw_orientation_output, language="text")
                else:
                    st.metric("Correct Orientation (Okay)", f"{correct_pct:.2f}%")
                    
                    # Create a DataFrame for the counts
                    counts_df = pd.DataFrame(
                        list(counts.items()), 
                        columns=['Orientation', 'Readings']
                    )
                    
                    # Calculate percentage for the pie chart
                    if counts_df['Readings'].sum() > 0:
                        counts_df['percent'] = (counts_df['Readings'] / counts_df['Readings'].sum())
                    else:
                        counts_df['percent'] = 0.0

                    # --- NEW PIE CHART VISUAL ---
                    st.subheader("Orientation Proportions")
                    
                    base = alt.Chart(counts_df).encode(
                       theta=alt.Theta("Readings:Q", stack=True)
                    ).properties(
                       title="Orientation Proportions"
                    )
                    
                    pie = base.mark_arc(outerRadius=120).encode(
                        color=alt.Color("Orientation:N"),
                        order=alt.Order("Readings:Q", sort="descending"),
                        tooltip=["Orientation", "Readings", alt.Tooltip("percent", format=".1%")]
                    )
                    
                    text = base.mark_text(radius=140).encode(
                        text=alt.Text("percent", format=".1%"),
                        order=alt.Order("Readings:Q", sort="descending"),
                        color=alt.value("black")
                    )
                    
                    chart = pie + text
                    # --- THIS IS THE FIX ---
                    st.altair_chart(chart, use_container_width=True) # Changed from width='stretch'
                    # --- END THE FIX ---
                    
                    with st.expander("Show Orientation Data Table"):
                        # Show the original df without the 'percent' column
                        st.dataframe(counts_df[['Orientation', 'Readings']], width='stretch')
                    
                    with st.expander("Show Raw Orientation String"):
                        st.code(orientation_str, language="text")

        # --- Raw Debug Log Tab ---
        with tab_debug_log:
            st.subheader("Raw Debug Log (-d)")
            if not st.session_state.raw_debug_output:
                st.warning("No debug output found.")
            else:
                st.code(st.session_state.raw_debug_output, language="log")

