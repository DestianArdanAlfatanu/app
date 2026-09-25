"""One-shot: wrap seed_demo_data.py linear phases into functions + --from-phase runner."""
PATH = 'seed_demo_data.py'
lines = open(PATH, encoding='utf-8').readlines()

# (name, start_1idx_inclusive, end_1idx_exclusive, globals)
PHASES = [
    ("login", 161, 172, []),
    ("accounts", 172, 181, ["ACCS"]),
    ("employees", 181, 219, ["EMPS"]),
    ("users", 219, 237, []),
    ("classes", 237, 254, ["CLASSES"]),
    ("students", 282, 303, ["ACTIVES"]),
    ("alumni", 303, 315, ["ALUMNI"]),
    ("candidates", 315, 340, ["CANDS"]),
    ("attendance", 340, 359, []),
    ("grades", 359, 379, []),
    ("selections", 379, 389, []),
    ("followups", 389, 405, []),
    ("payments", 405, 445, []),
    ("expenses", 445, 477, []),
    ("hr_attendance", 477, 506, []),
    ("payroll", 506, 531, []),
    ("jobs", 531, 568, ["JOBIDS"]),
    ("dep_students", 568, 581, ["DEPST"]),
    ("documents", 581, 608, []),
    ("departures", 608, 630, []),
    ("collections", 630, 642, []),
    ("summary", 642, 646, []),
]

# sanity: first line of each range must be the phase print (or summary tail)
for name, s, e, g in PHASES:
    first = lines[s - 1]
    assert first.startswith('print("==') or first.startswith('print(f"') or name == "summary", (name, first)
print("boundaries ok")

out = lines[:160]  # helpers + constants + make_student stay top-level
pos = 160  # 0-indexed line 161
for name, s, e, g in PHASES:
    # copy through any top-level lines between phases (helpers, constants)
    out.extend(lines[pos:s - 1])
    out.append(f"\n\ndef phase_{name}():\n")
    if g:
        out.append(f"    global {', '.join(g)}\n")
    for ln in lines[s - 1:e - 1]:
        out.append(("    " + ln) if ln.strip() else ln)
    pos = e - 1
assert pos == 645, pos
out.append('''

PHASES = [("login", phase_login), ("accounts", phase_accounts), ("employees", phase_employees),
          ("users", phase_users), ("classes", phase_classes), ("students", phase_students),
          ("alumni", phase_alumni), ("candidates", phase_candidates), ("attendance", phase_attendance),
          ("grades", phase_grades), ("selections", phase_selections), ("followups", phase_followups),
          ("payments", phase_payments), ("expenses", phase_expenses), ("hr_attendance", phase_hr_attendance),
          ("payroll", phase_payroll), ("jobs", phase_jobs), ("dep_students", phase_dep_students),
          ("documents", phase_documents), ("departures", phase_departures),
          ("collections", phase_collections), ("summary", phase_summary)]

if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--list-phases" in args:
        print(" ".join(n for n, _ in PHASES))
    else:
        start = 0
        if "--from-phase" in args:
            want = args[args.index("--from-phase") + 1]
            start = next(i for i, (n, _) in enumerate(PHASES) if n == want)
        for name, fn in PHASES[start:]:
            fn()
''')
open(PATH, 'w', encoding='utf-8').write(''.join(out))
print("wrapped ok")
