"""Generate profile images from GitHub data using Python and the GitHub CLI."""

import json
import subprocess
from datetime import date
from html import escape
from pathlib import Path


QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalPullRequestContributions
      totalIssueContributions
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
  }
}
"""

LEVELS = ["NONE", "FIRST_QUARTILE", "SECOND_QUARTILE", "THIRD_QUARTILE", "FOURTH_QUARTILE"]
COLORS = {
    "light": ["#eff2f5", "#d5e9ff", "#9acbff", "#58a6ff", "#0969da"],
    "dark": ["#161b22", "#122c46", "#1b4b78", "#2f81c8", "#58a6ff"],
}


def svg(width, height, title, content):
    palette = "".join(
        f".level-{i}{{fill:{color}}}" for i, color in enumerate(COLORS["light"])
    )
    dark_palette = "".join(
        f".level-{i}{{fill:{color}}}" for i, color in enumerate(COLORS["dark"])
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title">
  <title id="title">{escape(title)}</title>
  <style>
    text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
    .bg{{fill:#ffffff;stroke:#d0d7de}} .text{{fill:#1f2328}}
    .muted{{fill:#656d76}} .accent{{fill:#0969da}}
    {palette}
    @media(prefers-color-scheme:dark){{
      .bg{{fill:#0d1117;stroke:#30363d}} .text{{fill:#e6edf3}}
      .muted{{fill:#8b949e}} .accent{{fill:#58a6ff}}
      {dark_palette}
    }}
  </style>
  <rect class="bg" x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10"/>
  {''.join(content)}
</svg>
'''


def stats_card(stars, contributions, updated, wide=False):
    rows = [
        ("Stars on public repos", stars),
        ("Commits · last 12 months", contributions["totalCommitContributions"]),
        ("Pull requests · last 12 months", contributions["totalPullRequestContributions"]),
        ("Issues · last 12 months", contributions["totalIssueContributions"]),
    ]
    content = ['<text class="text" x="24" y="32" font-size="17" font-weight="600">Chenhui’s GitHub Stats</text>']
    for i, (label, value) in enumerate(rows):
        if wide:
            x = 24 + i * 208
            content.append(f'<text class="accent" x="{x}" y="78" font-size="30" font-weight="600">{value:,}</text>')
            content.append(f'<text class="muted" x="{x}" y="103" font-size="12">{label}</text>')
        else:
            y = 62 + i * 27
            content.append(f'<text class="muted" x="24" y="{y}" font-size="13">{label}</text>')
            content.append(f'<text class="accent" x="365" y="{y}" text-anchor="end" font-size="15" font-weight="600">{value:,}</text>')
    width, height = (860, 148) if wide else (390, 194)
    content.append(f'<text class="muted" x="24" y="{height - 20}" font-size="11">Updated {updated} · GitHub data</text>')
    return svg(width, height, "Chenhui's GitHub statistics", content)


def contribution_chart(calendar, compact=False):
    weeks = calendar["weeks"]
    width, height = (430, 354) if compact else (860, 214)
    step = 13 if compact else 14
    left = 48 if compact else 62
    columns = 27 if compact else len(weeks)
    total = calendar["totalContributions"]
    content = [f'<text class="text" x="24" y="31" font-size="16" font-weight="600">{total:,} contributions in the last year</text>']
    for start in range(0, len(weeks), columns):
        top = 80 + (start // columns) * 130
        previous_month = None
        for column, week in enumerate(weeks[start:start + columns]):
            days = week["contributionDays"]
            first = date.fromisoformat(days[0]["date"])
            month = next(
                (date.fromisoformat(day["date"]) for day in days if day["date"].endswith("-01")),
                first,
            )
            x = left + column * step
            if month.month != previous_month:
                content.append(f'<text class="muted" x="{x}" y="{top - 14}" font-size="11">{month:%b}</text>')
                previous_month = month.month
            for day in days:
                weekday = (date.fromisoformat(day["date"]).weekday() + 1) % 7
                y = top + weekday * step
                level = LEVELS.index(day["contributionLevel"])
                count = day["contributionCount"]
                content.append(f'<rect class="level-{level}" x="{x}" y="{y}" width="{step - 3}" height="{step - 3}" rx="2"><title>{day["date"]}: {count} contributions</title></rect>')
        for weekday, label in [(1, "Mon"), (3, "Wed"), (5, "Fri")]:
            content.append(f'<text class="muted" x="{left - 10}" y="{top + weekday * step + 9}" text-anchor="end" font-size="10">{label}</text>')
    footer = height - 20
    content.append(f'<text class="muted" x="24" y="{footer}" font-size="10">{weeks[0]["contributionDays"][0]["date"]} — {weeks[-1]["contributionDays"][-1]["date"]}</text>')
    content.append(f'<text class="muted" x="{width - 160}" y="{footer}" font-size="10">Less</text>')
    for i in range(5):
        content.append(f'<rect class="level-{i}" x="{width - 128 + 14 * i}" y="{footer - 10}" width="10" height="10" rx="2"/>')
    content.append(f'<text class="muted" x="{width - 50}" y="{footer}" font-size="10">More</text>')
    return svg(width, height, f"{total} GitHub contributions in the last year", content)


def main():
    cursor = None
    stars = 0
    while True:
        request = {"query": QUERY, "variables": {"login": "CHENHUI-X", "after": cursor}}
        response = json.loads(subprocess.check_output(
            ["gh", "api", "graphql", "--input", "-"],
            input=json.dumps(request), text=True, timeout=60,
        ))
        if response.get("errors"):
            raise RuntimeError(response["errors"])
        user = response["data"]["user"]
        repositories = user["repositories"]
        stars += sum(repo["stargazerCount"] for repo in repositories["nodes"])
        if not repositories["pageInfo"]["hasNextPage"]:
            break
        cursor = repositories["pageInfo"]["endCursor"]

    contributions = user["contributionsCollection"]
    calendar = contributions["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]]
    if not days or sum(day["contributionCount"] for day in days) != calendar["totalContributions"]:
        raise ValueError("GitHub contribution calendar is incomplete")

    output = Path(__file__).resolve().parents[1] / "assets"
    output.mkdir(exist_ok=True)
    (output / "stats.svg").write_text(stats_card(stars, contributions, days[-1]["date"]), encoding="utf-8")
    (output / "stats-wide.svg").write_text(stats_card(stars, contributions, days[-1]["date"], wide=True), encoding="utf-8")
    (output / "contributions.svg").write_text(contribution_chart(calendar), encoding="utf-8")
    (output / "contributions-mobile.svg").write_text(contribution_chart(calendar, compact=True), encoding="utf-8")
    print(f"Updated profile: {stars:,} stars, {calendar['totalContributions']:,} contributions")


if __name__ == "__main__":
    main()
