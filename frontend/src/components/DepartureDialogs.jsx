import { useState, useEffect } from "react";
import { toast } from "sonner";
import { api, errMsg, fileUrl } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FormDialog, Field, Loading, EmptyState } from "@/components/common";
import { fmtDate as fmtD } from "@/lib/format";

export const READINESS_LABELS = { NOT_READY: "Belum Ready", READY: "Ready", BLOCKED: "Blocked" };
export const READINESS_TONE = { NOT_READY: "bg-slate-100 text-slate-600 border-slate-200", READY: "bg-emerald-50 text-emerald-700 border-emerald-200", BLOCKED: "bg-red-50 text-red-700 border-red-200" };
export const ITEM_LABELS = { pending: "Pending", verified: "Verified", rejected: "Rejected", exception: "Exception" };

export function ChecklistDialog({ profile, onClose, onChanged }) {
  const { can } = useAuth();
  const [rows, setRows] = useState(null);
  const [verify, setVerify] = useState(null);
  const [reject, setReject] = useState(null);
  const [exc, setExc] = useState(null);
  const [note, setNote] = useState("");
  const [reason, setReason] = useState("");
  const [docId, setDocId] = useState("");
  const [busy, setBusy] = useState(false);
  const canVerify = can("departure_verify");

  useEffect(() => {
    if (!profile) return;
    setRows(null);
    api.get(`/departures/${profile.id}/checklist`).then(({ data }) => setRows(data)).catch((e) => toast.error(errMsg(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile]);

  const load = async () => {
    try { const { data } = await api.get(`/departures/${profile.id}/checklist`); setRows(data); }
    catch (e) { toast.error(errMsg(e)); }
  };

  const act = async (fn, okMsg) => {
    setBusy(true);
    try { await fn(); toast.success(okMsg); setVerify(null); setReject(null); setExc(null); setNote(""); setReason(""); setDocId(""); load(); onChanged && onChanged(); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(false); }
  };

  return (
    <FormDialog open={!!profile} onOpenChange={onClose} title={`Checklist — ${profile?.student_nama}`} description="Verifikasi manusia per item. Upload bukan verifikasi." onSubmit={onClose} submitLabel="Tutup" testId="dep-checklist-dialog" wide>
      {rows === null ? <Loading /> : (
        <div className="space-y-2 max-h-96 overflow-y-auto" data-testid="dep-checklist-list">
          {rows.map((it) => <div key={it.id} className="rounded-lg border p-3 text-sm">
            <div className="flex justify-between items-center gap-2 flex-wrap">
              <span className="font-medium">{it.requirement_name}{it.required ? "" : " (opsional)"}</span>
              <span className={`chip ${it.status === "verified" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : it.status === "rejected" ? "bg-red-50 text-red-700 border-red-200" : it.status === "exception" ? "bg-violet-50 text-violet-700 border-violet-200" : "bg-slate-100 text-slate-600 border-slate-200"}`}>{ITEM_LABELS[it.status]}</span>
            </div>
            <p className="text-xs text-slate-500 mt-1">
              {it.document?.jenis ? <>Dok: {it.document.jenis}{it.document.tanggal_kadaluarsa ? ` (exp ${fmtD(it.document.tanggal_kadaluarsa)})` : ""} {it.document.file_id ? <a className="text-red-600 font-semibold" href={fileUrl(it.document.file_id)} target="_blank" rel="noreferrer">Lihat</a> : ""} · </> : "Belum ada dokumen tertaut · "}
              {it.verified_by ? `Verified oleh ${it.verified_by} ${fmtD(it.verified_at?.slice(0, 10))} · ` : ""}
              {it.verification_note ? `“${it.verification_note}” · ` : ""}
              {it.status === "rejected" ? `Alasan: ${it.rejected_reason} · ` : ""}
              {it.exception_status !== "none" ? `Exception (${it.exception_status})${it.exception_reason ? `: ${it.exception_reason}` : ""}${it.exception_approved_by ? ` — disetujui ${it.exception_approved_by}` : ""}` : ""}
            </p>
            {canVerify && (
              <div className="flex gap-1.5 mt-2 flex-wrap">
                <button type="button" className="btn-outline btn-sm" onClick={() => { setVerify(it); setReject(null); setExc(null); }}>Verifikasi</button>
                <button type="button" className="btn-outline btn-sm" onClick={() => { setReject(it); setVerify(null); setExc(null); }}>Tolak</button>
                <button type="button" className="btn-outline btn-sm" onClick={() => { setExc(it); setVerify(null); setReject(null); }}>Exception</button>
              </div>)}
            {verify?.id === it.id && (
              <div className="grid sm:grid-cols-2 gap-2 mt-2">
                <Field label="Document ID (opsional)"><input className="input mono" value={docId} onChange={(e) => setDocId(e.target.value)} placeholder="kosongkan bila verifikasi fisik" /></Field>
                <Field label="Catatan verifikasi"><input className="input" value={note} onChange={(e) => setNote(e.target.value)} /></Field>
                <div className="sm:col-span-2"><button type="button" disabled={busy} className="btn-red btn-sm" onClick={() => act(() => api.put(`/departures/${profile.id}/checklist/${it.id}/verify`, { document_id: docId || null, note }), "Item verified")}>Simpan Verifikasi</button></div>
              </div>)}
            {reject?.id === it.id && (
              <div className="mt-2 flex gap-2">
                <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Alasan penolakan *" data-testid="dep-reject-reason" />
                <button type="button" disabled={busy} className="btn-red btn-sm" onClick={() => act(() => api.post(`/departures/${profile.id}/checklist/${it.id}/reject`, { reason }), "Item rejected")}>Tolak</button>
              </div>)}
            {exc?.id === it.id && (
              <div className="mt-2 flex gap-2">
                <input className="input" value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Alasan exception * (butuh approval Owner bila bukan Owner)" data-testid="dep-exc-reason" />
                <button type="button" disabled={busy} className="btn-red btn-sm" onClick={() => act(() => api.post(`/departures/${profile.id}/checklist/${it.id}/exception`, { reason }), "Exception tercatat")}>Ajukan</button>
              </div>)}
          </div>)}
        </div>)}
    </FormDialog>
  );
}

export function ProfileDialog({ student, profile, onClose, onSaved }) {
  const [form, setForm] = useState({ target_departure_date: profile?.target_departure_date || "", destination: profile?.destination || "", departure_location: profile?.departure_location || "", pic_name: profile?.pic_name || "", notes: profile?.notes || "", ticket_airline: profile?.ticket_airline || "", flight_number: profile?.flight_number || "", departure_datetime: profile?.departure_datetime || "", arrival_datetime: profile?.arrival_datetime || "", departure_airport: profile?.departure_airport || "", arrival_airport: profile?.arrival_airport || "", status: profile?.status || "disiapkan" });
  const [saving, setSaving] = useState(false);
  const [alasan, setAlasan] = useState("");
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (profile && !alasan.trim()) return toast.error("Alasan perubahan wajib diisi (audit)");
    setSaving(true);
    try {
      if (profile) {
        const { data } = await api.put(`/departures/${profile.id}`, { ...form, alasan });
        toast.success("Profile diperbarui"); onSaved && onSaved(data);
      } else {
        const { data } = await api.post("/departures", { student_id: student.id, target_departure_date: form.target_departure_date || null, destination: form.destination || null });
        toast.success("Departure profile dibuat (6 item checklist)"); onSaved && onSaved(data);
      }
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setSaving(false); }
  };

  return (
    <FormDialog open={!!(student || profile)} onOpenChange={onClose} title={profile ? `Edit Departure — ${profile.student_nama}` : `Buat Departure — ${student?.nama_lengkap}`} description="Data operasional keberangkatan." onSubmit={save} submitLabel={saving ? "Menyimpan..." : "Simpan"} testId="dep-profile-dialog" wide>
      <div className="grid sm:grid-cols-2 gap-3">
        <Field label="Target Departure"><input type="date" className="input" value={form.target_departure_date || ""} onChange={(e) => set("target_departure_date", e.target.value)} /></Field>
        <Field label="Destination"><input className="input" value={form.destination} onChange={(e) => set("destination", e.target.value)} placeholder="otomatis dari job order bila kosong" /></Field>
        <Field label="Lokasi Keberangkatan"><input className="input" value={form.departure_location} onChange={(e) => set("departure_location", e.target.value)} /></Field>
        <Field label="PIC"><input className="input" value={form.pic_name} onChange={(e) => set("pic_name", e.target.value)} /></Field>
        <Field label="Maskapai"><input className="input" value={form.ticket_airline} onChange={(e) => set("ticket_airline", e.target.value)} /></Field>
        <Field label="No. Penerbangan"><input className="input" value={form.flight_number} onChange={(e) => set("flight_number", e.target.value)} /></Field>
        <Field label="Berangkat (datetime)"><input type="datetime-local" className="input" value={form.departure_datetime || ""} onChange={(e) => set("departure_datetime", e.target.value)} /></Field>
        <Field label="Tiba (datetime)"><input type="datetime-local" className="input" value={form.arrival_datetime || ""} onChange={(e) => set("arrival_datetime", e.target.value)} /></Field>
        <Field label="Bandara Asal"><input className="input" value={form.departure_airport} onChange={(e) => set("departure_airport", e.target.value)} /></Field>
        <Field label="Bandara Tujuan"><input className="input" value={form.arrival_airport} onChange={(e) => set("arrival_airport", e.target.value)} /></Field>
        {profile && <Field label="Status Operasional"><select className="input" value={form.status} onChange={(e) => set("status", e.target.value)}>{["disiapkan", "siap", "tertunda", "berangkat"].map((x) => <option key={x} value={x}>{x}</option>)}</select></Field>}
        <Field label="Catatan"><input className="input" value={form.notes} onChange={(e) => set("notes", e.target.value)} /></Field>
      </div>
      {profile && <Field label="Alasan Perubahan *"><input className="input" value={alasan} onChange={(e) => setAlasan(e.target.value)} required /></Field>}
    </FormDialog>
  );
}

export function DecisionDialog({ profile, mode, onClose, onSaved }) {
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const save = async () => {
    if (mode === "block" && !reason.trim()) return toast.error("Alasan BLOCKED wajib diisi");
    setSaving(true);
    try {
      const { data } = await api.post(`/departures/${profile.id}/${mode}`, { reason });
      toast.success(mode === "ready" ? "Ditandai READY" : "Ditandai BLOCKED"); onSaved && onSaved(data); onClose();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setSaving(false); }
  };
  return (
    <FormDialog open={!!profile} onOpenChange={onClose} title={`${mode === "ready" ? "Mark READY" : "Mark BLOCKED"} — ${profile?.student_nama}`} description={mode === "ready" ? "Hanya bila seluruh checklist wajib verified dan tanpa blocker." : "Blocker eksplisit oleh Owner."} onSubmit={save} submitLabel={saving ? "Menyimpan..." : "Simpan"} testId="dep-decision-dialog">
      <Field label={mode === "block" ? "Alasan BLOCKED *" : "Catatan"}><textarea className="input" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="dep-decision-reason" /></Field>
    </FormDialog>
  );
}
