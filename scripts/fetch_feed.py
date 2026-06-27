#!/usr/bin/env python3
"""Fetch + parse the Oil & Gas Sales & Marketing Podcast RSS feed.

Produces data/episodes.json — the content spine for energygrowthplaybook.com,
mirroring the role the Buzzsprout feed played for bestseopodcast.com.
Stdlib only (no pip deps).
"""
import urllib.request, json, os, re
import xml.etree.ElementTree as ET

FEED = "https://feeds.oggn.com/category/ogsm/feed/"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "episodes.json")

NS = {
    "itunes": "http://www.itunes.com/dtds/podcast-1.0.dtd",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "podcast": "https://podcastindex.org/namespace/1.0",
    "atom": "http://www.w3.org/2005/Atom",
}

def text(el):
    return el.text.strip() if el is not None and el.text else ""

def main():
    req = urllib.request.Request(FEED, headers={"User-Agent": "Mozilla/5.0 (egp-build)"})
    raw = urllib.request.urlopen(req, timeout=90).read()
    root = ET.fromstring(raw)
    channel = root.find("channel")
    items = channel.findall("item")

    eps = []
    trans = 0
    for it in items:
        body = text(it.find("content:encoded", NS)) or text(it.find("description"))
        enc = it.find("enclosure")
        tr = it.find("podcast:transcript", NS)
        tr_url = tr.get("url") if tr is not None else ""
        if tr_url:
            trans += 1
        eps.append({
            "title": text(it.find("title")),
            "pubDate": text(it.find("pubDate")),
            "guid": text(it.find("guid")),
            "link": text(it.find("link")),
            "audio": enc.get("url") if enc is not None else "",
            "duration": text(it.find("itunes:duration", NS)),
            "episode": text(it.find("itunes:episode", NS)),
            "season": text(it.find("itunes:season", NS)),
            "transcript_url": tr_url,
            "desc_len": len(re.sub("<[^>]+>", "", body)),
            "description_html": body,
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"feed": FEED, "count": len(eps), "with_transcript": trans, "episodes": eps},
                  f, indent=2, ensure_ascii=False)

    print(f"episodes parsed : {len(eps)}")
    print(f"with <podcast:transcript> : {trans}")
    print(f"with audio enclosure : {sum(1 for e in eps if e['audio'])}")
    print(f"avg description chars : {sum(e['desc_len'] for e in eps)//max(1,len(eps))}")
    print("--- newest 5 ---")
    for e in eps[:5]:
        print(f"  [{e['episode'] or '?'}] {e['title'][:66]} | {e['duration'] or '?'} | {e['desc_len']}c | audio={'Y' if e['audio'] else 'N'} tr={'Y' if e['transcript_url'] else 'N'}")
    print("--- oldest 3 ---")
    for e in eps[-3:]:
        print(f"  [{e['episode'] or '?'}] {e['title'][:66]} | {e['pubDate']}")
    print(f"\nwrote {OUT}")

if __name__ == "__main__":
    main()
