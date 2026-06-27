#!/usr/bin/env python3
"""Transcribe Oil & Gas Sales & Marketing Podcast episodes via the OpenAI Whisper API.

Pipeline per episode (sequential, idempotent):
  1. download audio enclosure -> data/_audio_tmp/<slug>.mp3
  2. transcode to 16kHz mono 32kbps (bundled ffmpeg) -> under the 25MB API limit
  3. (if still >24MB) segment by time and transcribe each chunk
  4. OpenAI whisper-1 verbose_json -> text + timestamped segments
  5. save data/transcripts/<slug>.txt and <slug>.json ; delete temp audio

Key is read from $OPENAI_API_KEY, or a local .env pointed to by $EGP_ENV_PATH, at runtime (never printed). Run:
  python scripts/transcribe.py            # all remaining (skips done)
  python scripts/transcribe.py 2          # first 2 only (validation)
"""
import os, sys, json, subprocess, re
import requests
import imageio_ffmpeg
from openai import OpenAI

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
from build import slugify, ep_num, clean_title  # single source of truth for slugs

DATA = os.path.join(ROOT, "data", "episodes.json")
TR_DIR = os.path.join(ROOT, "data", "transcripts")
TMP = os.path.join(ROOT, "data", "_audio_tmp")
ENV_PATH = os.environ.get("EGP_ENV_PATH", os.path.join(ROOT, ".env"))  # point at your secrets file; values are never committed
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
MODEL = "whisper-1"
MAX_BYTES = 24_000_000  # safety margin under the 25MB API limit


def load_key():
    if os.environ.get("OPENAI_API_KEY"):
        return os.environ["OPENAI_API_KEY"]
    for name in ("OPENAI_API_KEY", "OPENAI_KEY", "OPENAI_APIKEY"):
        try:
            with open(ENV_PATH, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith(name + "="):
                        return line.split("=", 1)[1].strip().strip('"').strip("'")
        except FileNotFoundError:
            break
    raise SystemExit(f"OPENAI key not found in env or {ENV_PATH}")


def dur_seconds(d):
    if not d:
        return 0
    try:
        parts = [int(x) for x in d.split(":")]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts[-3:]
    return h * 3600 + m * 60 + s


def download(url, dst):
    with requests.get(url, stream=True, timeout=120,
                      headers={"User-Agent": "Mozilla/5.0 (egp-build)"}) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)


def transcode(src, dst):
    subprocess.run([FFMPEG, "-y", "-i", src, "-ac", "1", "-ar", "16000",
                    "-b:a", "32k", dst],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def segment(src, outdir, seconds=1500):
    os.makedirs(outdir, exist_ok=True)
    pat = os.path.join(outdir, "part_%03d.mp3")
    subprocess.run([FFMPEG, "-y", "-i", src, "-f", "segment",
                    "-segment_time", str(seconds), "-c", "copy", pat],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return sorted(os.path.join(outdir, f) for f in os.listdir(outdir) if f.startswith("part_"))


def whisper(client, path):
    with open(path, "rb") as f:
        r = client.audio.transcriptions.create(model=MODEL, file=f, response_format="verbose_json")
    segs = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip()}
            for s in (getattr(r, "segments", None) or [])]
    return getattr(r, "text", "").strip(), segs


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    os.makedirs(TR_DIR, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)
    client = OpenAI(api_key=load_key())

    eps = json.load(open(DATA, encoding="utf-8"))["episodes"]
    eps = [e for e in eps if e.get("audio") and not e["title"].lower().startswith("coming soon")]

    todo, done = [], 0
    for e in eps:
        slug = slugify(e["title"]) or "episode"
        txt = os.path.join(TR_DIR, slug + ".txt")
        if os.path.exists(txt) and os.path.getsize(txt) > 0:
            done += 1
            continue
        todo.append((slug, e))
    if limit:
        todo = todo[:limit]

    est_min = sum(dur_seconds(e["duration"]) for _, e in todo) / 60
    print(f"already transcribed: {done} | queued: {len(todo)} | est ~{est_min:.0f} audio-min ~${est_min*0.006:.2f}")

    ok = 0
    for i, (slug, e) in enumerate(todo, 1):
        title = clean_title(e["title"])
        raw = os.path.join(TMP, slug + ".mp3")
        mini = os.path.join(TMP, slug + ".min.mp3")
        try:
            print(f"[{i}/{len(todo)}] {title[:54]} ... ", end="", flush=True)
            download(e["audio"], raw)
            transcode(raw, mini)
            size = os.path.getsize(mini)
            if size <= MAX_BYTES:
                text, segs = whisper(client, mini)
            else:
                parts = segment(mini, os.path.join(TMP, slug + "_parts"))
                texts, segs, off = [], [], 0.0
                for p in parts:
                    t, s = whisper(client, p)
                    texts.append(t)
                    for seg in s:
                        seg["start"] += off; seg["end"] += off
                    segs += s
                    off = segs[-1]["end"] if segs else off
                    os.remove(p)
                os.rmdir(os.path.join(TMP, slug + "_parts"))
                text = "\n".join(texts)
            json.dump({"slug": slug, "title": title, "episode": ep_num(e["title"]),
                       "audio": e["audio"], "text": text, "segments": segs},
                      open(os.path.join(TR_DIR, slug + ".json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            open(os.path.join(TR_DIR, slug + ".txt"), "w", encoding="utf-8").write(text)
            ok += 1
            print(f"OK ({len(text)} chars, {len(segs)} segs)")
        except Exception as ex:
            print(f"FAIL: {str(ex)[:90]}")
        finally:
            for p in (raw, mini):
                if os.path.exists(p):
                    os.remove(p)

    print(f"\ndone this run: {ok}/{len(todo)} | total transcribed now: {done + ok}/{len(eps)}")


if __name__ == "__main__":
    main()
