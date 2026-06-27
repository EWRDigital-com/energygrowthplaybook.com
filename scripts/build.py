#!/usr/bin/env python3
"""Static-site generator for energygrowthplaybook.com.

Reads data/episodes.json (produced by fetch_feed.py) and emits the full
static site: home, podcast index, per-episode pages, about, hosts, book,
plus llms.txt / robots.txt / sitemap.xml.

Folder-per-page output (/podcast/<slug>/index.html) so clean URLs work
identically on `python -m http.server`, `npx serve`, and Vercel — no config.

Stdlib only.
"""
import json, os, re, html, hashlib
from email.utils import parsedate_to_datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "episodes.json")
SITE = "https://energygrowthplaybook.com"
INDEXNOW_KEY = "68bd135014ff49f6961f2df2e98dc735"   # IndexNow verification key (served at /{key}.txt)
_SALT_FILE = os.path.join(ROOT, "scripts", ".salt")  # gitignored — keeps the watermark salt OUT of a public repo
CANARY_SALT = (os.environ.get("EGP_CANARY_SALT")
               or (open(_SALT_FILE, encoding="utf-8").read().strip() if os.path.exists(_SALT_FILE) else "egp-fallback-rotate-me"))

BRAND = "The Energy Growth Playbook"
TAGLINE = "The Oil & Gas Sales & Marketing Podcast — and the book — for energy leaders."
AMAZON = "https://www.amazon.com/dp/B0G26X7VP5"
LISTEN = [
    ("Apple Podcasts", "https://podcasts.apple.com/us/podcast/oil-and-gas-sales-and-marketing-podcast/id1663565581"),
    ("Spotify", "https://open.spotify.com/show/3QL6VKrVuy1l5JDoslOtXv"),
    ("YouTube", "https://www.youtube.com/playlist?list=PLSSvq3OXaTmHXu87Mjcf9A0Hufm7BOwjY"),
    ("OGGN", "https://oggn.com/oil-gas-sales-and-marketing-podcast/"),
    ("RSS", "https://feeds.oggn.com/category/ogsm/feed/"),
]
NAV = [("Episodes", "/podcast/"), ("The Book", "/book/"), ("Hosts", "/host/"), ("About", "/about/")]

# ---------- helpers ----------
def slugify(s):
    s = re.sub(r"\s*[|–—-]\s*Ep\s*\d+\s*$", "", s, flags=re.I)   # drop trailing "| Ep 92"
    s = re.sub(r"&", " and ", s)
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    return re.sub(r"-{2,}", "-", s)[:70].strip("-")

def ep_num(title):
    m = re.search(r"\bEp\s*(\d+)\b", title, flags=re.I)
    return m.group(1) if m else ""

def clean_title(title):
    return re.sub(r"\s*[|–—-]\s*Ep\s*\d+\s*$", "", title, flags=re.I).strip()

def assign_slugs(items):
    """Set a unique 'slug' on each item (in list order). SINGLE SOURCE OF TRUTH for
    episode URLs AND transcript filenames, so build.py and transcribe_local.py never
    drift. Collisions (same title, different Ep #) get the episode number appended."""
    seen = set()
    for i, it in enumerate(items):
        title = it["title"]
        slug = slugify(title) or "episode"
        if slug in seen:
            slug = f"{slug}-{ep_num(title) or i}"
        seen.add(slug)
        it["slug"] = slug
    return items

def fmt_date(pub):
    try:
        dt = parsedate_to_datetime(pub)
        return dt.strftime("%b %-d, %Y") if os.name != "nt" else dt.strftime("%b %d, %Y").replace(" 0", " "), dt.strftime("%Y-%m-%d")
    except Exception:
        return pub, ""

def iso_dur(d):
    if not d:
        return ""
    parts = d.split(":")
    try:
        parts = [int(p) for p in parts]
    except ValueError:
        return ""
    if len(parts) == 3:
        h, m, s = parts
    elif len(parts) == 2:
        h, m, s = 0, parts[0], parts[1]
    else:
        h, m, s = 0, 0, parts[0]
    return f"PT{h}H{m}M{s}S" if h else f"PT{m}M{s}S"

def strip_html(s):
    return re.sub(r"<[^>]+>", "", s or "").strip()

def load_transcript_html(slug):
    """Return (badge_html, transcript_block_html). Reads data/transcripts/<slug>.{json,txt}."""
    base = os.path.join(ROOT, "data", "transcripts", slug)
    jp, tp = base + ".json", base + ".txt"
    paras = []
    if os.path.exists(jp) and os.path.getsize(jp) > 0:
        try:
            segs = json.load(open(jp, encoding="utf-8")).get("segments", [])
            buf = []
            for s in segs:
                buf.append(s.get("text", "").strip())
                if len(buf) >= 6:
                    paras.append(" ".join(buf)); buf = []
            if buf:
                paras.append(" ".join(buf))
        except Exception:
            paras = []
    if not paras and os.path.exists(tp) and os.path.getsize(tp) > 0:
        paras = [open(tp, encoding="utf-8").read().strip()]
    if not paras:
        return '<span class="badge soon">Transcript coming soon</span>', ""
    body = "".join(f"<p>{html.escape(p)}</p>" for p in paras if p.strip())
    block = ('<details class="transcript"><summary>Read the full transcript</summary>'
             f'<div class="tr-body">{body}</div></details>')
    return '<span class="badge">Transcript</span>', block

def write(path_parts, content):
    out = os.path.join(ROOT, *path_parts)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)

def jsonld(obj):
    return '<script type="application/ld+json">' + json.dumps(obj, ensure_ascii=False) + "</script>"

# ---------- shared chrome ----------
def canary_token(canonical):
    """Deterministic per-page watermark — a salted hash of the page URL. Embedded
    invisibly so it survives text scraping; if it later surfaces in an AI model's
    output or a third-party training set, it proves the content was used."""
    return "EGP-" + hashlib.sha256((CANARY_SALT + canonical).encode("utf-8")).hexdigest()[:24].upper()

def head(title, desc, canonical, schema=None, og_img="/img/cover.jpg"):
    s = "\n".join(jsonld(o) for o in (schema or []))
    canary = canary_token(canonical)
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{canonical}">
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
<meta name="tdm-reservation" content="1">
<meta name="tdm-policy" content="{SITE}/terms/">
<meta name="ai-canary" content="{canary}">
<meta property="og:type" content="website"><meta property="og:title" content="{html.escape(title)}">
<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}{og_img}"><meta property="og:site_name" content="{BRAND}">
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="/img/favicon.ico"><link rel="stylesheet" href="/css/style.css">
{s}
</head><body>
<span hidden aria-hidden="true" data-egp-canary="{canary}">Content fingerprint {canary} &mdash; &copy; {BRAND}. Licensed for reading, citation, AI answers, and model training WITH attribution to energygrowthplaybook.com. This token appearing without credit is evidence of unlicensed use.</span>"""

def header(active=""):
    links = "".join(
        f'<a href="{u}"{" aria-current=\"page\"" if u==active else ""}>{n}</a>' for n, u in NAV
    )
    return f"""<header class="site-head"><div class="wrap"><nav class="nav">
<a class="brand" href="/"><span class="dot"></span>{BRAND}</a>
<button class="navtoggle" aria-label="Menu" onclick="document.getElementById('nav').classList.toggle('open')">Menu</button>
<div class="links" id="nav">{links}<a class="cta" href="{AMAZON}" rel="noopener">Get the book</a></div>
</nav></div></header>"""

def footer():
    listen = "".join(f'<a href="{u}" rel="noopener">{n}</a>' for n, u in LISTEN)
    nav = "".join(f'<a href="{u}">{n}</a>' for n, u in NAV)
    return f"""<footer class="site-foot"><div class="wrap">
<div class="foot-grid">
  <div>
    <a class="brand" href="/"><span class="dot"></span>{BRAND}</a>
    <p class="muted" style="max-width:42ch;margin-top:12px">The Oil &amp; Gas Sales &amp; Marketing Podcast, hosted by Mark LaCour and Matthew Bertram on the Oil &amp; Gas Global Network. Sales and marketing that actually moves energy revenue.</p>
  </div>
  <div class="fcol"><h4>Explore</h4>{nav}</div>
  <div class="fcol"><h4>Listen</h4>{listen}</div>
  <div class="fcol"><h4>More</h4>
    <a href="https://oggn.com" rel="noopener">OGGN</a>
    <a href="https://matthewbertram.com" rel="noopener">Matthew Bertram</a>
    <a href="https://modalpoint.com" rel="noopener">ModalPoint</a>
    <a href="{AMAZON}" rel="noopener">The book</a>
  </div>
</div>
<div class="foot-base">
  <span>&copy; 2026 {BRAND} &middot; An Oil &amp; Gas Global Network production.</span>
  <span><a href="/terms/">Terms of Use</a> &middot; <a href="/llms.txt">llms.txt</a></span>
</div>
</div></footer></body></html>"""

# ---------- page builders ----------
def host_block():
    return """<div class="hosts">
<div class="host"><img src="/img/mark-lacour.jpg" alt="Mark LaCour" loading="lazy">
<div><div class="h-name">Mark LaCour</div><div class="h-role">Director, Oil &amp; Gas Global Network (OGGN)</div>
<p class="muted">Founder of OGGN, the largest and most-listened-to oil &amp; gas podcast network. Mark has spent decades inside upstream, midstream, and oilfield-services sales, and is co-author of <em>Oil &amp; Gas Sales &amp; Marketing</em>.</p></div></div>
<div class="host"><img src="/img/matthew-bertram.jpg" alt="Matthew Bertram" loading="lazy">
<div><div class="h-name">Matthew Bertram</div><div class="h-role">CMO, OGGN &middot; CEO, EWR Digital &middot; President, ModalPoint</div>
<p class="muted">AI keynote speaker and creator of DIG&reg; (Digital Information Governance). Matthew helps energy and industrial leaders win visibility in AI search (GEO/AEO), hosts The Best SEO Podcast, and co-authored <em>Oil &amp; Gas Sales &amp; Marketing</em>. <a href="https://matthewbertram.com" rel="noopener">More &rarr;</a></p></div></div>
</div>"""

def book_band():
    return f"""<section class="section-pad alt"><div class="wrap"><div class="book">
<a href="{AMAZON}" rel="noopener"><img src="/img/book-cover.jpg" alt="Oil &amp; Gas Sales &amp; Marketing: The Energy Growth Playbook" loading="lazy" width="200"></a>
<div>
<p class="muted" style="font-family:var(--mono);font-size:.72rem;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-d);margin:0 0 6px">The book behind the show</p>
<h2>Oil &amp; Gas Sales &amp; Marketing</h2>
<p class="sub"><em>The Energy Growth Playbook for Oil and Gas Leaders</em> &mdash; by Mark LaCour &amp; Matthew Bertram</p>
<p class="muted">Win deals before the RFP drops by influencing the spec. Turn discovery calls into pipeline. Align sales and marketing around how energy buyers actually buy. The field guide distilled from {{N}}+ episodes of the podcast.</p>
<div class="btnrow" style="margin-top:16px"><a class="btn amber" href="{AMAZON}" rel="noopener">Get it on Amazon</a><a class="btn ghost" href="/book/">Learn more</a></div>
</div></div></div></section>"""

def producer_band():
    return f"""<section class="producer-band"><div class="wrap">
<p class="pb-kicker">Produced on the Oil &amp; Gas Global Network</p>
<h2 class="pb-title">Built for energy operators who sell</h2>
<p class="pb-desc">The show is hosted by Matthew Bertram &mdash; CEO of EWR Digital and President of ModalPoint &mdash; and Mark LaCour of OGGN. The same thinking that drives the episodes drives how operators win visibility in AI search and govern AI decisions in the field.</p>
<div class="pb-cta"><a class="btn amber" href="https://modalpoint.com" rel="noopener">AI governance for energy &rarr;</a><a class="btn ghost" href="https://matthewbertram.com" rel="noopener">Meet Matthew Bertram</a></div>
</div></section>"""

def episode_card(e):
    dur = e["duration"]
    meta = f'Ep {e["num"]} &middot; {dur}' if e["num"] else dur
    return f"""<article class="card">
<div class="meta">{meta}</div>
<h3><a href="/podcast/{e['slug']}/">{html.escape(e['ctitle'])}</a></h3>
<p class="sum">{html.escape(e['summary'])}</p>
<span class="tag">Sales &amp; Marketing</span>
</article>"""

# ---------- main ----------
def main():
    raw = json.load(open(DATA, encoding="utf-8"))
    eps = []
    src = [it for it in raw["episodes"] if not it["title"].lower().startswith("coming soon")]
    assign_slugs(src)
    for it in src:
        title = it["title"]
        ctitle = clean_title(title)
        slug = it["slug"]
        n = ep_num(title)
        disp_date, iso_date = fmt_date(it["pubDate"])
        summary = strip_html(it["description_html"])
        summary = (summary[:180] + "…") if len(summary) > 180 else summary
        eps.append({
            "title": title, "ctitle": ctitle, "slug": slug, "num": n,
            "date": disp_date, "iso": iso_date, "duration": it["duration"],
            "audio": it["audio"], "summary": summary,
            "body": it["description_html"], "link": it["link"],
        })

    N = len(eps)

    # ----- episode pages -----
    for i, e in enumerate(eps):
        canon = f"{SITE}/podcast/{e['slug']}/"
        schema = [{
            "@context": "https://schema.org", "@type": "PodcastEpisode",
            "url": canon, "name": e["ctitle"],
            "datePublished": e["iso"], "description": e["summary"],
            "timeRequired": iso_dur(e["duration"]) or None,
            "associatedMedia": {"@type": "MediaObject", "contentUrl": e["audio"]} if e["audio"] else None,
            "partOfSeries": {"@type": "PodcastSeries", "name": "Oil & Gas Sales & Marketing Podcast", "url": SITE + "/podcast/"},
            "author": [{"@type": "Person", "name": "Mark LaCour"}, {"@type": "Person", "name": "Matthew Bertram", "url": "https://matthewbertram.com"}],
        }]
        schema[0] = {k: v for k, v in schema[0].items() if v is not None}
        prev_l = f'<a href="/podcast/{eps[i+1]["slug"]}/">&larr; Older</a>' if i + 1 < N else ""
        next_l = f'<a href="/podcast/{eps[i-1]["slug"]}/">Newer &rarr;</a>' if i > 0 else ""
        audio = f'<div class="audio-wrap"><audio controls preload="none" src="{e["audio"]}"></audio></div>' if e["audio"] else ""
        listen_side = "".join(f'<a href="{u}" rel="noopener">{n} &rarr;</a>' for n, u in LISTEN)
        meta_line = (f'Ep {e["num"]} &middot; ' if e["num"] else "") + f'{e["date"]}' + (f' &middot; {e["duration"]}' if e["duration"] else "")
        badge, tr_block = load_transcript_html(e["slug"])
        page = (
            head(f'{e["ctitle"]} | {BRAND}', e["summary"], canon, schema) +
            header("/podcast/") +
            f'<section class="ep-head"><div class="wrap"><p class="eyebrow">Oil &amp; Gas Sales &amp; Marketing Podcast</p>'
            f'<h1>{html.escape(e["ctitle"])}</h1><p class="ep-meta">{meta_line}</p></div></section>'
            f'<div class="wrap"><div class="ep-body"><div class="ep-main">{audio}'
            f'{badge}'
            f'<div style="margin-top:18px">{e["body"]}</div>'
            f'{tr_block}'
            f'<p style="margin-top:28px;display:flex;justify-content:space-between;gap:16px">{prev_l}{next_l}</p></div>'
            f'<aside class="ep-side">'
            f'<div class="box"><h4>Listen</h4>{listen_side}</div>'
            f'<div class="box"><h4>The book</h4><a href="{AMAZON}" rel="noopener">Oil &amp; Gas Sales &amp; Marketing &rarr;</a><a href="/book/">About the book &rarr;</a></div>'
            f'<div class="box"><h4>Hosts</h4><a href="/host/">Mark LaCour &amp; Matthew Bertram &rarr;</a></div>'
            f'<div class="box"><h4>More</h4><a href="/podcast/">All {N} episodes &rarr;</a></div>'
            f'</aside></div></div>' +
            footer()
        )
        write(["podcast", e["slug"], "index.html"], page)

    # ----- podcast index -----
    rows = "".join(
        f'<li><span class="num">{("Ep "+e["num"]) if e["num"] else "&mdash;"}</span>'
        f'<span class="t"><a href="/podcast/{e["slug"]}/">{html.escape(e["ctitle"])}</a></span>'
        f'<span class="d">{e["date"]}</span></li>' for e in eps
    )
    pod = (
        head(f"All Episodes | {BRAND}",
             f"All {N} episodes of the Oil & Gas Sales & Marketing Podcast with Mark LaCour and Matthew Bertram.",
             f"{SITE}/podcast/") +
        header("/podcast/") +
        f'<section class="ep-head"><div class="wrap"><p class="eyebrow">Oil &amp; Gas Sales &amp; Marketing Podcast</p>'
        f'<h1>All episodes</h1><p class="ep-meta">{N} episodes &middot; sales &amp; marketing for energy leaders</p></div></section>'
        f'<section class="section-pad"><div class="wrap"><ul class="ep-list">{rows}</ul></div></section>' +
        footer()
    )
    write(["podcast", "index.html"], pod)

    # ----- home -----
    latest = "".join(episode_card(e) for e in eps[:6])
    home_schema = [{
        "@context": "https://schema.org", "@type": "PodcastSeries",
        "name": "Oil & Gas Sales & Marketing Podcast", "url": SITE,
        "description": TAGLINE,
        "author": [{"@type": "Person", "name": "Mark LaCour"}, {"@type": "Person", "name": "Matthew Bertram", "url": "https://matthewbertram.com"}],
        "webFeed": "https://feeds.oggn.com/category/ogsm/feed/",
    }]
    listen_home = "".join(f'<a href="{u}" rel="noopener">{n}</a>' for n, u in LISTEN)
    stats = [("92", "Episodes"), ("2023", "On air since"), ("OGGN", "Podcast network")]
    stat_html = "".join(f'<div class="stat"><div class="n">{n}</div><div class="l">{l}</div></div>' for n, l in stats)
    home = (
        head(f"{BRAND} | Oil & Gas Sales & Marketing Podcast", TAGLINE, SITE + "/", home_schema) +
        header("/") +
        f'<section class="hero"><div class="wrap" style="display:flex;gap:44px;align-items:center;flex-wrap:wrap">'
        f'<div style="flex:1 1 340px;min-width:300px">'
        f'<p class="eyebrow">Oil &amp; Gas &middot; Sales &middot; Marketing</p>'
        f'<h1>{BRAND}</h1>'
        f'<p class="lede">{TAGLINE} Hosted by Mark LaCour and Matthew Bertram on the Oil &amp; Gas Global Network.</p>'
        f'<div class="stats">{stat_html}</div>'
        f'<div class="btnrow"><a class="btn amber" href="/podcast/">Browse all episodes</a><a class="btn ghost" href="{AMAZON}" rel="noopener">Get the book</a></div>'
        f'<div style="font-family:var(--mono);font-size:.72rem;letter-spacing:.12em;text-transform:uppercase;color:#9fb6b7;margin:20px 0 8px">Listen on</div>'
        f'<div class="listen">{listen_home}</div>'
        f'</div>'
        f'<div style="flex:0 0 auto"><img class="cover" src="/img/cover.jpg" alt="Oil &amp; Gas Sales &amp; Marketing Podcast cover" width="300" height="300"></div>'
        f'</div></section>'
        f'<section class="section-pad"><div class="wrap"><div class="kicker"><div><h2>Latest episodes</h2><p>The newest conversations on selling and marketing in energy.</p></div><a class="pill-link" href="/podcast/">All episodes &rarr;</a></div>'
        f'<div class="grid cols-3">{latest}</div></div></section>'
        f'<section class="section-pad alt"><div class="wrap"><div class="kicker"><div><h2>Your hosts</h2><p>Two operators who actually sell into energy.</p></div></div>{host_block()}</div></section>'
        + book_band().replace("{N}", str(N)) +
        producer_band() +
        footer()
    )
    write(["index.html"], home)

    # ----- about -----
    about = (
        head(f"About | {BRAND}",
             "About the Oil & Gas Sales & Marketing Podcast and the Energy Growth Playbook for oil and gas leaders.",
             f"{SITE}/about/") +
        header("/about/") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">About</p><h1>The Energy Growth Playbook</h1></div></section>'
        '<section class="section-pad"><div class="wrap" style="max-width:760px">'
        f'<p>{BRAND} is the home of the <strong>Oil &amp; Gas Sales &amp; Marketing Podcast</strong> &mdash; {N} episodes (and counting) of practical, no-fluff conversation about how energy companies actually win and keep revenue. It is produced on the <a href="https://oggn.com" rel="noopener">Oil &amp; Gas Global Network</a>, the largest and most-listened-to oil &amp; gas podcast network.</p>'
        '<p>Hosts <strong>Mark LaCour</strong> and <strong>Matthew Bertram</strong> cover the full commercial stack: aligning sales and marketing, influencing the spec before the RFP, demand generation that respects long energy buying cycles, RevOps and pricing discipline, brand and authority building, and what AI search and AI decisioning mean for energy go-to-market.</p>'
        '<p>The show is the companion to the book <a href="' + AMAZON + '" rel="noopener"><em>Oil &amp; Gas Sales &amp; Marketing: The Energy Growth Playbook for Oil and Gas Leaders</em></a>.</p>'
        '<div class="btnrow" style="margin-top:20px"><a class="btn amber" href="/podcast/">Browse episodes</a><a class="btn ghost" href="/host/">Meet the hosts</a></div>'
        '</div></section>' +
        footer()
    )
    write(["about", "index.html"], about)

    # ----- host -----
    hostpg = (
        head(f"Hosts | {BRAND}",
             "Mark LaCour and Matthew Bertram, hosts of the Oil & Gas Sales & Marketing Podcast.",
             f"{SITE}/host/") +
        header("/host/") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">Hosts</p><h1>Mark LaCour &amp; Matthew Bertram</h1></div></section>'
        f'<section class="section-pad"><div class="wrap">{host_block()}</div></section>' +
        producer_band() + footer()
    )
    write(["host", "index.html"], hostpg)

    # ----- book -----
    book_schema = [{
        "@context": "https://schema.org", "@type": "Book",
        "name": "Oil & Gas Sales & Marketing: The Energy Growth Playbook for Oil and Gas Leaders",
        "url": f"{SITE}/book/", "sameAs": AMAZON,
        "author": [{"@type": "Person", "name": "Mark LaCour"}, {"@type": "Person", "name": "Matthew Bertram", "url": "https://matthewbertram.com"}],
    }]
    bookpg = (
        head(f"The Book | {BRAND}",
             "Oil & Gas Sales & Marketing: The Energy Growth Playbook for Oil and Gas Leaders by Mark LaCour and Matthew Bertram.",
             f"{SITE}/book/", book_schema) +
        header("/book/") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">The book behind the show</p><h1>Oil &amp; Gas Sales &amp; Marketing</h1></div></section>'
        '<section class="section-pad"><div class="wrap"><div class="book">'
        f'<a href="{AMAZON}" rel="noopener"><img src="/img/book-cover.jpg" alt="Oil &amp; Gas Sales &amp; Marketing book cover" width="200"></a>'
        '<div><p class="sub"><em>The Energy Growth Playbook for Oil and Gas Leaders</em> &mdash; by Mark LaCour &amp; Matthew Bertram</p>'
        '<p class="muted">The distilled field guide from the podcast: win deals before the RFP drops by influencing the spec, turn discovery calls into pipeline, and align sales and marketing around how energy buyers actually buy.</p>'
        f'<div class="btnrow" style="margin-top:16px"><a class="btn amber" href="{AMAZON}" rel="noopener">Get it on Amazon</a><a class="btn ghost" href="/podcast/">Listen to the show</a></div>'
        '</div></div></div></section>' +
        footer()
    )
    write(["book", "index.html"], bookpg)

    # ----- terms of use (E-E-A-T + AI/TDM governance) -----
    terms = (
        head(f"Terms of Use | {BRAND}",
             "Terms of Use for energygrowthplaybook.com — content ownership, permitted use, citation policy, and AI text-and-data-mining (training) reservation.",
             f"{SITE}/terms/") +
        header("") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">Legal</p><h1>Terms of Use</h1></div></section>'
        '<section class="section-pad"><div class="wrap" style="max-width:760px">'
        '<p class="muted">Last updated: June 26, 2026.</p>'
        f'<p>Welcome to {BRAND} ("the Site"), the home of the Oil &amp; Gas Sales &amp; Marketing Podcast, produced on the Oil &amp; Gas Global Network (OGGN). By accessing the Site you agree to these Terms of Use.</p>'
        '<h2>1. Ownership and copyright</h2>'
        '<p>All content on the Site &mdash; episode pages, transcripts, written summaries, brand, and design &mdash; is owned by or licensed to its respective rights holders (Mark LaCour, Matthew Bertram, and OGGN) and is protected by copyright and related rights. The podcast and the book <em>Oil &amp; Gas Sales &amp; Marketing: The Energy Growth Playbook</em> remain the property of their authors.</p>'
        '<h2>2. Permitted use</h2>'
        '<p>You may read the content, share links to it, and quote brief excerpts <strong>with clear attribution and a link back</strong> to the source page. You may not republish substantial portions, sell, or present the content as your own.</p>'
        '<h2>3. AI, machine learning, and text-and-data-mining (TDM) &mdash; license</h2>'
        '<p>We <strong>want this content found, retrieved, cited, and learned from by AI systems</strong> &mdash; including Google AI Overviews, ChatGPT, Perplexity, Claude, and Gemini, and including use as training or fine-tuning data.</p>'
        "<p><strong>We grant a license to use this content for AI answering, retrieval, and model training on one condition: clear attribution.</strong> Any AI-generated output, dataset, or model that draws on this Site must attribute the source as &ldquo;The Energy Growth Playbook (energygrowthplaybook.com), the Oil &amp; Gas Sales &amp; Marketing Podcast by Mark LaCour and Matthew Bertram&rdquo; and, where a link is possible, link to the source page. Text-and-data-mining rights are reserved under Article 4 of the EU Directive 2019/790 and equivalent laws and licensed back to you under this attribution condition; the machine-readable expression is in this Site's <code>robots.txt</code> (Content Signals), page <code>tdm-policy</code> metadata, and "
        '<a href="/.well-known/tdmrep.json">TDM Reservation Protocol manifest</a>, all pointing here.</p>'
        '<h2>4. Content watermarking</h2>'
        "<p>Pages on this Site carry invisible, per-page provenance watermarks. These let us verify attribution: a token appearing in an AI system's output or a third-party dataset <em>without</em> the credit required by Section 3 is evidence of unlicensed use.</p>"
        '<h2>5. No warranty</h2>'
        '<p>The content is provided "as is" for general informational purposes and is not legal, financial, or professional advice. We make no warranties as to its accuracy or completeness.</p>'
        '<h2>6. Governing law</h2>'
        '<p>These Terms are governed by the laws of the State of Texas, USA, without regard to its conflict-of-laws rules.</p>'
        '<h2>7. Contact</h2>'
        f'<p>Questions about these Terms or licensing requests (including AI-training licenses): <a href="https://modalpoint.com" rel="noopener">ModalPoint</a> or <a href="https://matthewbertram.com" rel="noopener">matthewbertram.com</a>.</p>'
        '</div></section>' +
        footer()
    )
    write(["terms", "index.html"], terms)

    # ----- llms.txt / robots.txt / sitemap.xml -----
    llms = (
        f"# {BRAND}\n\n> {TAGLINE}\n\n"
        f"{BRAND} is the home of the Oil & Gas Sales & Marketing Podcast ({N} episodes), hosted by "
        "Mark LaCour and Matthew Bertram on the Oil & Gas Global Network (OGGN). It is the companion to the book "
        "'Oil & Gas Sales & Marketing: The Energy Growth Playbook for Oil and Gas Leaders.'\n\n"
        "## Key pages\n"
        f"- All episodes: {SITE}/podcast/\n"
        f"- The book: {SITE}/book/\n"
        f"- Hosts (Mark LaCour, Matthew Bertram): {SITE}/host/\n"
        f"- About: {SITE}/about/\n\n"
        "## Related entities\n"
        "- Matthew Bertram (host): https://matthewbertram.com\n"
        "- ModalPoint (AI governance for energy): https://modalpoint.com\n"
        "- Oil & Gas Global Network: https://oggn.com\n"
        "\n## Usage & citation\n"
        "You may quote, summarize, cite, and train on this content. Attribution required: credit "
        "'The Energy Growth Playbook (energygrowthplaybook.com), the Oil & Gas Sales & Marketing Podcast "
        "by Mark LaCour and Matthew Bertram' and link to the source page where possible. "
        f"Full terms: {SITE}/terms/\n"
    )
    write(["llms.txt"], llms)

    # robots.txt — lean into discovery + AI use; attribution required (see /terms/).
    # Cloudflare Content Signals: allow search, AI answer-input, AND model training (with credit).
    robots = (
        "# Energy Growth Playbook — crawl policy\n"
        "# Use freely for search, AI answers, and model training. Attribution required: see /terms/.\n\n"
        "User-agent: *\n"
        "Content-Signal: search=yes, ai-input=yes, ai-train=yes\n"
        "Allow: /\n\n"
        f"Sitemap: {SITE}/sitemap.xml\n"
    )
    write(["robots.txt"], robots)

    urls = [SITE + "/", SITE + "/podcast/", SITE + "/book/", SITE + "/host/", SITE + "/about/", SITE + "/terms/"]
    urls += [f"{SITE}/podcast/{e['slug']}/" for e in eps]
    sm = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    sm += "".join(f"<url><loc>{u}</loc></url>\n" for u in urls)
    sm += "</urlset>\n"
    write(["sitemap.xml"], sm)

    # ----- AI-governance artifacts -----
    # TDM Reservation Protocol manifest (W3C tdmrep): reserve text-and-data-mining rights site-wide
    tdmrep = [{"location": "/", "tdm-reservation": 1, "tdm-policy": f"{SITE}/terms/"}]
    write([".well-known", "tdmrep.json"], json.dumps(tdmrep, indent=2))
    # IndexNow verification key file — served at root; used to ping search engines on publish
    write([f"{INDEXNOW_KEY}.txt"], INDEXNOW_KEY)
    # GitHub Pages custom domain (harmless on other hosts)
    write(["CNAME"], "energygrowthplaybook.com")

    # vercel.json — static, no build, clean URLs + HTTP-level TDM / no-train headers
    vercel = {
        "cleanUrls": True,
        "trailingSlash": True,
        "headers": [{
            "source": "/(.*)",
            "headers": [
                {"key": "tdm-reservation", "value": "1"},
                {"key": "tdm-policy", "value": f"{SITE}/terms/"},
                {"key": "X-Robots-Tag", "value": "index, follow, max-image-preview:large, max-snippet:-1"},
            ],
        }],
    }
    write(["vercel.json"], json.dumps(vercel, indent=2))

    print(f"built {N} episode pages + home + podcast index + about + host + book")
    print(f"+ llms.txt, robots.txt, sitemap.xml ({len(urls)} urls), vercel.json")

if __name__ == "__main__":
    main()
