import requests
import json
import os
import time
import datetime
from pathlib import Path

# Configuration
DATA_DIR = Path("data")
HISTORY_FILE = DATA_DIR / "history.json"
README_FILE = Path("README.md")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
MAX_PAGES = 2 # Fetch up to 2 pages per query (100 per page) to stay within rate limits

# Search queries focused on AI Agent related repos
# 7 queries × 2 pages = 14 requests (within 30 req/min auth limit)
SEARCH_QUERIES = [
    "topic:ai-agent",
    "topic:ai-agents",
    "topic:llm-agent",
    "topic:agent-framework",
    "topic:autonomous-agents",
    "topic:mcp",
    "ai agent framework multi-agent",
]

def fetch_repos(query, per_page=100, max_pages=2):
    """Fetch repositories using GitHub Search API with retry on rate limit."""
    repos = {}
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"

    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/search/repositories?q={query}&sort=stars&order=desc&per_page={per_page}&page={page}"
        print(f"Fetching: {url}")
        
        # Retry up to 3 times on rate limit
        for attempt in range(3):
            response = requests.get(url, headers=headers)
            
            if response.status_code == 200:
                break
            elif response.status_code == 403:
                # Rate limited — wait and retry
                wait_time = 15 * (attempt + 1)
                print(f"  Rate limited. Waiting {wait_time}s before retry ({attempt + 1}/3)...")
                time.sleep(wait_time)
            else:
                print(f"Error fetching data: {response.status_code} - {response.text}")
                break
        else:
            print(f"  Skipping query after 3 retries.")
            break
        
        if response.status_code != 200:
            break
            
        data = response.json()
        items = data.get("items", [])
        if not items:
            break
            
        for item in items:
            repos[item["full_name"]] = {
                "name": item["full_name"],
                "stars": item["stargazers_count"],
                "url": item["html_url"],
                "description": item["description"]
            }
        
        # Delay between pages to avoid rate limiting
        time.sleep(2)
            
    return repos

def fetch_all_ai_repos():
    """Fetch repos for all queries and merge results."""
    all_repos = {}
    for i, query in enumerate(SEARCH_QUERIES):
        repos = fetch_repos(query, max_pages=MAX_PAGES)
        for name, data in repos.items():
            if name not in all_repos:
                all_repos[name] = data
        # Delay between queries to respect rate limits
        if i < len(SEARCH_QUERIES) - 1:
            print("  Waiting 6s before next query...")
            time.sleep(6)
    return all_repos

def load_history():
    """Load history from JSON file."""
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history):
    """Save history to JSON file."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)

def update_history(current_repos):
    """Update history with today's fetch."""
    history = load_history()
    today = datetime.date.today().isoformat()
    
    for name, data in current_repos.items():
        if name not in history:
            history[name] = {
                "name": data["name"],
                "url": data["url"],
                "description": data["description"],
                "stars_history": {}
            }
        
        # Always update metadata in case it changed
        history[name]["url"] = data["url"]
        history[name]["description"] = data["description"]
        
        # Record today's stars
        history[name]["stars_history"][today] = data["stars"]
        
    # Clean up old data (keep only last 14 days to prevent file from growing indefinitely)
    fourteen_days_ago = (datetime.date.today() - datetime.timedelta(days=14)).isoformat()
    for name in history:
        history[name]["stars_history"] = {
            date: stars for date, stars in history[name]["stars_history"].items()
            if date >= fourteen_days_ago
        }
        
    save_history(history)
    return history

def calculate_growth(history):
    """Calculate the star growth over the last 7 days."""
    today = datetime.date.today()
    target_past_date = today - datetime.timedelta(days=7)
    
    growth_data = []
    
    for name, repo_data in history.items():
        stars_history = repo_data.get("stars_history", {})
        if not stars_history:
            continue
            
        # Get today's stars (or the latest available)
        available_dates = sorted(stars_history.keys())
        latest_date = available_dates[-1]
        latest_stars = stars_history[latest_date]
        
        # Find the closest date to 7 days ago
        past_date = None
        for date_str in reversed(available_dates):
            date_obj = datetime.date.fromisoformat(date_str)
            if date_obj <= target_past_date:
                past_date = date_str
                break
                
        # If we couldn't find a date <= 7 days ago, use the oldest available date
        # provided it's at least 3 days old (to avoid noise from 1-2 day tracking)
        if not past_date:
            oldest_date = available_dates[0]
            oldest_date_obj = datetime.date.fromisoformat(oldest_date)
            if (datetime.date.fromisoformat(latest_date) - oldest_date_obj).days >= 3:
                past_date = oldest_date
            else:
                continue # Not enough history to calculate meaningful growth
                
        past_stars = stars_history[past_date]
        growth = latest_stars - past_stars
        
        growth_data.append({
            "name": name,
            "url": repo_data["url"],
            "description": repo_data["description"] or "",
            "latest_stars": latest_stars,
            "past_stars": past_stars,
            "growth": growth,
            "period_days": (datetime.date.fromisoformat(latest_date) - datetime.date.fromisoformat(past_date)).days
        })
        
    # Sort by growth descending
    growth_data.sort(key=lambda x: x["growth"], reverse=True)
    return growth_data

def generate_readme(top_repos):
    """Generate the README.md report."""
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    lines = [
        "# 🤖 Top AI Agent Repositories by Weekly Star Growth",
        "",
        f"This list tracks the top AI Agent related repositories on GitHub and ranks them by the number of stars gained over the last 7 days.",
        "",
        f"*Last updated: {now}*",
        "",
        "## Top 10 Fastest Growing AI Agent Repositories This Week",
        "",
        "| Rank | Repository | Description | Stars Gained | Total Stars |",
        "| :---: | :--- | :--- | :---: | :---: |"
    ]
    
    for i, repo in enumerate(top_repos[:10], 1):
        # Escape pipes in description for markdown table
        desc = repo['description'].replace('|', '&#124;').replace('\n', ' ') if repo['description'] else ''
        # Truncate long descriptions
        if len(desc) > 100:
            desc = desc[:97] + "..."
            
        row = f"| {i} | [{repo['name']}]({repo['url']}) | {desc} | +{repo['growth']:,} | {repo['latest_stars']:,} |"
        lines.append(row)
        
    lines.extend([
        "",
        "## How it works",
        "A GitHub Action runs daily to fetch the top AI Agent repositories (using topics like `ai-agent`, `llm-agent`, `agent-framework`, `mcp`, etc.) and stores their star counts. It then calculates the growth over the past 7 days to generate this list.",
    ])
    
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("README.md generated successfully.")

def main():
    print("Fetching AI repositories...")
    current_repos = fetch_all_ai_repos()
    print(f"Fetched {len(current_repos)} unique repositories.")
    
    print("Updating history...")
    history = update_history(current_repos)
    
    print("Calculating growth...")
    growth_data = calculate_growth(history)
    
    if growth_data:
        print("Generating report...")
        generate_readme(growth_data)
        
        print("\nTop 5 repos:")
        for r in growth_data[:5]:
            print(f"- {r['name']}: +{r['growth']} stars ({r['latest_stars']} total)")
    else:
        print("Not enough historical data to calculate growth yet.")
        print("Run the script again in a few days.")

if __name__ == "__main__":
    main()
