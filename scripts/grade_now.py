#!/usr/bin/env python3
"""Grade pending public picks/forecasts from completed ESPN results; keep files untouched
unless at least one grade actually changed (so timestamps alone never create commits).

Never re-grades a graded row (grade_files skips them) and never turns a missing result
into a loss. Prints a one-line summary and writes .agent/grading.md for the bus.
"""
import json, shutil, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from grading import grade_files  # noqa: E402

FILES = [('picks.json', 'picks'), ('prediction_log.json', 'predictions')]


def grades(path, field):
    rows = json.loads(path.read_text(encoding='utf-8')).get(field, []) if path.exists() else []
    return {str(r.get('id') or r.get('key')): r.get('grade') for r in rows}


def main(data=ROOT / 'data', now=None):
    now = now or datetime.now(timezone.utc)
    data = Path(data)
    before = {n: grades(data / n, f) for n, f in FILES}
    backup = Path(tempfile.mkdtemp())
    for n, _ in FILES:
        if (data / n).exists():
            shutil.copy2(data / n, backup / n)
    grade_files(data, now)
    changed = []
    for n, f in FILES:
        after = grades(data / n, f)
        diff = [(k, after[k]) for k in after if after[k] != before[n].get(k)]
        lost = [k for k in before[n] if k not in after]
        if lost:  # safety: grading must never drop a record
            raise SystemExit(f'{n}: {len(lost)} records disappeared during grading; aborting')
        if diff:
            changed += [(n, k, g) for k, g in diff]
        elif (backup / n).exists():
            shutil.copy2(backup / n, data / n)  # restore byte-for-byte: no timestamp-only churn
    lines = [f'- `{n}` **{k}** -> {g}' for n, k, g in changed]
    Path(ROOT / '.agent').mkdir(exist_ok=True)
    (ROOT / '.agent' / 'grading.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'{len(changed)} new grades at {now:%Y-%m-%d %H:%M} UTC')
    for line in lines:
        print(line)
    return changed


if __name__ == '__main__':
    main()
