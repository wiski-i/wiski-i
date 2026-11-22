"""Render the profile's linked SVG cards from the account's public projects."""

import json
import os
import re
import textwrap
from html import escape
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
OWNER = "wiski-i"
START = "<!-- repository-cards:start -->"
END = "<!-- repository-cards:end -->"
GENERATED = ROOT / "assets/generated-repositories"
EXCLUDED = {"testdisk"}

CURATED = {
    "starlit-crosshair": (
        "Crosshair Studio",
        "Windows crosshair editor and overlay with per-game profiles, profile packs, and pixel calibration.",
        "C# · .NET Framework",
        "assets/repo-crosshair.svg",
    ),
    "wiski-i": (
        "wiski-i",
        "Source for this GitHub profile, including the Jeton artwork and coin animation.",
        "SVG · CSS · Markdown",
        "assets/repo-wiski.svg",
    ),
    "starlit-desk": (
        "Starlit Desk",
        "Five seasonal effects for your Windows desktop, from snowfall to space.",
        "C# · .NET Framework",
        None,
    ),
    "starlit-deskrewind": (
        "Starlit DeskRewind",
        "Save, preview, and restore window layouts across multiple monitors.",
        "C# · .NET Framework",
        None,
    ),
}

ICONS = {
    "starlit-desk": """<path d="M385 31l3.5 15.5L404 50l-15.5 3.5L385 69l-3.5-15.5L366 50l15.5-3.5z" fill="#ff8eb7"/>
    <path d="M401 30v10m-5-5h10M368 62v10m-5-5h10" stroke="#69e6ff" stroke-width="2" stroke-linecap="round"/>""",
    "starlit-deskrewind": """<rect x="379" y="32" width="25" height="23" rx="5" fill="none" stroke="#cabaff" stroke-width="2.5"/>
    <rect x="366" y="44" width="32" height="25" rx="5" fill="#1b2537" stroke="#b3e0f7" stroke-width="2.5"/>
    <path d="M367 51h30m-17 5-4 4 4 4m-4-4h13" fill="none" stroke="#b3e0f7" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>""",
}
DEFAULT_ICON = """<path d="M371 36h19l10 10v19a3 3 0 0 1-3 3h-26a3 3 0 0 1-3-3V39a3 3 0 0 1 3-3zm19 0v11h10m-24 7h15m-15 7h10" fill="none" stroke="#69e6ff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>"""


def repositories():
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "wiski-i-profile-repository-cards",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token := os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    projects = []
    page = 1
    while True:
        query = urlencode({"type": "owner", "sort": "full_name", "per_page": 100, "page": page})
        request = Request(f"https://api.github.com/users/{OWNER}/repos?{query}", headers=headers)
        with urlopen(request, timeout=25) as response:
            batch = json.load(response)
        projects.extend(repo for repo in batch if not repo["fork"] and not repo["private"]
                        and repo["name"].casefold() not in EXCLUDED and repo["owner"]["login"].casefold() == OWNER)
        if len(batch) < 100:
            break
        page += 1
    if not any(repo["name"].casefold() == OWNER for repo in projects):
        raise ValueError("The GitHub response did not include the profile repository.")
    order = {key: index for index, key in enumerate(CURATED)}
    return sorted(projects, key=lambda repo: (order.get(repo["name"].casefold(), len(order)), repo["name"].casefold()))


def svg_card(key, title, description, language):
    title_line = textwrap.shorten(title, width=21, placeholder="…") if len(title.split()) > 1 else title[:20] + ("…" if len(title) > 20 else "")
    wrapper = textwrap.TextWrapper(width=35, max_lines=2, placeholder="…")
    description_lines = wrapper.wrap(" ".join(description.split()))
    copy = "\n".join(f'    <text x="20" y="{68 + index * 21}" font-size="15" fill="#f1eaf9">{escape(line)}</text>'
                     for index, line in enumerate(description_lines))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 436 150" role="img" aria-labelledby="title">
  <title id="title">{escape(title)}</title>
  <defs>
    <linearGradient id="panel" x2="1" y2="1">
      <stop stop-color="#1b112b"/><stop offset="1" stop-color="#0d0817"/>
    </linearGradient>
    <pattern id="grid" width="8" height="8" patternUnits="userSpaceOnUse">
      <path d="M8 0H0v8" fill="none" stroke="#4a365f" opacity=".62"/>
    </pattern>
  </defs>
  <rect x="1" y="1" width="434" height="140" rx="14" fill="url(#panel)" stroke="#493262" stroke-width="2"/>
  <rect x="356" y="23" width="58" height="58" rx="7" fill="url(#grid)" stroke="#4a365f"/>
  {ICONS.get(key, DEFAULT_ICON)}
  <path d="M20 104h396" stroke="#4a365f"/>
  <g font-family="Consolas, 'Courier New', monospace">
    <text x="20" y="42" font-size="25" font-weight="700" fill="#ff8eb7">{escape(title_line)}</text>
{copy}
    <text x="20" y="128" font-size="14" font-weight="700" fill="#ffe17c">{escape(language[:27])}</text>
    <text x="416" y="128" text-anchor="end" font-size="14" font-weight="700" fill="#69e6ff">OPEN REPO ↗</text>
  </g>
</svg>
'''


def render(projects):
    readme_path = ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    before, marker, rest = readme.partition(START)
    _, closing, after = rest.partition(END)
    if not marker or not closing:
        raise ValueError("Missing repository card markers in README.md.")

    generated = {}
    links = []
    for repo in projects:
        name = repo["name"]
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
            raise ValueError(f"Unexpected GitHub repository name: {name!r}")
        key = name.casefold()
        title, description, language, image = CURATED.get(
            key, (name, repo["description"] or "Browse the source and project details.", repo["language"] or "Source repository", None)
        )
        if image is None:
            path = GENERATED / f"{key}.svg"
            generated[path] = svg_card(key, title, description, language)
            image = path.relative_to(ROOT).as_posix()
        alt = escape(f"Open {title} repository. {description} {language}.", quote=True)
        links.append(f'<a href="https://github.com/{OWNER}/{quote(name, safe="")}"><img width="400" src="{image}" alt="{alt}"></a>')

    rows = "\n\n".join("<p>" + " ".join(links[i:i + 2]) + "</p>" for i in range(0, len(links), 2))
    banner_path = ROOT / "assets/repositories.svg"
    banner = banner_path.read_text(encoding="utf-8")
    count_label = "PROJECT" if len(projects) == 1 else "PROJECTS"
    banner, count = re.subn(r'(<text id="project-count"[^>]*>)[^<]*', rf'\g<1>{len(projects)} {count_label}', banner)
    if count != 1:
        raise ValueError("Missing project-count field in repositories.svg.")

    GENERATED.mkdir(parents=True, exist_ok=True)
    for path, content in generated.items():
        path.write_text(content, encoding="utf-8", newline="\n")
    for stale in GENERATED.glob("*.svg"):
        if stale not in generated:
            stale.unlink()
    readme_path.write_text(f"{before}{START}\n{rows}\n{END}{after}", encoding="utf-8", newline="\n")
    banner_path.write_text(banner, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    render(repositories())
