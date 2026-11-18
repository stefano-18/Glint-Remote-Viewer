"""Summarise one or more JSON files produced by `python -m viewer --bench ...`."""
import json
import re
import statistics
import sys


def num(v):
    m = re.match(r"-?[\d.]+", str(v or ""))
    return float(m.group()) if m else None


def summarize(path):
    d = json.load(open(path, encoding="utf-8"))
    s = [r for r in d["samples"] if r.get("state") == "playing" and r.get("resolution", "—") != "—"]
    steady = s[5:] if len(s) > 8 else s

    def med(key):
        vals = [num(r.get(key)) for r in steady if num(r.get(key)) is not None]
        return round(statistics.median(vals), 2) if vals else None

    def mx(key):
        vals = [num(r.get(key)) for r in steady if num(r.get(key)) is not None]
        return round(max(vals), 2) if vals else None
    last = s[-1] if s else {}
    return {
        "file": path.replace("\\", "/").rsplit("/", 1)[-1], "profile": d["opts"]["profile"],
        "playing_samples": len(s), "resolution": last.get("resolution"), "fps_source": last.get("fps_source"),
        "fps_shown_median": med("fps_shown"), "decoding": last.get("hwdec"), "dropped_final": last.get("dropped"),
        "cpu_pct_median": med("cpu_pct"), "cpu_pct_max": mx("cpu_pct"), "ram_mb_max": mx("rss_mb"),
        "buffer_median_s": med("buffer"), "lag_edge_median_s": med("lag_edge"),
        "lag_ingest_median_s": med("lag_ingest"), "stalls": last.get("stalls"),
        "connect_time": last.get("connect_time"), "audio": last.get("audio_codec"), "ao": last.get("ao"),
        "events": d.get("events"),
        "log_errors": [line for line in d.get("log_tail", []) if "[error]" in line or "[fatal]" in line][:5],
    }


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(summarize(p), ensure_ascii=False, indent=1))
