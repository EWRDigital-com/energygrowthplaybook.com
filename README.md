# energygrowthplaybook.com

Static site for **The Energy Growth Playbook** — the home of the *Oil & Gas Sales & Marketing Podcast*
(Mark LaCour + Matthew Bertram, on OGGN) and the companion book. Modeled on the bestseopodcast.com
AEO playbook: episodes → answer-first pages → authority funnel to matthewbertram.com + modalpoint.com.

**No framework, no build step at deploy time.** Pages are pre-generated HTML. Vercel just serves the folder.

## Structure

```
/                       index.html (home)
/podcast/               episode index
/podcast/<slug>/        one page per episode (92)
/about/ /host/ /book/   static pages
/css/style.css          styles
/img/                   cover, headshots, book cover
/data/episodes.json     content spine (parsed from the OGGN RSS feed)
/scripts/fetch_feed.py  pulls the RSS feed -> data/episodes.json
/scripts/build.py       generates all HTML from data/episodes.json
/llms.txt /robots.txt /sitemap.xml /vercel.json
```

## Rebuild from source (any machine)

```bash
python scripts/fetch_feed.py   # refresh episode data from the feed
python scripts/build.py        # regenerate all HTML
```

Feed: `https://feeds.oggn.com/category/ogsm/feed/`

## Preview locally

```bash
python -m http.server 8787     # then open http://127.0.0.1:8787
# or: npx serve
```

## Deploy

GitHub is the source of truth. Vercel is connected via Git integration:
**push to `main` → Vercel auto-deploys.** Vercel settings: framework preset **Other**,
no build command, output dir = repo root. (`vercel.json` sets clean URLs.)

## Pending / TODO

- [ ] Transcripts for all 92 episodes (YouTube captions and/or Whisper) — fuels `/answers/`
- [ ] `/answers/` + `/topics/` + `/glossary/` AEO pages (cited to episodes) — the BSP citation play
- [ ] Real `/img/mark-lacour.jpg`, `/img/book-cover.jpg`, `/img/favicon.ico`
- [ ] Per-episode guest extraction + topic tagging
