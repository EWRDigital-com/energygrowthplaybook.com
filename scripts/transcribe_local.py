#!/usr/bin/env python3
"""Transcribe episodes locally with faster-whisper on the GPU (free, no API quota).

Per episode (sequential, idempotent): download audio -> faster-whisper transcribe
-> save data/transcripts/<slug>.txt and <slug>.json -> delete temp audio.

Run:
  python scripts/transcribe_local.py            # model=small, all remaining
  python scripts/transcribe_local.py small 2    # model=small, first 2 (validation)
  python scripts/transcribe_local.py medium     # better quality, all remaining
"""
import os, sys, json, time
import requests

def _enable_cuda_dlls():
    """faster-whisper/CTranslate2 need cuBLAS + cuDNN + CUDA runtime DLLs on the
    Windows DLL path. Add ALL nvidia/*/bin dirs (cublas, cuda_runtime, cuda_nvrtc, cudnn)."""
    try:
        import nvidia, glob
        for base in nvidia.__path__:
            for d in glob.glob(os.path.join(base, "*", "bin")):
                if os.path.isdir(d):
                    os.add_dll_directory(d)
                    os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    except Exception as e:
        print("cuda dll setup skipped:", e)

_enable_cuda_dlls()
from faster_whisper import WhisperModel

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
sys.path.insert(0, SCRIPTS)
from build import slugify, ep_num, clean_title, assign_slugs

DATA = os.path.join(ROOT, "data", "episodes.json")
TR_DIR = os.path.join(ROOT, "data", "transcripts")
TMP = os.path.join(ROOT, "data", "_audio_tmp")


def get_model(size):
    try:
        m = WhisperModel(size, device="cuda", compute_type="float16")
        print(f"model={size} device=cuda compute=float16")
        return m
    except Exception as e:
        print(f"cuda load failed ({str(e)[:70]}); falling back to CPU int8")
        m = WhisperModel(size, device="cpu", compute_type="int8")
        print(f"model={size} device=cpu compute=int8")
        return m


def download(url, dst):
    with requests.get(url, stream=True, timeout=180,
                      headers={"User-Agent": "Mozilla/5.0 (egp-build)"}) as r:
        r.raise_for_status()
        with open(dst, "wb") as f:
            for chunk in r.iter_content(1 << 16):
                f.write(chunk)


def main():
    args = [a for a in sys.argv[1:]]
    size = "small"
    limit = None
    for a in args:
        if a.isdigit():
            limit = int(a)
        else:
            size = a

    os.makedirs(TR_DIR, exist_ok=True)
    os.makedirs(TMP, exist_ok=True)

    raw = json.load(open(DATA, encoding="utf-8"))["episodes"]
    src = [e for e in raw if not e["title"].lower().startswith("coming soon")]
    assign_slugs(src)  # same unique-slug assignment build.py uses (collision-safe)
    eps = [e for e in src if e.get("audio")]

    todo, done = [], 0
    for e in eps:
        slug = e["slug"]
        txt = os.path.join(TR_DIR, slug + ".txt")
        if os.path.exists(txt) and os.path.getsize(txt) > 0:
            done += 1
            continue
        todo.append((slug, e))
    if limit:
        todo = todo[:limit]

    print(f"already transcribed: {done} | queued: {len(todo)}")
    if not todo:
        print("nothing to do.")
        return

    model = get_model(size)
    ok = 0
    for i, (slug, e) in enumerate(todo, 1):
        title = clean_title(e["title"])
        raw = os.path.join(TMP, slug + ".mp3")
        try:
            t0 = time.time()
            print(f"[{i}/{len(todo)}] {title[:52]} ... ", end="", flush=True)
            download(e["audio"], raw)
            segments, info = model.transcribe(raw, beam_size=5, vad_filter=True,
                                              language="en")
            segs, parts = [], []
            for s in segments:
                segs.append({"start": round(s.start, 2), "end": round(s.end, 2),
                             "text": s.text.strip()})
                parts.append(s.text.strip())
            text = " ".join(parts)
            json.dump({"slug": slug, "title": title, "episode": ep_num(e["title"]),
                       "audio": e["audio"], "duration": round(info.duration, 1),
                       "text": text, "segments": segs},
                      open(os.path.join(TR_DIR, slug + ".json"), "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
            open(os.path.join(TR_DIR, slug + ".txt"), "w", encoding="utf-8").write(text)
            ok += 1
            rt = info.duration / max(1, time.time() - t0)
            print(f"OK ({len(text)} chars, {len(segs)} segs, {rt:.1f}x realtime)")
        except Exception as ex:
            print(f"FAIL: {str(ex)[:90]}")
        finally:
            if os.path.exists(raw):
                os.remove(raw)

    print(f"\ndone this run: {ok}/{len(todo)} | total now: {done + ok}/{len(eps)}")


if __name__ == "__main__":
    main()
