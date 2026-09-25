import json

rows = []
with open("backend/qa_rg.log", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line.startswith("{"):
            rows.append(json.loads(line))
bad = [r for r in rows
       if r.get("$report_type") == "TestReport"
       and r.get("outcome") in ("failed", "error")
       and r.get("when") != "teardown"]
print("count:", len(bad))
for r in bad[:30]:
    print(r["outcome"], r["nodeid"].split("::")[-1])
