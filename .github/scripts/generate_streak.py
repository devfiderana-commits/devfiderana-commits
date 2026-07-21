"""
Generate a GitHub streak stats SVG using GitHub's GraphQL API.
Produces: assets/streak-stats.svg
Shows: Total Contributions | Current Streak | Longest Streak
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse as parse_date

USERNAME = os.environ["GH_USERNAME"]
TOKEN    = os.environ["GH_TOKEN"]

GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ── Fetch contribution data (last 365 days) ──────────────────────────────────
def fetch_contributions():
    end   = datetime.now(timezone.utc)
    start = end - timedelta(days=365)

    query = """
    query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
        createdAt
      }
    }
    """
    variables = {
        "login": USERNAME,
        "from":  start.isoformat(),
        "to":    end.isoformat(),
    }
    resp = requests.post(GRAPHQL_URL, headers=HEADERS,
                         json={"query": query, "variables": variables})
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")
    return data["data"]["user"]

# ── Calculate streaks ────────────────────────────────────────────────────────
def calculate_streaks(weeks):
    days = []
    for week in weeks:
        for day in week["contributionDays"]:
            days.append((day["date"], day["contributionCount"]))
    days.sort(key=lambda x: x[0])

    total        = sum(c for _, c in days)
    current      = 0
    longest      = 0
    streak       = 0
    today_str    = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    for date, count in reversed(days):
        if count > 0:
            streak += 1
            longest = max(longest, streak)
        else:
            if date not in (today_str, yesterday_str):
                break
            # allow today with no contributions yet (don't break streak)
            if date == today_str:
                continue
            break

    # current streak: walk from today backward
    current_streak = 0
    for date, count in reversed(days):
        if date > today_str:
            continue
        if count > 0:
            current_streak += 1
        else:
            if date == today_str:
                continue
            break
    current = current_streak

    # longest streak (full scan)
    best = cur = 0
    for _, count in days:
        if count > 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    longest = best

    return total, current, longest

# ── Build SVG ────────────────────────────────────────────────────────────────
def build_svg(total, current, longest):
    W, H = 780, 190
    pad  = 26

    # date range label
    end_dt   = datetime.now(timezone.utc)
    start_dt = end_dt - timedelta(days=365)
    date_range = f"{start_dt.strftime('%b %d, %Y')} – {end_dt.strftime('%b %d, %Y')}"

    col_w = (W - pad * 2) / 3
    def cx(i):  # center x of column i (0,1,2)
        return pad + col_w * i + col_w / 2

    def section(i, top_label, value, bottom_label, value_color="#FFFFFF"):
        x = cx(i)
        # divider lines
        dividers = ""
        if i > 0:
            lx = pad + col_w * i
            dividers = f'<line x1="{lx:.1f}" y1="30" x2="{lx:.1f}" y2="{H-30}" stroke="#00FFD130" stroke-width="1"/>'
        return f"""
{dividers}
<text x="{x:.1f}" y="55"  text-anchor="middle" fill="#8B949E" font-size="13" font-family="Segoe UI,sans-serif">{top_label}</text>
<text x="{x:.1f}" y="115" text-anchor="middle" fill="{value_color}" font-size="42" font-weight="bold" font-family="Segoe UI,sans-serif">{value}</text>
<text x="{x:.1f}" y="150" text-anchor="middle" fill="#8B949E" font-size="13" font-family="Segoe UI,sans-serif">{bottom_label}</text>
"""

    # streak fire emoji via text (unicode)
    fire = "🔥" if current > 0 else "❄️"
    lightning = "⚡"

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <defs>
    <linearGradient id="ringGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%"   stop-color="#00FFD1"/>
      <stop offset="100%" stop-color="#0077FF"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="{W}" height="{H}" rx="12" fill="#0D1117"/>

  <!-- Border -->
  <rect width="{W}" height="{H}" rx="12" fill="none" stroke="#00FFD1" stroke-width="1" stroke-opacity="0.4"/>

  <!-- Date range -->
  <text x="{W/2:.1f}" y="22" text-anchor="middle" fill="#8B949E" font-size="11"
        font-family="Segoe UI,sans-serif">{date_range}</text>

  <!-- Sections -->
  {section(0, "Total Contributions", f"{total:,}", "Contributions", "#FFFFFF")}
  {section(1, "Current Streak", f"{current} {fire}", "days", "#FF6B35")}
  {section(2, "Longest Streak", f"{longest} {lightning}", "days", "#00FFD1")}

  <!-- Bottom label -->
  <text x="{W/2:.1f}" y="{H-10:.1f}" text-anchor="middle" fill="#8B949E" font-size="10"
        font-family="Segoe UI,sans-serif">@{USERNAME} · GitHub Contributions</text>
</svg>"""
    return svg

# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    print(f"Fetching contributions for {USERNAME}…")
    user_data  = fetch_contributions()
    cal        = user_data["contributionsCollection"]["contributionCalendar"]
    weeks      = cal["weeks"]

    total, current, longest = calculate_streaks(weeks)
    print(f"  Total: {total}  |  Current streak: {current}  |  Longest: {longest}")

    svg = build_svg(total, current, longest)

    os.makedirs("assets", exist_ok=True)
    out = "assets/streak-stats.svg"
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  Written → {out}")

if __name__ == "__main__":
    main()
