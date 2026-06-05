"""
Runner script to launch the Golf Tournament Live Scoring App.
Checks for streamlit and runs it.
"""
import os
import sys
import subprocess

def main():
    # Make sure we are in the workspace root or golf_scoring directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(current_dir, "app.py")
    
    if not os.path.exists(app_path):
        print(f"Error: app.py not found at {app_path}")
        sys.exit(1)
        
    print("Launching GolfScore Live...")
    print("Make sure you have streamlit installed. If not, run: pip install streamlit")
    
    try:
        # Run streamlit as a python module to avoid PATH issues on Windows
        subprocess.run([sys.executable, "-m", "streamlit", "run", app_path], check=True)
    except KeyboardInterrupt:
        print("\nStopping GolfScore Live. See you next round! 🏌️")
    except Exception as e:
        print(f"Error starting Streamlit: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
