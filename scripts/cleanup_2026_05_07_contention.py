"""
One-shot surgical cleanup for the 2026-05-07 LM Studio model-contention incident.

Window: 2026-05-07 23:02:22 -> 23:04:30 (local).
Cause:  Two run_experiment.py processes (nemotron + qwen35_4b) competed for LM
        Studio's single-active-model slot. Each call would unload the other
        model, returning 400 'Model unloaded' on the next request.

Affected experiments (identified by trace timestamp overlap with the window):
  - qwen35_4b rate_0.00 nopb j=100, 101  (CSV + trace)
  - nemotron rate_0.02 nopb j=186, 187   (CSV + trace)
  - nemotron rate_0.02 nopb j=188        (TRACE-ONLY orphan turns from
                                          interrupted attempt; CSV row is
                                          already from the clean 2026-05-08
                                          rerun)

Action: split CSV/trace into active (clean) and .retired_2026-05-07_contention
        evidence files. Rerun fills the holes deterministically via seed.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETIRED_SUFFIX  = ".retired_2026-05-07_contention"
ORIGINAL_SUFFIX = ".original_2026-05-07_pre_cleanup"

CONTENTION_START = dt.datetime(2026, 5, 7, 23, 2, 22).timestamp()
CONTENTION_END   = dt.datetime(2026, 5, 7, 23, 4, 30).timestamp()

# (csv_path, trace_path, contaminated_csv_ids, trace_only_orphan_ids)
PLAN = [
    {
        "name": "qwen35_4b",
        "csv":   ROOT / "experiments/qwen35_4b/qwen35-4b/http/rate_0.00.csv",
        "trace": ROOT / "experiments/qwen35_4b/qwen35-4b/http/trace.jsonl",
        "csv_ids": {
            "http-qwen35-4b-nopb-0.0-100",
            "http-qwen35-4b-nopb-0.0-101",
        },
        "trace_only_ids": set(),
    },
    {
        "name": "nemotron_nano_4b",
        "csv":   ROOT / "experiments/nemotron_nano_4b/nemotron-nano-4b/http_think/rate_0.02.csv",
        "trace": ROOT / "experiments/nemotron_nano_4b/nemotron-nano-4b/http_think/trace.jsonl",
        "csv_ids": {
            "http-nemotron-nano-4b-think-nopb-0.02-186",
            "http-nemotron-nano-4b-think-nopb-0.02-187",
        },
        "trace_only_ids": {
            # CSV row from clean rerun, but trace has 3 contention-era turns
            "http-nemotron-nano-4b-think-nopb-0.02-188",
        },
    },
]


def split_csv(path: Path, csv_ids: set[str]) -> tuple[list[list[str]], list[list[str]], list[str]]:
    """Return (clean_rows, retired_rows, header)."""
    with path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        clean, retired = [], []
        for row in reader:
            (retired if row[0] in csv_ids else clean).append(row)
    return clean, retired, header


def split_trace(
    path: Path,
    csv_ids: set[str],
    trace_only_ids: set[str],
) -> tuple[list[dict], list[dict]]:
    """Return (clean_events, retired_events).

    csv_ids        -> ALL turns go to retired
    trace_only_ids -> only turns with timestamp inside contention window go to retired
    others         -> all clean
    """
    clean, retired = [], []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line:
                continue
            e = json.loads(line)
            eid = e["experiment_id"]
            ts = e.get("timestamp", 0)
            if eid in csv_ids:
                retired.append(e)
            elif eid in trace_only_ids and CONTENTION_START <= ts <= CONTENTION_END:
                retired.append(e)
            else:
                clean.append(e)
    return clean, retired


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def write_jsonl(path: Path, events: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def with_suffix_before_ext(path: Path, suffix: str) -> Path:
    return path.with_name(path.stem + suffix + path.suffix)


def main() -> None:
    print(f"Cleanup script — incident window: "
          f"{dt.datetime.fromtimestamp(CONTENTION_START)} -> "
          f"{dt.datetime.fromtimestamp(CONTENTION_END)}\n")

    summary = []
    for entry in PLAN:
        print(f"=== {entry['name']} ===")
        csv_path: Path = entry["csv"]
        trace_path: Path = entry["trace"]
        csv_ids: set[str] = entry["csv_ids"]
        trace_only_ids: set[str] = entry["trace_only_ids"]

        # --- Step 0: archive immutable originals (verbatim byte copies) ---
        original_csv = with_suffix_before_ext(csv_path, ORIGINAL_SUFFIX)
        original_trace = with_suffix_before_ext(trace_path, ORIGINAL_SUFFIX)
        shutil.copy2(csv_path, original_csv)
        shutil.copy2(trace_path, original_trace)
        h_csv_original = sha256_file(original_csv)
        h_trace_original = sha256_file(original_trace)
        print(f"  ORIGINAL CSV archived  : {original_csv.name}  sha256={h_csv_original}")
        print(f"  ORIGINAL trace archived: {original_trace.name}  sha256={h_trace_original}")

        # --- CSV split ---
        clean_rows, retired_rows, header = split_csv(csv_path, csv_ids)
        retired_csv = with_suffix_before_ext(csv_path, RETIRED_SUFFIX)
        if retired_rows:
            write_csv(retired_csv, header, retired_rows)
        write_csv(csv_path, header, clean_rows)
        print(f"  CSV active : {len(clean_rows)} rows  ({csv_path.name})")
        print(f"  CSV retired: {len(retired_rows)} rows  ({retired_csv.name})")

        # --- Trace split ---
        clean_evts, retired_evts = split_trace(trace_path, csv_ids, trace_only_ids)
        retired_trace = with_suffix_before_ext(trace_path, RETIRED_SUFFIX)
        if retired_evts:
            write_jsonl(retired_trace, retired_evts)
        write_jsonl(trace_path, clean_evts)
        print(f"  Trace active : {len(clean_evts)} events  ({trace_path.name})")
        print(f"  Trace retired: {len(retired_evts)} events  ({retired_trace.name})")

        # --- Hashes ---
        h_csv_active = sha256_file(csv_path)
        h_csv_retired = sha256_file(retired_csv) if retired_rows else "—"
        h_trace_active = sha256_file(trace_path)
        h_trace_retired = sha256_file(retired_trace) if retired_evts else "—"
        print(f"  SHA256 active CSV   : {h_csv_active}")
        print(f"  SHA256 retired CSV  : {h_csv_retired}")
        print(f"  SHA256 active trace : {h_trace_active}")
        print(f"  SHA256 retired trace: {h_trace_retired}")
        print()

        summary.append({
            "name": entry["name"],
            "csv_active": str(csv_path.relative_to(ROOT)),
            "csv_retired": str(retired_csv.relative_to(ROOT)) if retired_rows else None,
            "csv_original": str(original_csv.relative_to(ROOT)),
            "trace_active": str(trace_path.relative_to(ROOT)),
            "trace_retired": str(retired_trace.relative_to(ROOT)) if retired_evts else None,
            "trace_original": str(original_trace.relative_to(ROOT)),
            "hashes": {
                "csv_active": h_csv_active,
                "csv_retired": h_csv_retired,
                "csv_original": h_csv_original,
                "trace_active": h_trace_active,
                "trace_retired": h_trace_retired,
                "trace_original": h_trace_original,
            },
            "csv_rows_active": len(clean_rows),
            "csv_rows_retired": len(retired_rows),
            "trace_events_active": len(clean_evts),
            "trace_events_retired": len(retired_evts),
            "csv_ids_excluded": sorted(csv_ids),
            "trace_only_ids_filtered": sorted(trace_only_ids),
        })

    out = ROOT / "experiments" / "INCIDENT_2026-05-07_lm_studio_contention.summary.json"
    out.write_text(json.dumps({
        "window_start": dt.datetime.fromtimestamp(CONTENTION_START).isoformat(),
        "window_end": dt.datetime.fromtimestamp(CONTENTION_END).isoformat(),
        "actions": summary,
    }, indent=2), encoding="utf-8")
    print(f"Summary written: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
