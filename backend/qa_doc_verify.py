"""Targeted QA: document verification lifecycle. Synthetic realistic IDs tracked for cleanup."""
import requests

API = "http://127.0.0.1:8000/api"
R = {"pass": [], "fail": []}


def check(name, cond, extra=""):
    (R["pass"] if cond else R["fail"]).append(name)
    print(("PASS " if cond else "FAIL ") + name, extra)


t = requests.post(API + "/auth/login", json={"email": "owner@lpk.id", "password": "owner123"}, timeout=15).json()["token"]
H = {"Authorization": "Bearer " + t}

# A. existing metadata readable
s0 = requests.get(API + "/students", headers=H, timeout=15).json()[0]["id"]
r = requests.get(API + f"/students/{s0}/documents", headers=H, timeout=15)
check("A existing docs readable", r.status_code == 200 and isinstance(r.json(), list))

# temp student (realistic synthetic)
s = requests.post(API + "/students", headers=H, json={"nama_lengkap": "Andi Pratama", "jenis_kelamin": "L",
    "no_hp": "081234567890", "email": "andi.pratama.qa@example.test"}, timeout=15).json()
sid = s["id"]
print("temp student:", sid)

# B. metadata-only upload (no storage involved) -> pending
r = requests.post(API + f"/students/{sid}/documents",
                  headers={**H, "Content-Type": "application/x-www-form-urlencoded"},
                  data={"jenis": "Ijazah", "kategori": "pendidikan"}, timeout=15)
check("B metadata upload pending", r.status_code == 200 and r.json().get("status") == "pending_verification", str(r.status_code))
doc1 = r.json().get("id")

# C. upload WITH file, storage blocked -> controlled failure, no metadata
n0 = len(requests.get(API + f"/students/{sid}/documents", headers=H, timeout=15).json())
try:
    r = requests.post(API + f"/students/{sid}/documents", headers=H,
                      files={"file": ("Andi_Pratama_Ijazah.pdf", b"%PDF-1.4 fake", "application/pdf")},
                      data={"jenis": "Ijazah", "kategori": "pendidikan"}, timeout=60)
    code, has_meta = r.status_code, None
except Exception as e:
    code, has_meta = f"EXC {type(e).__name__}", None
n1 = len(requests.get(API + f"/students/{sid}/documents", headers=H, timeout=15).json())
check("C file upload fails controlled, no orphan metadata", code in (502,) and n1 == n0, f"code={code} n0={n0} n1={n1}")

# D. verify
r = requests.put(API + f"/students/{sid}/documents/{doc1}/verify", headers=H, json={"note": "QA cek"}, timeout=15)
check("D verify", r.status_code == 200 and r.json().get("status") == "verified", str(r.status_code))

# E. reject flow on second doc + F. reject without reason
r = requests.post(API + f"/students/{sid}/documents", headers={**H, "Content-Type": "application/x-www-form-urlencoded"},
                  data={"jenis": "SKCK", "kategori": "identitas"}, timeout=15)
doc2 = r.json().get("id")
r = requests.put(API + f"/students/{sid}/documents/{doc2}/reject", headers=H, json={"reason": ""}, timeout=15)
check("F reject w/o reason 400", r.status_code == 400, str(r.status_code))
r = requests.put(API + f"/students/{sid}/documents/{doc2}/reject", headers=H, json={"reason": "Dokumen tidak sesuai"}, timeout=15)
check("E reject", r.status_code == 200 and r.json().get("status") == "rejected"
      and r.json().get("rejected_reason") == "Dokumen tidak sesuai", str(r.status_code))

# G. cross-student (verify doc1 under another student id)
r = requests.put(f"{API}/students/bogus-id/documents/{doc1}/verify", headers=H, json={}, timeout=15)
check("G cross-student 404", r.status_code == 404, str(r.status_code))

# replacement -> pending again
r = requests.post(API + f"/students/{sid}/documents", headers={**H, "Content-Type": "application/x-www-form-urlencoded"},
                  data={"jenis": "SKCK", "kategori": "identitas"}, timeout=15)
check("reupload pending", r.status_code == 200 and r.json().get("status") == "pending_verification", str(r.status_code))

# H. doc_progress counts verified, not pending/rejected
rows = requests.get(API + f"/students/{sid}/documents", headers=H, timeout=15).json()
print("   doc statuses:", sorted(x["status"] for x in rows))

# J. audit
au = requests.get(API + "/audit-logs?entity=document&limit=50", headers=H, timeout=15).json()
mine = [x for x in au if x.get("entity_id") in (doc1, doc2)]
print("   audit actions:", sorted({x["action"] for x in mine}))
check("J audit upload/verify/reject", {"upload", "verify", "reject"} <= {x["action"] for x in mine})

print(f"\nQA ids for cleanup: student={sid}")
print(f"RESULT pass={len(R['pass'])} fail={len(R['fail'])}")
if R["fail"]:
    print("FAILED:", R["fail"])
