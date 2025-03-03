import schedule
import time
import subprocess
import sys
from datetime import datetime

# Funktionen zum Starten der einzelnen Prozesse
def start_backend():
    print(f"[{datetime.now()}] Starte Flask Backend...")
    subprocess.Popen(["sys.executable", "s3_backend.py"])

def scrape_pdfs():
    print(f"[{datetime.now()}] Starte PDF Scraping...")
    subprocess.run(["sys.executable", "s3_scrape_pdfs.py"])

def process_pdfs():
    print(f"[{datetime.now()}] Verarbeite PDF-Daten...")
    subprocess.run(["sys.executable", "s3_process_pdfs.py"])

# Backend starten
start_backend()

# Zeitplan für tägliche Aufgaben
schedule.every().day.at("03:00").do(scrape_pdfs)
schedule.every().day.at("03:30").do(process_pdfs)

print("Scheduler läuft und wartet auf geplante Aufgaben...")

# Dauerschleife, um den Scheduler am Laufen zu halten
while True:
    schedule.run_pending()
    time.sleep(60)  # Checkt jede Minute nach geplanten Aufgaben
