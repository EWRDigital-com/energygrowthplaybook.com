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
NAV = [("Episodes", "/podcast/"), ("Answers", "/answers/"), ("Topics", "/topics/"), ("The Book", "/book/"), ("Hosts", "/host/"), ("About", "/about/")]

# Answer-first AEO pages — the questions energy buyers/sellers actually ask. Each renders
# as a FAQPage with schema so AI answer engines (AI Overviews, ChatGPT, Perplexity) can cite it.
ANSWERS = [
  {"slug":"how-to-sell-to-oil-and-gas-companies",
   "q":"How do you sell to oil and gas companies?",
   "summary":"Selling to oil & gas means winning a long, committee-driven, risk-averse buying process: get specified in early and prove you cut downtime and total cost.",
   "a":[
     "Selling to oil and gas companies means selling into a long, committee-driven, safety- and uptime-obsessed buying process &mdash; not a quick transaction. The companies that win get <strong>specified into the project before the RFP is written</strong>, earn trust with both the technical buyer (engineering and operations) and the economic buyer (procurement), and prove they reduce risk, downtime, and total cost of ownership.",
     "Generic, high-volume outreach fails in energy. What works is domain credibility, relationships, and being present where operators actually learn &mdash; industry podcasts, trade events, referrals, and approved-vendor lists. Because budgets follow capital cycles and the oil price, the strongest sellers build pipeline continuously rather than reacting when a bid drops.",
     "In short: lead with how you de-risk the operation, get in before the spec is locked, and build the authority that shortens the long trust-building phase of an energy sale."]},
  {"slug":"oil-and-gas-sales-cycle",
   "q":"What does the oil and gas sales cycle (buying process) look like?",
   "summary":"Long (6-18+ months), multi-stakeholder, gated by capital cycles, safety qualification, and procurement, with spec development the highest-leverage stage.",
   "a":[
     "The oil and gas buying process is long &mdash; often 6 to 18 months or more &mdash; multi-stakeholder, and gated by capital budgets, safety and qualification requirements, and procurement. It typically moves through problem recognition, <strong>spec development</strong> (the highest-leverage moment to influence), vendor qualification and approval, RFP or bid, procurement negotiation, award, and onboarding.",
     "Two things make it distinct from ordinary B2B: the process is heavily risk- and compliance-driven (a failure can mean downtime, safety incidents, or lost production), and it is sensitive to the capital cycle and commodity price. Deals stall and accelerate with forces outside the seller's control.",
     "The practical implication: build relationships and authority continuously, influence the requirements before procurement formalizes them, and keep a full pipeline so you are not dependent on any single long-cycle deal."]},
  {"slug":"marketing-for-oilfield-services",
   "q":"How do you market oilfield services?",
   "summary":"Oilfield-services marketing builds technical authority and trust with a narrow, high-value audience: case studies with hard numbers, thought leadership where operators are, and ABM.",
   "a":[
     "Marketing oilfield services is about building <strong>technical authority and trust with a narrow, high-value audience</strong> &mdash; not mass reach. The buyers are engineers, operations leaders, and procurement at a finite set of operators, so credibility and specificity beat volume every time.",
     "What works: case studies with hard numbers (non-productive time reduced, dollars per barrel saved, HSE outcomes), thought leadership where operators actually consume content (industry podcasts, LinkedIn, and trade media), getting onto approved-vendor lists, and account-based marketing aimed at named operators. Brand and visibility do real work here &mdash; they shorten the trust-building phase of a long, high-stakes sale.",
     "The goal of oilfield-services marketing is not lead volume; it is familiarity and authority, so that when a buyer has a problem, your company is already the trusted name they call."]},
  {"slug":"influence-the-spec-before-the-rfp",
   "q":"How do you influence the spec before the RFP in energy sales?",
   "summary":"Be in the conversation during problem-definition and spec-writing: educate engineers early so your approach is written into the requirements before procurement formalizes them.",
   "a":[
     "You influence the spec by <strong>being in the conversation during the problem-definition and spec-writing phase, before procurement formalizes the requirements</strong>. That means educating engineers and operations early, providing reference designs, technical content, and a clear point of view, and becoming the trusted advisor whose approach gets written into the requirements.",
     "This matters because once an RFP is published, the specification often already favors whoever helped shape it. Competing after that point usually becomes a price game against requirements built around someone else's solution.",
     "Practically: invest in upstream relationships and education, publish content that frames the problem the way your solution solves it, and measure success by how often your thinking shows up in the requirements &mdash; not just how many bids you respond to."]},
  {"slug":"align-sales-and-marketing-in-energy",
   "q":"How do you align sales and marketing in an energy or industrial company?",
   "summary":"Point both teams at the buyer's real journey and a shared definition of a qualified opportunity: marketing creates authority so sales enters warm, and feeds the technical content each stage needs.",
   "a":[
     "You align sales and marketing by pointing both at the <strong>buyer's actual journey and a shared definition of a qualified opportunity</strong> &mdash; not at lead volume. In energy and industrial companies, marketing's real job is to create familiarity and authority so sales enters warm conversations, and to supply the technical content sales needs at each stage of a long cycle.",
     "The mechanics that keep them aligned: shared pipeline metrics (not vanity leads), regular feedback loops where sales tells marketing what buyers actually ask, and content built from real sales conversations and podcast episodes. When marketing is measured on pipeline and revenue contribution, the friction between the two teams largely disappears.",
     "Done right, the line between sales and marketing blurs into one revenue motion: marketing warms and educates, sales advises and closes, and both work from the same view of the customer."]},
  {"slug":"ai-search-aeo-for-energy-companies",
   "q":"How do energy companies get found in AI search (AEO / GEO)?",
   "summary":"AI answer engines increasingly mediate B2B energy research. Earn citations with answer-first content, schema, crawler access, and entity authority. Classic ranking is not the same as AI-answer visibility.",
   "a":[
     "Energy companies get found in AI search by <strong>earning the citation</strong>, not just ranking. AI answer engines (Google AI Overviews, ChatGPT, Perplexity, Gemini) increasingly mediate B2B research, including in energy, and they synthesize answers from sources they trust rather than returning a list of links.",
     "The levers: publish clear, <strong>answer-first content</strong> for the specific questions buyers ask; structure it with schema so machines can parse it; make sure AI crawlers can access it; and build entity authority &mdash; consistent brand and person signals, citations, and being referenced across the web. A tracked question with no page that answers it is a guaranteed zero in AI presence.",
     "Classic SEO ranking does not equal AI-answer visibility, and this is exactly the discipline ModalPoint and Matt Bertram work on: making energy and industrial brands the source AI engines cite. Learn more at <a href='https://modalpoint.com' rel='noopener'>ModalPoint</a> and <a href='https://matthewbertram.com' rel='noopener'>matthewbertram.com</a>."]},
]

# Glossary terms — definitional content for "what is X" AI-answer queries (DefinedTermSet schema).
GLOSSARY = [
  ("Answer Engine Optimization (AEO)", "Optimizing content so AI answer engines &mdash; Google AI Overviews, ChatGPT, Perplexity &mdash; cite it directly in their answers. Unlike classic SEO, the goal is to be the source the AI quotes, not just a blue link."),
  ("Generative Engine Optimization (GEO)", "A near-synonym for AEO: shaping content and entity signals so generative AI systems surface and attribute your brand when users ask questions."),
  ("Speccing in (spec influence)", "Getting your product or approach written into a project's technical specification before the RFP is issued. In energy sales it is the highest-leverage move &mdash; the spec often decides the winner before bidding starts."),
  ("Approved Vendor List (AVL)", "A pre-qualified list of suppliers an operator is allowed to buy from. Getting onto the AVL is a gate that must be cleared before most oil and gas deals can even begin."),
  ("Upstream, midstream, downstream", "The three segments of the oil and gas value chain: upstream is exploration and production; midstream is transport and storage (pipelines, terminals); downstream is refining, processing, and distribution."),
  ("Oilfield services (OFS)", "Companies that provide the equipment, technology, and services that exploration-and-production operators need to drill and produce. A long-cycle, relationship-driven B2B market."),
  ("Exploration and Production (E&amp;P)", "The upstream operators who find and extract oil and gas. They are the ultimate buyers most oilfield-services and energy-tech companies are selling to."),
  ("Request for Proposal (RFP)", "A formal procurement document inviting vendors to bid against a defined specification. By the time an RFP is issued, the spec &mdash; and often the likely winner &mdash; is largely set."),
  ("Non-productive time (NPT)", "Time when a rig or operation is not producing due to equipment failure, waiting, or problems. Reducing NPT is one of the most persuasive value propositions in oilfield sales."),
  ("Total cost of ownership (TCO)", "The full lifetime cost of a solution &mdash; purchase, install, operate, maintain, downtime &mdash; not just the sticker price. Energy buyers evaluate on TCO and risk, which is why the lowest bid does not always win."),
  ("Revenue Operations (RevOps)", "Aligning sales, marketing, and customer success around one revenue process and shared data, so the long energy buying journey is not fragmented across teams."),
  ("Demand generation", "Marketing activity that creates awareness and interest among future buyers. It matters in energy because buying cycles are long, so demand must be built continuously, not on demand."),
  ("Account-based marketing (ABM)", "Targeting a defined set of high-value accounts (specific operators) with tailored marketing and sales, rather than chasing broad lead volume &mdash; well suited to the finite, high-value energy buyer universe."),
  ("Ideal Customer Profile (ICP)", "A precise definition of the accounts most likely to buy and succeed with your solution. In energy, a sharp ICP (by segment, basin, asset type) focuses scarce sales effort where it pays off."),
  ("Sales cycle", "The time and stages from first contact to closed deal. Energy sales cycles are unusually long (often 6 to 18+ months) and gated by capital budgets, qualification, and procurement."),
  ("Thought leadership", "Publishing genuinely useful expertise (podcasts, articles, talks) to build authority and trust ahead of the sale &mdash; a primary way energy and oilfield brands shorten the trust-building phase of a long cycle."),
]

# Topic cluster hubs — group answers + matching episodes for topical authority + internal linking.
TOPICS = [
  {"slug":"selling-to-energy","title":"Selling to Oil & Gas",
   "intro":"How to win deals in energy's long, committee-driven, risk-averse buying process — from getting specced in to closing.",
   "kw":["sell","selling","sales","deal","clos","prospect","pipeline","negotiat","cold"],
   "answers":["how-to-sell-to-oil-and-gas-companies","oil-and-gas-sales-cycle","influence-the-spec-before-the-rfp"]},
  {"slug":"energy-marketing","title":"Marketing for Energy & Oilfield Services",
   "intro":"Building authority, demand, and trust with a narrow, high-value energy audience.",
   "kw":["market","brand","content","demand","awareness","seo","linkedin","trade show","podcast","thought","awareness"],
   "answers":["marketing-for-oilfield-services","align-sales-and-marketing-in-energy"]},
  {"slug":"sales-marketing-alignment","title":"Sales & Marketing Alignment",
   "intro":"Pointing sales and marketing at one revenue motion built around how energy buyers actually buy.",
   "kw":["align","revops","sales and marketing","marketing and sales","joined","lead"],
   "answers":["align-sales-and-marketing-in-energy"]},
  {"slug":"ai-in-energy-gtm","title":"AI in Energy Go-To-Market",
   "intro":"What AI search, AI answer engines, and AI decisioning mean for how energy companies get found and sell.",
   "kw":["ai ","a.i","artificial intelligence","chatgpt","llm","aeo","geo","automation","digital","machine"],
   "answers":["ai-search-aeo-for-energy-companies"]},
  {"slug":"how-energy-companies-buy","title":"How Energy Companies Buy",
   "intro":"Inside the energy buyer: procurement, the spec, qualification, and the long capital-driven decision.",
   "kw":["buy","buying","buyer","procure","rfp","spec","decision","budget","capital","purchas"],
   "answers":["oil-and-gas-sales-cycle","influence-the-spec-before-the-rfp","how-to-sell-to-oil-and-gas-companies"]},
]

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
  <span><a href="/glossary/">Glossary</a> &middot; <a href="/topics/">Topics</a> &middot; <a href="/terms/">Terms of Use</a> &middot; <a href="/llms.txt">llms.txt</a></span>
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
<div class="btnrow" style="margin-top:16px"><a class="btn amber" href="{AMAZON}" rel="noopener">Get it on Amazon</a><a class="btn ghost" href="/podcast/">Listen to the show</a></div>
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

    # ----- answers (answer-first AEO pages w/ FAQPage schema) -----
    cards = []
    for a in ANSWERS:
        acanon = f"{SITE}/answers/{a['slug']}/"
        faq = [{
            "@context": "https://schema.org", "@type": "FAQPage",
            "mainEntity": [{"@type": "Question", "name": a["q"],
                "acceptedAnswer": {"@type": "Answer", "text": strip_html(" ".join(a["a"]))}}],
        }]
        body = "".join(f"<p>{p}</p>" for p in a["a"])
        related = "".join(
            f'<li><a href="/podcast/{e["slug"]}/">{html.escape(e["ctitle"])}</a></li>'
            for e in eps[:4]
        )
        page = (
            head(f'{a["q"]} | {BRAND}', a["summary"], acanon, faq) +
            header("/answers/") +
            f'<section class="ep-head"><div class="wrap"><p class="eyebrow">Answers</p><h1>{html.escape(a["q"])}</h1></div></section>'
            f'<div class="wrap"><div class="ep-body"><div class="ep-main"><div class="answer" style="font-size:1.05rem;line-height:1.7">{body}</div>'
            f'<div class="btnrow" style="margin-top:26px"><a class="btn amber" href="/podcast/">Hear it on the podcast</a><a class="btn ghost" href="{AMAZON}" rel="noopener">Get the book</a></div></div>'
            f'<aside class="ep-side"><div class="box"><h4>More answers</h4>'
            + "".join(f'<a href="/answers/{o["slug"]}/">{html.escape(o["q"])}</a>' for o in ANSWERS if o["slug"] != a["slug"])
            + '</div><div class="box"><h4>Recent episodes</h4><ul style="margin:0;padding-left:18px">' + related + '</ul></div>'
            f'<div class="box"><h4>The book</h4><a href="{AMAZON}" rel="noopener">Oil &amp; Gas Sales &amp; Marketing &rarr;</a></div></aside>'
            f'</div></div>' +
            footer()
        )
        write(["answers", a["slug"], "index.html"], page)
        cards.append(
            f'<li style="margin:0 0 16px;list-style:none"><a href="/answers/{a["slug"]}/" style="display:block;text-decoration:none">'
            f'<strong style="color:var(--deep)">{html.escape(a["q"])}</strong>'
            f'<span class="muted" style="display:block;margin-top:4px">{html.escape(a["summary"])}</span></a></li>'
        )
    answers_hub = (
        head(f"Answers: Oil & Gas Sales & Marketing | {BRAND}",
             "Straight, sourced answers on how oil & gas and energy companies actually buy, sell, and market — from the Energy Growth Playbook podcast and book.",
             f"{SITE}/answers/") +
        header("/answers/") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">Answers</p><h1>Oil &amp; Gas Sales &amp; Marketing &mdash; Answers</h1>'
        '<p class="ep-meta">Straight, sourced answers to how energy companies actually buy, sell, and market.</p></div></section>'
        f'<section class="section-pad"><div class="wrap" style="max-width:820px"><ul style="padding:0;margin:0">{"".join(cards)}</ul></div></section>' +
        footer()
    )
    write(["answers", "index.html"], answers_hub)

    # ----- topics (cluster hubs: answers + matching episodes) -----
    def match_eps(kws, limit=10):
        out = []
        for e in eps:
            t = e["title"].lower()
            if any(k in t for k in kws):
                out.append(e)
            if len(out) >= limit:
                break
        return out
    tcards = []
    for t in TOPICS:
        tcanon = f"{SITE}/topics/{t['slug']}/"
        rel_ans = [a for a in ANSWERS if a["slug"] in t["answers"]]
        rel_eps = match_eps(t["kw"])
        ans_html = "".join(f'<li><a href="/answers/{a["slug"]}/">{html.escape(a["q"])}</a></li>' for a in rel_ans)
        eps_html = "".join(f'<li><a href="/podcast/{e["slug"]}/">{html.escape(e["ctitle"])}</a></li>' for e in rel_eps) or '<li class="muted">More episodes soon.</li>'
        page = (
            head(f'{t["title"]} | {BRAND}', t["intro"], tcanon) +
            header("/topics/") +
            f'<section class="ep-head"><div class="wrap"><p class="eyebrow">Topic</p><h1>{html.escape(t["title"])}</h1><p class="ep-meta">{html.escape(t["intro"])}</p></div></section>'
            f'<section class="section-pad"><div class="wrap" style="max-width:820px">'
            f'<h2>Answers</h2><ul style="line-height:1.9;padding-left:18px">{ans_html}</ul>'
            f'<h2 style="margin-top:32px">Episodes on this topic</h2><ul style="line-height:1.9;padding-left:18px">{eps_html}</ul>'
            f'<div class="btnrow" style="margin-top:28px"><a class="btn amber" href="/podcast/">All episodes</a><a class="btn ghost" href="/glossary/">Glossary</a></div>'
            f'</div></section>' +
            footer()
        )
        write(["topics", t["slug"], "index.html"], page)
        tcards.append(f'<li style="margin:0 0 16px;list-style:none"><a href="/topics/{t["slug"]}/" style="display:block;text-decoration:none"><strong style="color:var(--deep)">{html.escape(t["title"])}</strong><span class="muted" style="display:block;margin-top:4px">{html.escape(t["intro"])}</span></a></li>')
    topics_hub = (
        head(f"Topics | {BRAND}",
             "Oil & gas sales and marketing by topic: selling to energy, marketing, sales-marketing alignment, AI in go-to-market, and how energy companies buy.",
             f"{SITE}/topics/") +
        header("/topics/") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">Topics</p><h1>Browse by topic</h1></div></section>'
        f'<section class="section-pad"><div class="wrap" style="max-width:820px"><ul style="padding:0;margin:0">{"".join(tcards)}</ul></div></section>' +
        footer()
    )
    write(["topics", "index.html"], topics_hub)

    # ----- glossary (DefinedTermSet schema) -----
    gschema = [{"@context": "https://schema.org", "@type": "DefinedTermSet",
                "name": "Oil & Gas Sales & Marketing Glossary", "url": f"{SITE}/glossary/",
                "hasDefinedTerm": [{"@type": "DefinedTerm", "name": re.sub(r"&amp;", "&", g[0]),
                                    "description": strip_html(g[1])} for g in GLOSSARY]}]
    gbody = "".join(
        f'<div style="margin:0 0 22px"><h2 id="{slugify(g[0])}" style="margin:0 0 6px;font-size:1.15rem">{g[0]}</h2>'
        f'<p style="margin:0">{g[1]}</p></div>' for g in GLOSSARY
    )
    glossary = (
        head(f"Glossary: Oil & Gas Sales & Marketing Terms | {BRAND}",
             "Plain-English definitions of oil & gas sales and marketing terms: AEO, speccing in, OFS, RevOps, ABM, NPT, TCO, and more.",
             f"{SITE}/glossary/", gschema) +
        header("") +
        '<section class="ep-head"><div class="wrap"><p class="eyebrow">Glossary</p><h1>Oil &amp; Gas Sales &amp; Marketing Glossary</h1><p class="ep-meta">Plain-English definitions for energy go-to-market.</p></div></section>'
        f'<section class="section-pad"><div class="wrap" style="max-width:760px">{gbody}</div></section>' +
        footer()
    )
    write(["glossary", "index.html"], glossary)

    # ----- llms.txt / robots.txt / sitemap.xml -----
    llms = (
        f"# {BRAND}\n\n> {TAGLINE}\n\n"
        f"{BRAND} is the home of the Oil & Gas Sales & Marketing Podcast ({N} episodes), hosted by "
        "Mark LaCour and Matthew Bertram on the Oil & Gas Global Network (OGGN). It is the companion to the book "
        "'Oil & Gas Sales & Marketing: The Energy Growth Playbook for Oil and Gas Leaders.'\n\n"
        "## Key pages\n"
        f"- All episodes: {SITE}/podcast/\n"
        f"- Answers (how energy companies buy, sell & market): {SITE}/answers/\n"
        f"- Topics (clustered by theme): {SITE}/topics/\n"
        f"- Glossary (O&G sales/marketing terms): {SITE}/glossary/\n"
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

    urls = [SITE + "/", SITE + "/podcast/", SITE + "/answers/", SITE + "/topics/", SITE + "/glossary/", SITE + "/book/", SITE + "/host/", SITE + "/about/", SITE + "/terms/"]
    urls += [f"{SITE}/answers/{a['slug']}/" for a in ANSWERS]
    urls += [f"{SITE}/topics/{t['slug']}/" for t in TOPICS]
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
