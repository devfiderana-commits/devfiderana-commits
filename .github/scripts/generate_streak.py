"""
Generate a GitHub streak stats SVG using GitHub's GraphQL API.
Produces: assets/streak-stats.svg
Shows: Total Contributions | Current Streak | Longest Streak

Fetches ALL contribution years so the longest streak is never
truncated by a 365-day window.
"""

import os
import requests
from datetime import datetime, date, timezone, timedelta

USERNAME = os.environ["GH_USERNAME"]
TOKEN    = os.environ["GH_TOKEN"]

GRAPHQL_URL = "https://api.github.com/graphql"
HEADERS = {
    "Authorization": f"bearer {TOKEN}",
    "Content-Type": "application/json",
}

# ─────────────────────────────────────────────────────────────────────────────
# Fetch one year-chunk of contributions
# ─────────────────────────────────────────────────────────────────────────────
QUERY = """
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

def fetch_year(year_start: datetime, year_end: datetime):
    """Return list of (date_str, count) for the given range."""
    resp = requests.post(
        GRAPHQL_URL,
        headers=HEADERS,
        json={
            "query": QUERY,
            "variables": {
                "login": USERNAME,
                "from":  year_start.isoformat(),
                "to":    year_end.isoformat(),
            },
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data:
        raise RuntimeError(f"GraphQL errors: {data['errors']}")

    user     = data["data"]["user"]
    weeks    = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    created  = user["createdAt"]

    days = []
    for week in weeks:
        for d in week["contributionDays"]:
            days.append((d["date"], d["contributionCount"]))
    return days, created


def fetch_all_contributions():
    """
    Fetch contributions for every year from account-creation year → now.
    GitHub's API only allows a 1-year window per query, so we page by year.
    """
    now = datetime.now(timezone.utc)

    # Get account creation year from the first query
    _, created_at = fetch_year(
        now - timedelta(days=365),
        now,
    )
    created_year = int(created_at[:4])

    all_days = []
    seen_dates = set()

    # Walk year by year from creation → now
    for yr in range(created_year, now.year + 1):
        yr_start = datetime(yr,     1,  1, tzinfo=timezone.utc)
        yr_end   = datetime(yr,    12, 31, 23, 59, 59, tzinfo=timezone.utc)

        # Cap to account creation and current time
        yr_start = max(yr_start, datetime(created_year, 1, 1, tzinfo=timezone.utc))
        yr_end   = min(yr_end, now)

        print(f"  Fetching {yr_start.date()} → {yr_end.date()} …")
        days, _ = fetch_year(yr_start, yr_end)

        for date_str, count in days:
            if date_str not in seen_dates:
                seen_dates.add(date_str)
                all_days.append((date_str, count))

    all_days.sort(key=lambda x: x[0])
    return all_days


# ─────────────────────────────────────────────────────────────────────────────
# Streak calculation  (correct algorithm)
# ─────────────────────────────────────────────────────────────────────────────
def calculate_streaks(all_days):
    """
    all_days: sorted list of (date_str, contribution_count)

    Returns (total, current_streak, longest_streak).

    Current streak:
      Walk backward from *today*. If today has 0 contributions we still
      keep the streak alive (day isn't over yet) and start counting from
      yesterday. A gap of any earlier day with 0 contributions breaks it.

    Longest streak:
      Single forward pass — global maximum run of consecutive days with ≥1
      contribution.
    """
    today      = datetime.now(timezone.utc).date()
    today_str  = today.strftime("%Y-%m-%d")

    # Build quick lookup  date_str → count
    contrib = {d: c for d, c in all_days}

    # ── Total ────────────────────────────────────────────────────────────────
    total = sum(c for _, c in all_days)

    # ── Current streak ───────────────────────────────────────────────────────
    current = 0
    cursor  = today

    # If today has 0, don't break — start counting from yesterday
    if contrib.get(today_str, 0) == 0:
        cursor = today - timedelta(days=1)
    else:
        current = 1
        cursor  = today - timedelta(days=1)

    while True:
        d_str = cursor.strftime("%Y-%m-%d")
        if contrib.get(d_str, 0) > 0:
            current += 1
            cursor -= timedelta(days=1)
        else:
            break   # gap found — streak ends

    # ── Longest streak ───────────────────────────────────────────────────────
    longest  = 0
    run      = 0
    prev     = None

    for date_str, count in all_days:          # already sorted ascending
        d = date.fromisoformat(date_str)
        if prev is not None and (d - prev).days > 1:
            run = 0                           # non-consecutive date gap → reset
        if count > 0:
            run += 1
            longest = max(longest, run)
        else:
            run = 0
        prev = d

    return total, current, longest


# ─────────────────────────────────────────────────────────────────────────────
# SVG builder
# ─────────────────────────────────────────────────────────────────────────────
def build_svg(total: int, current: int, longest: int, first_date: str, last_date: str) -> str:
    W, H  = 780, 195
    PAD   = 26
    col_w = (W - PAD * 2) / 3

    def cx(i):
        return PAD + col_w * i + col_w / 2

    def divider(i):
        if i == 0:
            return ""
        lx = PAD + col_w * i
        return (
            f'<line x1="{lx:.1f}" y1="32" x2="{lx:.1f}" y2="{H - 28}"'
            f' stroke="#00FFD1" stroke-width="1" stroke-opacity="0.25"/>'
        )

    def column(i, label_top, value_str, label_bot, color):
        x = cx(i)
        return f"""
  {divider(i)}
  <text x="{x:.1f}" y="54"  text-anchor="middle" fill="#8B949E"
        font-size="12.5" font-family="'Segoe UI',Arial,sans-serif">{label_top}</text>
  <text x="{x:.1f}" y="118" text-anchor="middle" fill="{color}"
        font-size="44" font-weight="700" font-family="'Segoe UI',Arial,sans-serif">{value_str}</text>
  <text x="{x:.1f}" y="150" text-anchor="middle" fill="#8B949E"
        font-size="12.5" font-family="'Segoe UI',Arial,sans-serif">{label_bot}</text>"""

    fire      = "🔥" if current > 0 else "❄️"
    lightning = "⚡"
    date_range = f"{first_date} – {last_date}"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
  <!-- Background -->
  <rect width="{W}" height="{H}" rx="14" fill="#0D1117"/>
  <!-- Border glow -->
  <rect width="{W}" height="{H}" rx="14" fill="none"
        stroke="#00FFD1" stroke-width="1" stroke-opacity="0.35"/>

  <!-- Date range header -->
  <text x="{W / 2:.1f}" y="21" text-anchor="middle" fill="#6E7681"
        font-size="11" font-family="'Segoe UI',Arial,sans-serif">{date_range}</text>

  <!-- Three columns -->
  {column(0, "Total Contributions", f"{total:,}", "contributions", "#FFFFFF")}
  {column(1, "Current Streak", f"{current} {fire}", "days", "#FF6B35")}
  {column(2, "Longest Streak", f"{longest} {lightning}", "days", "#00FFD1")}

  <!-- Footer -->
  <text x="{W / 2:.1f}" y="{H - 8:.1f}" text-anchor="middle" fill="#484F58"
        font-size="10" font-family="'Segoe UI',Arial,sans-serif">
    @{USERNAME} · github.com
  </text>
</svg>"""


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print(f"Fetching ALL contributions for @{USERNAME} …")
    all_days = fetch_all_contributions()

    total, current, longest = calculate_streaks(all_days)

    first_date = all_days[0][0]  if all_days else "N/A"
    last_date  = all_days[-1][0] if all_days else "N/A"

    print(f"  Date range   : {first_date} → {last_date}")
    print(f"  Total        : {total:,}")
    print(f"  Current streak: {current} days")
    print(f"  Longest streak: {longest} days")

    svg = build_svg(total, current, longest, first_date, last_date)

    os.makedirs("assets", exist_ok=True)
    out = "assets/streak-stats.svg"
    with open(out, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  ✅  Written → {out}")


if __name__ == "__main__":
    main()
