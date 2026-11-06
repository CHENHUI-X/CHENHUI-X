"""Generate profile images from GitHub data using Python and the GitHub CLI."""

import json
import re
import subprocess
from collections import Counter
from datetime import date
from html import escape
from pathlib import Path


QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC) {
      pageInfo { hasNextPage endCursor }
      nodes {
        stargazerCount
        isFork
        languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
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


def svg(width, height, title, content, vertical_padding=0):
    canvas_height = height + 2 * vertical_padding
    palette = "".join(
        f".level-{i}{{fill:{color}}}" for i, color in enumerate(COLORS["light"])
    )
    dark_palette = "".join(
        f".level-{i}{{fill:{color}}}" for i, color in enumerate(COLORS["dark"])
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{canvas_height}" viewBox="0 0 {width} {canvas_height}" role="img" aria-labelledby="title">
  <title id="title">{escape(title)}</title>
  <style>
    text{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}}
    .bg{{fill:#ffffff;stroke:#d0d7de}} .text{{fill:#1f2328}}
    .muted{{fill:#656d76}} .accent{{fill:#0969da}}
    .mono{{font-family:ui-monospace,SFMono-Regular,Consolas,monospace}}
    {palette}
    @media(prefers-color-scheme:dark){{
      .bg{{fill:#0d1117;stroke:#30363d}} .text{{fill:#e6edf3}}
      .muted{{fill:#8b949e}} .accent{{fill:#58a6ff}}
      {dark_palette}
    }}
  </style>
  <rect class="bg" x="0.5" y="{vertical_padding + 0.5}" width="{width - 1}" height="{height - 1}" rx="10"/>
  <g transform="translate(0,{vertical_padding})">{''.join(content)}</g>
</svg>
'''


def overview_card(lines, stars, contributions, updated, compact=False):
    if not compact:
        code = re.sub(r"(?m)^(\w+=\([^\n]*)\n +([^\n]*\))$", r"\1 \2", "\n".join(lines))
        lines = code.splitlines()
    width = 360 if compact else 860
    code_end = 78 + len(lines) * 20
    stats_top = code_end + 40 if compact else 32
    height = stats_top + 214 if compact else code_end + 26
    content = [
        '<text class="text mono" x="24" y="32" font-size="14" font-weight="600">~$ cat profile.sh</text>',
        f'<path d="M24 52H{width - 24}" fill="none" stroke="#8b949e" stroke-opacity="0.3"/>',
    ]
    if not compact:
        content.append(f'<path d="M548 52V{height - 24}" fill="none" stroke="#8b949e" stroke-opacity="0.3"/>')
    for i, line in enumerate(lines):
        if line.startswith("#"):
            value = f'<tspan class="muted">{escape(line)}</tspan>'
        elif "=" in line:
            name, value = line.split("=", 1)
            value = f'{escape(name)}=<tspan class="accent">{escape(value)}</tspan>'
        else:
            value = f'<tspan class="accent">{escape(line)}</tspan>'
        content.append(f'<text class="text mono" x="24" y="{78 + i * 20}" font-size="13" xml:space="preserve">{value}</text>')
    rows = [
        ("Stars · public repos", stars),
        ("Commits", contributions["totalCommitContributions"]),
        ("Pull requests", contributions["totalPullRequestContributions"]),
        ("Issues", contributions["totalIssueContributions"]),
    ]
    stats_left = 24 if compact else 580
    if compact:
        content.append(f'<path d="M24 {code_end + 8}H336" fill="none" stroke="#8b949e" stroke-opacity="0.3"/>')
    content.append(f'<text class="text mono" x="{stats_left}" y="{stats_top}" font-size="14" font-weight="600">GitHub stats</text>')
    for i, (label, value) in enumerate(rows):
        x = stats_left + (i % 2) * 164 if compact else stats_left
        y = stats_top + 48 + (i // 2) * 76 if compact else 114 + i * ((height - 164) / 4)
        content.append(f'<text class="accent" x="{x}" y="{y}" font-size="26" font-weight="600">{value:,}</text>')
        content.append(f'<text class="muted" x="{x}" y="{y + 22}" font-size="12">{label}</text>')
    content.append(f'<text class="muted" x="{stats_left}" y="{height - 44}" font-size="10">Activity: last 12 months</text>')
    content.append(f'<text class="muted" x="{stats_left}" y="{height - 24}" font-size="10">Updated {updated}</text>')
    return svg(width, height, "Chenhui's Shell profile, projects, and GitHub statistics", content)


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


def language_chart(languages, compact=False):
    total = sum(languages.values())
    rows = languages.most_common(5)
    other = total - sum(size for _, size in rows)
    if other:
        rows.append(("Other", other))
    width = 430 if compact else 860
    height = 110 + len(rows) * (64 if compact else 42)
    content = [
        '<text class="muted" x="24" y="36" font-size="12">Public, non-fork repositories · by code size</text>',
    ]
    for i, (name, size) in enumerate(rows):
        percent = size / total * 100
        y = 82 + i * (64 if compact else 42)
        content.append(f'<text class="text mono" x="24" y="{y}" font-size="14">{escape(name)}</text>')
        content.append(f'<text class="muted mono" x="{width - 24}" y="{y}" text-anchor="end" font-size="13">{percent:.2f} %</text>')
        left, top = (24, y + 14) if compact else (240, y - 11)
        step = 14 if compact else 18
        for segment in range(27):
            color = "accent" if (segment + 0.5) / 27 <= size / total else "level-0"
            content.append(f'<rect class="{color}" x="{left + segment * step}" y="{top}" width="{step - 2}" height="12" rx="1"/>')
    content.append(f'<text class="muted" x="24" y="{height - 18}" font-size="10">GitHub Linguist · language share across my projects</text>')
    return svg(width, height, "Code language distribution by size in public, non-fork repositories", content)


def main():
    cursor = None
    stars = 0
    languages = Counter()
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
        for repo in repositories["nodes"]:
            stars += repo["stargazerCount"]
            if not repo["isFork"]:
                for language in repo["languages"]["edges"]:
                    languages[language["node"]["name"]] += language["size"]
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
    readme = (output.parent / "README.md").read_text(encoding="utf-8")
    lines = re.search(r"```bash\n(.*?)```", readme, re.S)[1].strip().splitlines()
    (output / "overview.svg").write_text(overview_card(lines, stars, contributions, days[-1]["date"]), encoding="utf-8")
    (output / "overview-mobile.svg").write_text(overview_card(lines, stars, contributions, days[-1]["date"], compact=True), encoding="utf-8")
    (output / "contributions.svg").write_text(contribution_chart(calendar), encoding="utf-8")
    (output / "contributions-mobile.svg").write_text(contribution_chart(calendar, compact=True), encoding="utf-8")
    (output / "languages.svg").write_text(language_chart(languages), encoding="utf-8")
    (output / "languages-mobile.svg").write_text(language_chart(languages, compact=True), encoding="utf-8")
    print(f"Updated profile: {stars:,} stars, {calendar['totalContributions']:,} contributions")
    print("Language shares:", ", ".join(f"{name} {size / sum(languages.values()):.2%}" for name, size in languages.most_common(5)))


if __name__ == "__main__":
    main()
