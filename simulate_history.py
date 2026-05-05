import json
import datetime
import random
from pathlib import Path

DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "history.json"

def simulate_history():
    if not HISTORY_FILE.exists():
        print("No history.json found.")
        return
        
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        history = json.load(f)
        
    today = datetime.date.today()
    seven_days_ago = (today - datetime.timedelta(days=7)).isoformat()
    today_iso = today.isoformat()
    
    modified_count = 0
    for name, data in history.items():
        if today_iso in data["stars_history"]:
            current_stars = data["stars_history"][today_iso]
            # Simulate that the repo had fewer stars 7 days ago
            # Random growth between 10 and 1000
            growth = random.randint(10, 1000)
            past_stars = max(0, current_stars - growth)
            
            data["stars_history"][seven_days_ago] = past_stars
            modified_count += 1
            
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
        
    print(f"Simulated historical data for {modified_count} repos.")

if __name__ == "__main__":
    simulate_history()
