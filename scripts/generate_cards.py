#!/usr/bin/env python3
"""
Generates animated, brand-styled GitHub cards for the profile README:
  stats.svg     — overall GitHub stats + animated contributions ring
  langs.svg     — top languages with animated bars
  activity.svg  — contribution activity for the last 31 days (animated line chart)

Runs inside GitHub Actions (see .github/workflows/profile.yml).
Env: GH_TOKEN (required), GH_USER (default: repo owner), OUT_DIR (default: dist)
Local preview without network:  python scripts/generate_cards.py --mock
"""
import base64, datetime as dt, json, os, sys, urllib.request

RED, BG, CARD, LINE, MUT, WHITE = "#FF5757", "#121212", "#161616", "#2A2A2A", "#8A8A8A", "#FFFFFF"
USER = os.environ.get("GH_USER", "NafeaC")
OUT = os.environ.get("OUT_DIR", "dist")
TOKEN = os.environ.get("GH_TOKEN", "")
MOCK = "--mock" in sys.argv

# ─────────────────────────── fonts (embedded so they render inside <img>) ───────────────────────────
def _font_css():
    css = ""
    for w, style in [(400, "normal"), (600, "normal"), (800, "normal"), (800, "italic")]:
        url = f"https://cdn.jsdelivr.net/npm/@fontsource/poppins/files/poppins-latin-{w}-{style}.woff2"
        try:
            data = urllib.request.urlopen(url, timeout=20).read()
            b64 = base64.b64encode(data).decode()
            css += (f"@font-face{{font-family:'Poppins';font-weight:{w};font-style:{style};"
                    f"src:url(data:font/woff2;base64,{b64}) format('woff2');}}")
        except Exception as e:  # falls back to system fonts
            print(f"font {w}-{style} skipped: {e}", file=sys.stderr)
    return css

FONT_CSS = "" if MOCK and not os.environ.get("MOCK_FONTS") else _font_css()

BASE_CSS = f"""{FONT_CSS}
text{{font-family:'Poppins','Segoe UI',Ubuntu,'Helvetica Neue',sans-serif}}
.t{{font-size:17px;font-weight:800;fill:{WHITE}}}
.st{{font-size:11px;font-weight:600;fill:{MUT};letter-spacing:2.5px}}
.lbl{{font-size:13.5px;fill:#D0D0D0}}
.val{{font-size:13.5px;font-weight:800;fill:{WHITE}}}
.fade{{opacity:0;animation:fade .7s cubic-bezier(.2,.8,.2,1) forwards}}
@keyframes fade{{from{{opacity:0;transform:translateX(-10px)}}to{{opacity:1;transform:none}}}}
.grow{{transform-box:fill-box;transform-origin:left;animation:grow 1.2s cubic-bezier(.2,.8,.2,1) both}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.pulse{{animation:pulse 1.8s ease-in-out infinite;transform-box:fill-box;transform-origin:center}}
@keyframes pulse{{0%,100%{{opacity:1}}50%{{opacity:.3}}}}
.sweep{{animation:sweep 5s ease-in-out infinite}}
@keyframes sweep{{from{{transform:translateX(-200px)}}to{{transform:translateX(1200px)}}}}
"""

def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def kfmt(n):
    return f"{n/1000:.1f}k".replace(".0k", "k") if n >= 1000 else str(n)

def frame(w, h, title, sub, body, extra_css=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">
<style>{BASE_CSS}{extra_css}</style>
<defs>
  <clipPath id="r"><rect width="{w}" height="{h}" rx="14"/></clipPath>
  <linearGradient id="sw" x1="0" x2="1"><stop offset="0" stop-color="{RED}" stop-opacity="0"/><stop offset=".5" stop-color="{RED}"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></linearGradient>
</defs>
<g clip-path="url(#r)">
  <rect width="{w}" height="{h}" fill="{BG}"/>
  <rect width="{w}" height="3" fill="{LINE}"/>
  <rect class="sweep" width="160" height="3" fill="url(#sw)"/>
  <circle class="pulse" cx="28" cy="34" r="4.5" fill="{RED}"/>
  <text x="42" y="40" class="t">{esc(title)}</text>
  <text x="{w-24}" y="39" class="st" text-anchor="end">{esc(sub)}</text>
  {body}
</g>
</svg>'''

# ─────────────────────────── data ───────────────────────────
def gql(query, variables):
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": variables}).encode(),
        headers={"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json",
                 "User-Agent": "profile-cards"})
    res = json.loads(urllib.request.urlopen(req, timeout=60).read())
    if "errors" in res:
        raise RuntimeError(res["errors"])
    return res["data"]

Q_USER = """query($login:String!,$after:String){ user(login:$login){
  createdAt followers{totalCount}
  pullRequests{totalCount} issues{totalCount}
  repositoriesContributedTo(contributionTypes:[COMMIT,PULL_REQUEST,ISSUE,REPOSITORY]){totalCount}
  contributionsCollection{ contributionYears
    contributionCalendar{ weeks{ contributionDays{ date contributionCount } } } }
  repositories(first:100, after:$after, ownerAffiliations:OWNER, isFork:false){
    totalCount pageInfo{hasNextPage endCursor}
    nodes{ stargazerCount languages(first:10, orderBy:{field:SIZE,direction:DESC}){ edges{ size node{ name color } } } } }
}}"""

Q_YEAR = """query($login:String!,$from:DateTime!,$to:DateTime!){ user(login:$login){
  contributionsCollection(from:$from,to:$to){ totalCommitContributions restrictedContributionsCount
    contributionCalendar{ totalContributions } } }}"""

def fetch():
    if MOCK:
        import random
        random.seed(7)
        today = dt.date.today()
        days = [{"date": str(today - dt.timedelta(days=i)), "contributionCount": random.choice([0, 0, 1, 2, 3, 5, 8])} for i in range(60)][::-1]
        return dict(stars=12, commits=264, prs=18, issues=9, contributed=6, repos=21, followers=34, total=412,
                    langs=[("PHP", 41000, "#4F5D95"), ("Python", 30000, "#3572A5"), ("JavaScript", 21000, "#f1e05a"),
                           ("C++", 9000, "#f34b7d"), ("HTML", 7000, "#e34c26"), ("CSS", 4000, "#563d7c")],
                    days=days, since=2022)

    data, repos, after = None, [], None
    while True:
        d = gql(Q_USER, {"login": USER, "after": after})["user"]
        data = data or d
        repos += d["repositories"]["nodes"]
        pi = d["repositories"]["pageInfo"]
        if not pi["hasNextPage"]:
            break
        after = pi["endCursor"]

    commits = total = 0
    years = data["contributionsCollection"]["contributionYears"]
    for y in years:
        c = gql(Q_YEAR, {"login": USER, "from": f"{y}-01-01T00:00:00Z", "to": f"{y}-12-31T23:59:59Z"})["user"]["contributionsCollection"]
        commits += c["totalCommitContributions"] + c["restrictedContributionsCount"]
        total += c["contributionCalendar"]["totalContributions"]

    langs = {}
    for r in repos:
        for e in r["languages"]["edges"]:
            n = e["node"]["name"]
            s, col = langs.get(n, (0, e["node"]["color"] or MUT))
            langs[n] = (s + e["size"], col)
    langs = sorted(((n, s, c) for n, (s, c) in langs.items()), key=lambda x: -x[1])

    days = [d for w in data["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    return dict(stars=sum(r["stargazerCount"] for r in repos), commits=commits,
                prs=data["pullRequests"]["totalCount"], issues=data["issues"]["totalCount"],
                contributed=data["repositoriesContributedTo"]["totalCount"],
                repos=data["repositories"]["totalCount"], followers=data["followers"]["totalCount"],
                total=total, langs=langs, days=days, since=min(years) if years else dt.date.today().year)

# ─────────────────────────── cards ───────────────────────────
ICONS = {  # simple 16px glyphs, drawn in brand red
    "star": "M8 1.5l1.9 4 4.3.5-3.2 2.9.9 4.3L8 11l-3.9 2.2.9-4.3L1.8 6l4.3-.5z",
    "commit": "M8 5a3 3 0 110 6 3 3 0 010-6zM0 7.2h4.6v1.6H0zM11.4 7.2H16v1.6h-4.6z",
    "pr": "M4 2a2 2 0 100 4 2 2 0 000-4zM3.2 6h1.6v4H3.2zM4 10a2 2 0 100 4 2 2 0 000-4zM12 10a2 2 0 100 4 2 2 0 000-4zM11.2 6.5h1.6V10h-1.6zM8 2.5h2.5a2 2 0 012 2v2h-1.6v-2a.4.4 0 00-.4-.4H8V6L5.5 3.3 8 .6z",
    "issue": "M8 1a7 7 0 110 14A7 7 0 018 1zm0 1.6a5.4 5.4 0 100 10.8A5.4 5.4 0 008 2.6zM8 6.5a1.5 1.5 0 110 3 1.5 1.5 0 010-3z",
    "repo": "M3 1.5h10v11H4.5a1 1 0 000 2H13V16H4.5A2.5 2.5 0 012 13.5V2.5a1 1 0 011-1zm1.5 1.6v7.9h6.9V3.1z",
    "people": "M5.5 2a2.8 2.8 0 110 5.6 2.8 2.8 0 010-5.6zM0 14c0-3 2.4-5 5.5-5s5.5 2 5.5 5v.5H0zM11 3a2.4 2.4 0 110 4.8A2.4 2.4 0 0111 3zm1 6.3c2.3.3 4 2 4 4.4v.8h-3.6c0-2-.2-3.6-.4-5.2z",
}

def stats_card(d):
    W, H = 495, 210
    rows = [("star", "Total Stars", d["stars"]), ("commit", "Total Commits", d["commits"]),
            ("pr", "Pull Requests", d["prs"]), ("issue", "Issues", d["issues"]),
            ("repo", "Contributed To", d["contributed"]), ("people", "Followers", d["followers"])]
    body = ""
    for i, (ic, label, v) in enumerate(rows):
        y = 70 + i * 22.5
        body += (f'<g class="fade" style="animation-delay:{0.15 + i*0.12:.2f}s">'
                 f'<path transform="translate(28,{y-12}) scale(.85)" d="{ICONS[ic]}" fill="{RED}"/>'
                 f'<text x="52" y="{y}" class="lbl">{label}:</text>'
                 f'<text x="250" y="{y}" class="val" text-anchor="end">{kfmt(v)}</text></g>')
    # ring
    cx, cy, r = 385, 118, 52
    circ = 2 * 3.14159 * r
    body += f'''
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{LINE}" stroke-width="7"/>
  <circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{RED}" stroke-width="7" stroke-linecap="round"
    stroke-dasharray="{circ:.1f}" stroke-dashoffset="{circ:.1f}" transform="rotate(-90 {cx} {cy})" class="ring"/>
  <g class="fade" style="animation-delay:.9s">
    <text x="{cx}" y="{cy+6}" text-anchor="middle" font-size="26" font-weight="800" fill="{WHITE}">{kfmt(d["total"])}</text>
    <text x="{cx}" y="{cy+26}" text-anchor="middle" font-size="8" font-weight="600" letter-spacing=".8" fill="{MUT}">CONTRIBUTIONS</text>
  </g>'''
    css = (f".ring{{animation:ring 1.8s .3s cubic-bezier(.2,.8,.2,1) forwards}}"
           f"@keyframes ring{{to{{stroke-dashoffset:{circ*0.12:.1f}}}}}")
    return frame(W, H, "GitHub Stats", f"SINCE {d['since']}", body, css)

def langs_card(d):
    W, H = 495, 210
    langs = d["langs"][:8]
    tot = sum(s for _, s, _ in langs) or 1
    body, x = "", 28.0
    bw = W - 56
    body += f'<rect x="28" y="62" width="{bw}" height="10" rx="5" fill="{LINE}"/>'
    body += '<clipPath id="bar"><rect x="28" y="62" width="%d" height="10" rx="5"/></clipPath><g clip-path="url(#bar)">' % bw
    for i, (n, s, c) in enumerate(langs):
        w = bw * s / tot
        body += f'<rect class="grow" style="animation-delay:{0.2 + i*0.1:.2f}s" x="{x:.1f}" y="62" width="{w+0.5:.1f}" height="10" fill="{c}"/>'
        x += w
    body += "</g>"
    for i, (n, s, c) in enumerate(langs):
        col, row = i % 2, i // 2
        lx, ly = 28 + col * 225, 104 + row * 27
        pct = 100 * s / tot
        body += (f'<g class="fade" style="animation-delay:{0.5 + i*0.1:.2f}s">'
                 f'<circle cx="{lx+5}" cy="{ly-4}" r="5" fill="{c}"/>'
                 f'<text x="{lx+18}" y="{ly}" class="lbl">{esc(n)}</text>'
                 f'<text x="{lx+205}" y="{ly}" class="val" text-anchor="end">{pct:.1f}%</text></g>')
    return frame(W, H, "Top Languages", "BY CODE SIZE", body)

def activity_card(d):
    W, H = 1000, 300
    days = d["days"][-31:]
    counts = [x["contributionCount"] for x in days]
    mx = max(max(counts), 4)
    L, R, T, B = 56, 30, 70, 250
    pw, ph = W - L - R, B - T
    step = pw / (len(days) - 1)
    pts = [(L + i * step, B - ph * c / mx) for i, c in enumerate(counts)]

    def smooth(p):
        s = f"M{p[0][0]:.1f},{p[0][1]:.1f}"
        for i in range(1, len(p)):
            x0, y0 = p[i - 1]; x1, y1 = p[i]
            mxp = (x0 + x1) / 2
            s += f" C{mxp:.1f},{y0:.1f} {mxp:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
        return s

    line = smooth(pts)
    area = line + f" L{pts[-1][0]:.1f},{B} L{pts[0][0]:.1f},{B} Z"
    grid = ""
    for k in range(5):
        y = B - ph * k / 4
        grid += f'<line x1="{L}" x2="{W-R}" y1="{y:.1f}" y2="{y:.1f}" stroke="{LINE}" stroke-dasharray="3 5"/>'
        grid += f'<text x="{L-14}" y="{y+4:.1f}" font-size="11" fill="{MUT}" text-anchor="end">{round(mx*k/4)}</text>'
    labels = ""
    for i, x in enumerate(days):
        if i % 3 == 0 or i == len(days) - 1:
            day = dt.date.fromisoformat(x["date"])
            labels += f'<text x="{pts[i][0]:.1f}" y="{B+22}" font-size="10.5" fill="{MUT}" text-anchor="middle">{day.strftime("%b %d")}</text>'
    dots = "".join(
        f'<circle class="dot" style="animation-delay:{1.4 + i*0.035:.2f}s" cx="{x:.1f}" cy="{y:.1f}" r="{4 if counts[i] else 2.6}" '
        f'fill="{WHITE if counts[i] else LINE}" stroke="{RED}" stroke-width="{2 if counts[i] else 0}"/>'
        for i, (x, y) in enumerate(pts))
    total = sum(counts)
    body = f'''
  <defs><linearGradient id="ar" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="{RED}" stop-opacity=".45"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></linearGradient></defs>
  {grid}{labels}
  <path class="area" d="{area}" fill="url(#ar)"/>
  <path class="line" d="{line}" fill="none" stroke="{RED}" stroke-width="3" stroke-linecap="round" pathLength="1"/>
  {dots}
  <g class="fade" style="animation-delay:.4s"><text x="{W-24}" y="62" text-anchor="end" font-size="12" fill="{MUT}"><tspan font-weight="800" fill="{WHITE}">{total}</tspan> contributions</text></g>'''
    css = (".line{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 2.2s .3s ease-out forwards}"
           "@keyframes draw{to{stroke-dashoffset:0}}"
           ".area{opacity:0;animation:af 1.2s 1.2s ease forwards}@keyframes af{to{opacity:1}}"
           ".dot{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .45s cubic-bezier(.3,1.6,.5,1) forwards}"
           "@keyframes pop{from{opacity:0;transform:scale(0)}to{opacity:1;transform:scale(1)}}")
    return frame(W, H, "Contribution Activity", "LAST 31 DAYS", body, css)

def main():
    d = fetch()
    os.makedirs(OUT, exist_ok=True)
    for name, fn in [("stats.svg", stats_card), ("langs.svg", langs_card), ("activity.svg", activity_card)]:
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(fn(d))
        print("wrote", os.path.join(OUT, name))

if __name__ == "__main__":
    main()
