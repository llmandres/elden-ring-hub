import sys
import os

# Add src to Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from er_save_manager.ui.gui import main as gui_main

def main():
    gui_main()

if __name__ == "__main__":
    main()
