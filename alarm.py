import subprocess
import time
import tkinter as tk
import configparser
import os
import winsound
import threading
import pystray
from PIL import Image, ImageDraw
from datetime import datetime
import sys
import logging

# Configure logging to file instead of console
logging.basicConfig(filename='server_alarm.log', level=logging.INFO, 
                   format='%(asctime)s - %(message)s')

# Global variables to control the monitoring and status
monitoring_active = True
server_status = "Unknown"
last_ping_time = "Never"
current_sound_stop_event = None

# Function to load configuration
def load_config():
    """Load configuration from config.ini file"""
    config = configparser.ConfigParser()
    
    # Get the directory where the executable/script is located
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        application_path = os.path.dirname(sys.executable)
    else:
        # Running as script
        application_path = os.path.dirname(__file__)
    
    config_path = os.path.join(application_path, 'config.ini')
    config.read(config_path)
    return config

def create_tray_icon():
    """Create a simple icon for the system tray"""
    # Create a simple icon (red circle for offline, green for online)
    color = (87, 255, 87) if server_status == "Online" else (255, 87, 87)
    image = Image.new('RGB', (64, 64), color=color)
    dc = ImageDraw.Draw(image)
    dc.ellipse([16, 16, 48, 48], fill=(255, 255, 255))
    return image

def update_tray_icon(icon):
    """Update the tray icon with current status"""
    if icon:
        icon.icon = create_tray_icon()
        icon.title = f"Server Alarm - {get_status_text()}"

def get_status_text():
    """Get current status text for display"""
    monitoring_text = "ON" if monitoring_active else "OFF"
    return f"Monitoring: {monitoring_text} | Server: {server_status} | Last: {last_ping_time}"

def on_quit(icon, item):
    """Quit the application"""
    global monitoring_active
    monitoring_active = False
    icon.stop()

def on_stop_monitoring(icon, item):
    """Stop monitoring temporarily"""
    global monitoring_active
    monitoring_active = False
    update_tray_icon(icon)

def on_start_monitoring(icon, item):
    """Resume monitoring"""
    global monitoring_active
    monitoring_active = True
    # Start monitoring in a new thread
    monitor_thread = threading.Thread(target=ping_server, args=(icon,), daemon=True)
    monitor_thread.start()
    update_tray_icon(icon)

def on_test_alarm(icon, item):
    """Test the alarm system"""
    config = load_config()
    show_message_box(config)

def setup_tray():
    """Setup system tray icon"""
    image = create_tray_icon()
    
    menu = pystray.Menu(
        pystray.MenuItem("Server Alarm Monitor", None, enabled=False),
        pystray.MenuItem(get_status_text(), None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Stop Monitoring", on_stop_monitoring),
        pystray.MenuItem("Start Monitoring", on_start_monitoring),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Test Alarm", on_test_alarm),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit)
    )
    
    icon = pystray.Icon("server_alarm", image, f"Server Alarm - {get_status_text()}", menu)
    return icon

def show_message_box(config):
    """
    Displays a MsgBox,
    Always on top of other windows,
    Centered on the screen.
    """
    # Get values from config
    window_width = int(config.get('UI', 'window_width', fallback='500'))
    window_height = int(config.get('UI', 'window_height', fallback='250'))
    window_title = config.get('UI', 'window_title', fallback='Server Status')
    message_text = config.get('UI', 'message_text', fallback='SERVER IS UP!')
    background_color = config.get('UI', 'background_color', fallback='#1E1E1E')
    alert_color = config.get('UI', 'alert_color', fallback='#FF5F57')
    button_color = config.get('UI', 'button_color', fallback='#4CAF50')
    text_color = config.get('UI', 'text_color', fallback='white')

    font_family = config.get('UI', 'family', fallback='Arial')
    font_size = int(config.get('UI', 'size', fallback='24'))
    button_font_size = int(config.get('UI', 'button_size', fallback='16'))
    font_style = config.get('UI', 'style', fallback='bold')

    always_on_top = config.getboolean('UI', 'always_on_top', fallback=True)

    root = tk.Tk()
    root.title(window_title)

    # Make sure the message box is always on top
    if always_on_top:
        root.attributes("-topmost", True)

    # Set the size of the window and its position
    root.geometry(f"{window_width}x{window_height}")
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()

    # Calculate the position to center the window
    position_top = int(screen_height / 2 - window_height / 2)
    position_left = int(screen_width / 2 - window_width / 2)

    root.geometry(f"{window_width}x{window_height}+{position_left}+{position_top}")

    canvas = tk.Canvas(root,
                       width=window_width,
                       height=window_height,
                       bg=background_color,
                       bd=0,
                       highlightthickness=0)
    canvas.pack()

    canvas.create_rectangle(0, 0,
                            window_width, window_height,
                            fill=alert_color,
                            outline=alert_color)

    label = tk.Label(root,
                     text=message_text,
                     font=(font_family, font_size, font_style),
                     fg=text_color,
                     bg=alert_color)

    label.place(relx=0.5, rely=0.35, anchor="center")

    # Start playing sound if enabled
    sound_enabled = config.getboolean('Sound', 'enabled', fallback=True)
    sound_file = config.get('Sound', 'file', fallback='alarm.wav')

    stop_sound = threading.Event()

    if sound_enabled:
        sound_thread = threading.Thread(target=play_alarm_sound, args=(sound_file, stop_sound))
        sound_thread.daemon = True
        sound_thread.start()



    button = tk.Button(root, text="OK",
                       font=(font_family, button_font_size),
                       command= lambda: (stop_sound.set(), root.destroy()),
                       relief="flat",
                       bg=button_color,
                       fg=text_color,
                       padx=20, pady=10)

    button.place(relx=0.5, rely=0.6, anchor="center")

    root.mainloop()

def play_alarm_sound(sound_file, stop_event):
    """Play sound in loop until stop_event is set"""
    try:
        # Start playing in background, looping until stopped
        winsound.PlaySound(sound_file, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_LOOP)
        while not stop_event.wait(0.2):  # Check every 200ms if stop signal was given
            continue
    finally:
        # Stop any ongoing sound
        winsound.PlaySound(None, winsound.SND_ASYNC)

def ping_server(icon=None):
    """
    Periodically pings the server to check if it is up.
    If the server is up, shows a message box with the configured message.
    The server and ping interval are configured in the 'config.ini' file.
    """
    global monitoring_active, server_status, last_ping_time
    
    config = load_config()

    # Get server settings from config
    server = config.get('Server', 'hostname', fallback='game.project-epoch.net:3724')
    ping_interval = int(config.get('Server', 'ping_interval', fallback='5'))
    ping_count = config.get('Server', 'ping_count', fallback='1')

    while monitoring_active:
        if not monitoring_active:
            break
            
        # Update last ping time
        last_ping_time = datetime.now().strftime("%H:%M:%S")
            
        response = subprocess.run(
            ["ping", "-n", ping_count, server],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW
        )

        # Log to file instead of console to avoid command prompt flash
        logging.info(f"Pinging {server}... Response code: {response.returncode}")

        # Update server status
        if response.returncode == 0:
            server_status = "Online"
            if icon:
                update_tray_icon(icon)
            show_message_box(config)
            break
        else:
            server_status = "Offline"
            if icon:
                update_tray_icon(icon)
        
        time.sleep(ping_interval)  # Wait before retrying

if __name__ == "__main__":
    # Redirect stdout and stderr to suppress any console output
    if getattr(sys, 'frozen', False):
        sys.stdout = open(os.devnull, 'w')
        sys.stderr = open(os.devnull, 'w')
    
    # Setup system tray
    tray_icon = setup_tray()
    
    # Start monitoring in a separate thread
    monitor_thread = threading.Thread(target=ping_server, args=(tray_icon,), daemon=True)
    monitor_thread.start()
    
    # Run the tray icon (this blocks)
    tray_icon.run()