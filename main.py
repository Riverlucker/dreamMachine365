import os
import sys

# Fügt den `dreammachine` Ordner zum Suchpfad hinzu, damit Python alle dortigen Module findet
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dreammachine'))

# Importiert und startet effektiv dreammachine/main.py
import main as dm_main

if __name__ == '__main__':
    dm_main.main()
