"""DEV-ONLY B3: collection activities on real arrears."""
import requests

API = "http://127.0.0.1:8000/api"
T = {}
for r, e, p in [("finance", "finance@lpk.id", "password123")]:
    T[r] = requests.post(API + "/auth/login", json={"email": e, "password": p}, timeout=15).json()["token"]
H = {"Authorization": "Bearer " + T["finance"]}


def post(path, body):
    r = requests.post(API + path, headers=H, json=body, timeout=30)
    assert r.status_code == 200, f"FAIL POST {path}: {r.status_code} {r.text[:200]}"
    return r.json()


od = [x for x in requests.get(API + "/payments-arrears", headers=H, timeout=20).json()
      if x.get("kondisi") == "terlambat"][:7]
print("targets:", len(od))
acts = [("phone", "contacted", "Sudah dihubungi, janji transfer", "2026-09-26"),
        ("whatsapp", "contacted", "Ingatkan via WA manual (catatan)", "2026-09-28"),
        ("phone", "promised_payment", "Janji bayar setelah gajian", "2026-10-02"),
        ("in_person", "no_response", "Datang ke rumah, tidak ada orang", "2026-09-30"),
        ("phone", "promised_payment", "Minta keringanan cicilan", "2026-09-20"),
        ("whatsapp", "no_response", "Chat WA manual belum dibalas (catatan)", None),
        ("phone", "contacted", "Akan dibayar minggu ini", "2026-09-27")]
for o, (ch, oc, note, fu) in zip(od, acts):
    body = {"student_id": o["id"], "channel": ch, "outcome": oc, "note": note}
    if fu:
        body.update({"next_follow_up_at": fu, "next_follow_up_note": "Follow-up pembayaran"})
    post("/collections/activities", body)
print("B3 done")
