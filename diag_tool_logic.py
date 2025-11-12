import subprocess
import re
import os
import datetime
from typing import List, Dict, Any, Tuple

# --- REGEX PATTERNS ---
# Pattern for the main summary line
SUMMARY_PATTERN = re.compile(
    r"ID:(?P<id>\d+),"
    r"Family=(?P<type>.*?)/.*?,.*?"
    r"Ver (?P<firmware>[\w\.\+a-fA-F0-9]+),.*?"
    r"Flags=(?P<flags>0x[a-fA-F0-9]+)",
    re.IGNORECASE
)

# Pattern for 6.5 GHz config
GSP_PATTERN = re.compile(
    r"ID:(?P<id>\d+),.*?"
    r"txCode=(?P<tx>\d+),rxCode=(?P<rx>\d+)",
    re.IGNORECASE
)

# Pattern for public key
GPK_PATTERN = re.compile(
    r"ID:(?P<id>\d+), Public Key Hash=(?P<key_hash>[a-fA-F0-9]+)",
    re.IGNORECASE
)

# Pattern for session info start
SI_START_PATTERN = re.compile(r"Id:(?P<id>\d+) Total Sessions:(?P<total>\d+)", re.IGNORECASE)

# Pattern for individual session lines
SI_SESSION_PATTERN = re.compile(
    r"Session (?P<num>\d+): length=(?P<length>\d+),Duration=(?P<duration>\d+) secs,createTime (?P<time>.*?) UTC",
    re.IGNORECASE
)

# Pattern for orientation data line
ORIENTATION_PATTERN = re.compile(r"^[\+ru\.]+$")

# Pattern for battery debug data
BATTERY_PATTERN = re.compile(
    r"^\s*[a-fA-F0-9]+\s+(?P<time_s>[\d\.]+)\s+DATA:\s+Battery=(?P<voltage>[\d\.]+)V,\s+(?P<percent>\d+)%",
    re.IGNORECASE | re.MULTILINE
)

# --- HELPER FUNCTIONS ---

def run_command(exe_path: str, args: List[str], cwd: str = None) -> Tuple[bool, str, str]:
    """
    Runs the ConfigDevices.exe command, which is interactive.
    It expects a "press any key" prompt, so we send a newline.
    """
    if not os.path.exists(exe_path):
        return False, "", f"Error: ConfigDevices.exe not found at '{exe_path}'"

    command = [exe_path] + args
    
    try:
        # Use Popen for interactive communication
        process = subprocess.Popen(
            command,
            cwd=cwd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore'
        )
        
        # Send a newline character to "press any key"
        # Communicate handles sending stdin and capturing stdout/stderr
        stdout_data, stderr_data = process.communicate(input='\n', timeout=10)
        
        if process.returncode != 0 and not stdout_data:
             # If it failed and there's no stdout, return the error
             return False, "", stderr_data or "Command failed with no output."
        
        # Success, return the output
        return True, stdout_data, stderr_data

    except subprocess.TimeoutExpired:
        process.kill()
        return False, "", "Error: The command timed out. The device may be unresponsive."
    except FileNotFoundError:
        return False, "", f"Error: Executable not found at '{exe_path}'. Please check the path."
    except Exception as e:
        return False, "", f"An unexpected error occurred: {str(e)}"

# --- RAW FILE VIEWER FUNCTIONS ---
def run_raw_file_viewer(viewer_exe_path: str, file_name: str, flag: str) -> Tuple[bool, str, str]:
    """
    Runs the viewer.exe command.
    'file_name' is just the name of the file (e.g., "{None} ... .raw"),
    which is assumed to exist in the same directory as viewer_exe_path.
    """
    # --- New Logging ---
    print("\n==============================")
    print(f"--- DEBUG: run_raw_file_viewer (flag: {flag}) ---")
    print("==============================")
    
    if not os.path.exists(viewer_exe_path):
        print(f"--- DEBUG ERROR: viewer.exe not found at path: {viewer_exe_path}")
        print("==============================\n")
        return False, "", f"Error: viewer.exe not found at '{viewer_exe_path}'"
    print(f"--- DEBUG: viewer.exe found at: {viewer_exe_path}")
        
    # Get the directory of the viewer.exe
    viewer_dir = os.path.dirname(viewer_exe_path)
    print(f"--- DEBUG: viewer.exe directory (cwd): {viewer_dir}")
    
    # Check if the target file exists in that directory
    full_file_path = os.path.join(viewer_dir, file_name)
    if not os.path.exists(full_file_path):
        print(f"--- DEBUG ERROR: Raw file not found at expected path: {full_file_path}")
        print("==============================\n")
        return False, "", f"Error: Raw file not found at '{full_file_path}'"
    print(f"--- DEBUG: Raw file found at: {full_file_path}")

    # The command now uses just the filename, as CWD is set
    command = [viewer_exe_path, flag, file_name] 
    print(f"--- DEBUG: Executing command: {' '.join(command)}")
    
    try:
        result = subprocess.run(
            command,
            # capture_output=True, # <-- ERROR: Cannot use with stderr=STDOUT
            stdout=subprocess.PIPE,     # <-- FIX: Capture stdout
            stderr=subprocess.STDOUT, # FIX: Combine stderr into stdout
            text=True,
            encoding='utf-8',
            errors='ignore',
            cwd=viewer_dir # Run from the viewer's directory
        )
        
        # --- New Logging ---
        print(f"--- DEBUG: Command return code: {result.returncode}")
        print(f"--- DEBUG: Raw combined output (stdout+stderr):\n---\n{result.stdout}\n---")

        # result.stdout now contains combined output
        # Check return code to determine success
        if result.returncode != 0:
            # Command failed, return False and the error output
            # If stdout is empty, provide a more helpful error
            error_msg = result.stdout or f"Command failed with return code {result.returncode} and no output."
            print(f"--- DEBUG: Command FAILED. Returning error message: {error_msg}")
            print("==============================\n")
            return False, error_msg, ""
        
        # Command succeeded
        print("--- DEBUG: Command SUCCEEDED.")
        print("==============================\n")
        return True, result.stdout, ""
        
    except FileNotFoundError:
        print(f"--- DEBUG CRITICAL ERROR: FileNotFoundError. Executable not found at '{viewer_exe_path}'.")
        print("==============================\n")
        return False, "", f"Error: Executable not found at '{viewer_exe_path}'. Please check the path."
    except Exception as e:
        print(f"--- DEBUG CRITICAL ERROR: An unexpected exception occurred: {str(e)}")
        print("==============================\n")
        return False, "", f"An unexpected error occurred: {str(e)}"

def parse_orientation_data(raw_output: str) -> Tuple[str, Dict[str, int], float]:
    """
    Parses the raw output from the -R flag to find the orientation string.
    """
    # Debug logging to the console (PowerShell/cmd window)
    print("\n==============================")
    print("--- DEBUG: parse_orientation_data ---")
    print("==============================")
    print(f"Received Raw Output:\n---\n{raw_output}\n---")
    
    try:
        orientation_string = ""
        lines = [line.strip() for line in raw_output.splitlines() if line.strip()]
        print(f"Found Non-Empty Lines:\n{lines}")

        # Scan in reverse to find the first line that matches the regex
        print(f"Using Regex: {ORIENTATION_PATTERN.pattern}")
        for line in reversed(lines):
            if ORIENTATION_PATTERN.match(line):
                orientation_string = line
                print(f"--- DEBUG: Found Match: {line} ---")
                break

        if not orientation_string:
            print("--- DEBUG: No orientation string found. ---")
            print("==============================\n")
            return "", {}, 0.0

        total_readings = len(orientation_string)
        counts = {
            'Okay (+)': orientation_string.count('+'),
            'Reversed (r)': orientation_string.count('r'),
            'Upside Down (u)': orientation_string.count('u'),
            'Flat (.)': orientation_string.count('.'),
        }
        
        # Calculate "correct" percentage (Okay)
        correct_percentage = (counts['Okay (+)'] / total_readings) * 100 if total_readings > 0 else 0
        
        print("--- DEBUG: Parse Successful ---")
        print("==============================\n")
        return orientation_string, counts, correct_percentage

    except Exception as e:
        print(f"--- DEBUG: Error during parsing: {e} ---")
        print("==============================\n")
        return "", {}, 0.0

def parse_debug_data(raw_output: str) -> Tuple[Dict[str, Any], List[Dict[str, float]]]:
    """
    Parses the raw output from the -d flag to find battery degradation.
    """
    summary = {
        "first_reading": "N/A",
        "last_reading": "N/A",
        "time_elapsed_str": "N/A",
        "percent_drop": "N/A"
    }
    all_data_points = []
    
    try:
        matches = list(BATTERY_PATTERN.finditer(raw_output))
        
        if not matches:
            return summary, all_data_points

        # Store all data points for the graph
        all_data_points = [
            {
                "Time (s)": float(m.group('time_s')),
                "Voltage (V)": float(m.group('voltage')),
                "Battery %": float(m.group('percent'))
            } for m in matches
        ]

        # Get first and last data points
        first_match = matches[0]
        last_match = matches[-1]

        first_time_s = float(first_match.group('time_s'))
        first_percent = float(first_match.group('percent'))
        
        last_time_s = float(last_match.group('time_s'))
        last_percent = float(last_match.group('percent'))

        # Format summary
        summary['first_reading'] = f"{first_percent:.0f}%"
        summary['last_reading'] = f"{last_percent:.0f}%"
        
        # Calculate time elapsed and format as HH:MM
        time_delta_seconds = last_time_s - first_time_s
        total_minutes = int(time_delta_seconds // 60)
        total_hours = total_minutes // 60
        remaining_minutes = total_minutes % 60
        summary['time_elapsed_str'] = f"{total_hours:02}:{remaining_minutes:02}"


        # Calculate percentage drop
        percent_drop_val = first_percent - last_percent
        summary['percent_drop'] = f"{percent_drop_val:.0f}%"

        return summary, all_data_points

    except Exception as e:
        summary['error'] = f"Error parsing debug data: {str(e)}"
        return summary, all_data_points


# --- TASK 1: GET CONNECTED DEVICES ---

def get_connected_devices(exe_path: str) -> Tuple[List[Dict[str, Any]], str]:
    """
    Runs ConfigDevices.exe without args to get the summary.
    Parses the summary line for all connected devices.
    """
    success, stdout, stderr = run_command(exe_path, [])
    
    if not success:
        return [], stderr or "Failed to run ConfigDevices.exe"

    devices = []
    error_log = []
    
    for line in stdout.splitlines():
        match = SUMMARY_PATTERN.search(line)
        if match:
            data = match.groupdict()
            # Clean up ID by removing leading zeros
            data['id'] = data['id'].lstrip('0')
            # Add bit setting info
            data['bit_status'], data['all_bits'] = get_bit_status(data['flags'])
            # Add current HR mode
            data['hr_mode'] = get_current_hr_mode(data['bit_status'])
            devices.append(data)
        elif "ID:" in line:
            error_log.append(f"Failed to parse line: {line}")

    if not devices and not error_log:
        return [], "No devices found. Check connection."
        
    return devices, "\n".join(error_log)

# --- TASK 2: PARSE BIT SETTINGS ---

def get_bit_status(flags_hex: str) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """
    Parses the Flags=0x... hex string into individual bit status.
    """
    try:
        # Remove '0x' and convert hex string to a 64-bit integer
        flags_int = int(flags_hex.replace('0x', ''), 16)
    except (ValueError, TypeError):
        return {}, []

    # Define the bits we care about
    specific_bits_map = {
        3: "Enables HR",
        24: "Double button to turn off",
        28: "Enables ECH heartrate pickup",
        30: "Enables BLE HR monitoring"
    }

    specific_bits_status = {}
    all_bits_table = []

    # Check all 64 bits
    for i in range(64):
        # Use bitwise AND to check if the i-th bit is set
        is_set = (flags_int >> i) & 1
        status_str = "ON" if is_set else "OFF"
        
        description = specific_bits_map.get(i, f"Bit {i}")
        
        # Add to the table for all bits
        all_bits_table.append({"Bit": i, "Status": status_str, "Description": description})
        
        # If this is one of the specific bits, save its status
        if i in specific_bits_map:
            specific_bits_status[str(i)] = status_str

    return specific_bits_status, all_bits_table

def get_current_hr_mode(bit_status: Dict[str, str]) -> str:
    """
    Determines the current HR mode based on bit settings.
    """
    try:
        bit_3 = bit_status.get('3')
        bit_28 = bit_status.get('28')
        bit_30 = bit_status.get('30')

        if bit_3 == "ON" and bit_28 == "OFF" and bit_30 == "OFF":
            return "Polar Strap"
        elif bit_3 == "ON" and bit_28 == "ON" and bit_30 == "OFF":
            return "Integrated HR"
        elif bit_3 == "ON" and bit_28 == "OFF" and bit_30 == "ON":
            return "Bluetooth HR"
        else:
            return "Unknown/Custom"
    except Exception:
        return "Error"

# --- TASK 3: SET HR MODE ---

def set_hr_mode(exe_path: str, mode: str) -> str:
    """
    Runs a series of ConfigDevices.exe commands to set a specific HR mode.
    """
    commands = []
    if mode == "Polar Strap":
        # bit 3 ON, bit 28 OFF, bit 30 OFF
        commands = [
            (exe_path, ["-ds", "3"]),
            (exe_path, ["-dc", "28"]),
            (exe_path, ["-dc", "30"]),
        ]
    elif mode == "Integrated HR":
        # bit 3 ON, bit 28 ON, bit 30 OFF
        commands = [
            (exe_path, ["-ds", "3"]),
            (exe_path, ["-ds", "28"]),
            (exe_path, ["-dc", "30"]),
        ]
    elif mode == "Bluetooth HR":
        # bit 3 ON, bit 30 ON, bit 28 OFF
        commands = [
            (exe_path, ["-ds", "3"]),
            (exe_path, ["-ds", "30"]),
            (exe_path, ["-dc", "28"]),
        ]
    else:
        return "Invalid mode selected."

    output_log = [f"--- Setting HR Mode to: {mode} ---"]
    
    for exe, args in commands:
        success, stdout, stderr = run_command(exe, args)
        if success:
            output_log.append(f"SUCCESS: {' '.join(args)}\n{stdout}")
        else:
            output_log.append(f"ERROR: {' '.join(args)}\n{stderr}")
            
    output_log.append("--- HR Mode setting complete. ---")
    return "\n".join(output_log)

# --- TASK 4: 6.5 GHZ CONFIGURATION ---

def get_6_5ghz_config(exe_path: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Runs ConfigDevices.exe -gsp to get the 6.5 GHz config.
    """
    success, stdout, stderr = run_command(exe_path, ["-gsp"])
    
    if not success:
        return [], stderr or "Failed to run -gsp command."

    configs = []
    for line in stdout.splitlines():
        match = GSP_PATTERN.search(line)
        if match:
            data = match.groupdict()
            tx = data['tx']
            rx = data['rx']
            
            if tx == '9' and rx == '9':
                config_type = "Default (tx=9, rx=9)"
            elif tx == '3' and rx == '3':
                config_type = "Alternative (tx=3, rx=3)"
            else:
                config_type = f"Unknown (tx={tx}, rx={rx})"
            
            configs.append({
                "id": data['id'].lstrip('0'),
                "config_type": config_type,
                "raw": line.strip()
            })
            
    return configs, ""

def set_6_5ghz_config(exe_path: str, mode: str) -> str:
    """
    Runs the command to set the 6.5 GHz configuration.
    """
    args = []
    if mode == "Default":
        args = ["-ssp", "5", "2", "36", "1", "9", "9", "0", "2", "3", "4161", "181", "0x1F1F1F1F"]
    elif mode == "Alternative":
        args = ["-ssp", "5", "1", "36", "1", "3", "3", "0", "2", "3", "4161", "181", "0x1F1F1F1F"]
    else:
        return "Invalid mode selected."

    output_log = [f"--- Setting 6.5 GHz Config to: {mode} ---"]
    success, stdout, stderr = run_command(exe_path, args)
    
    if success:
        output_log.append(f"SUCCESS: {' '.join(args)}\n{stdout}")
    else:
        output_log.append(f"ERROR: {' '.join(args)}\n{stderr}")
            
    output_log.append("--- 6.5 GHz Config setting complete. ---")
    return "\n".join(output_log)


# --- TASK 5: GET ENCRYPTION KEY ---

def get_public_key(exe_path: str) -> Tuple[List[Dict[str, str]], str]:
    """
    Runs ConfigDevices.exe -gpk to get the public key hash.
    """
    success, stdout, stderr = run_command(exe_path, ["-gpk"])
    
    if not success:
        return [], stderr or "Failed to run -gpk command."

    keys = []
    for line in stdout.splitlines():
        match = GPK_PATTERN.search(line)
        if match:
            data = match.groupdict()
            keys.append({
                "id": data['id'].lstrip('0'), 
                "key_hash": data['key_hash']
            })
            
    return keys, ""

# --- TASK 6: LIST SESSIONS ---

def list_sessions(exe_path: str) -> Tuple[Dict[str, List[Dict[str, Any]]], str]:
    """
    Runs ConfigDevices.exe -si to get all session info.
    """
    success, stdout, stderr = run_command(exe_path, ["-si"])
    
    if not success:
        return {}, stderr or "Failed to run -si command."

    sessions_by_device = {}
    current_device_id = None
    
    for line in stdout.splitlines():
        start_match = SI_START_PATTERN.search(line)
        session_match = SI_SESSION_PATTERN.search(line)
        
        if start_match:
            current_device_id = start_match.group('id').lstrip('0')
            if current_device_id not in sessions_by_device:
                sessions_by_device[current_device_id] = []
        
        elif session_match and current_device_id:
            data = session_match.groupdict()
            # Add a 'Select' column for the st.data_editor
            data['Select'] = False
            sessions_by_device[current_device_id].append(data)
            
    return sessions_by_device, ""

# --- TASK 7: DOWNLOAD SESSIONS (REAL) ---

def download_sessions(exe_path: str, device_id: str, session_nums: List[str], path: str) -> str:
    """
    Runs ConfigDevices.exe -id <id> -sd <num> to download sessions.
    Runs the command *from* the specified download path.
    """
    if not os.path.exists(path):
        try:
            os.makedirs(path)
        except OSError as e:
            return f"Error creating download directory: {e}"

    log = []
    for num in session_nums:
        # Use -id to target the specific device
        args = ["-id", device_id, "-sd", str(num)]
        log.append(f"--- Downloading Session {num} for Device {device_id} to {path} ---")
        
        # Run the command with cwd=path
        success, stdout, stderr = run_command(exe_path, args, cwd=path)
        
        if success:
            log.append(f"SUCCESS: {stdout}")
        else:
            log.append(f"ERROR: {stderr}")
            
    log.append("--- Download complete. ---")
    return "\n".join(log)

