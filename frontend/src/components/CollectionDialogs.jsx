import { useState, useEffect } from "react";
import { toast } from "sonner";
import { MessageCircle, Phone, History } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FormDialog, Field, Loading, EmptyState } from "@/components/common";
import { rupiah, fmtDate as fmtD } from "@/lib/format";

export const OUTCOME_LABELS = { contacted: "Dihubungi", promised_payment: "Janji Bayar", paid_after_contact: "Bayar Setelah Dihubungi", no_response: "Tidak Merespons", wrong_number: "Nomor Salah", requested_extension: "Minta Tenggang", refused: "Menolak", other: "Lainnya" };
export const CHANNEL_LABELS = { whatsapp: "WhatsApp", phone: "Telepon", in_person: "Tatap Muka", other: "Lainnya" };

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

export function WaRemindDialog({ student, onClose, onSaved }) {
  const [recipient, setRecipient] = useState("siswa");
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");
  const [fu, setFu] = useState("");
  const [outcome, setOutcome] = useState("contacted");
  const [sending, setSending] = useState(false);

  const loadPreview = async (rcpt) => {
    setLoading(true);
    try { const { data } = await api.get(`/collections/preview?student_id=${student.id}&recipient=${rcpt || recipient}`); setPreview(data); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setLoading(false); }
  };

  const send = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/collections/activities/send-wa", { student_id: student.id, recipient, idem_key: uid(), outcome, note, next_follow_up_at: fu || null });
      if (data.wa_sent) toast.success(data.wa_dry_run ? "Terkirim (dry-run) & tercatat" : "WA terkirim & tercatat");
      else toast.warning(`Tercatat, status WA: ${data.wa_status || "tidak terkirim"} — cek log WA`);
      onSaved && onSaved(data);
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setSending(false); }
  };

  return (
    <FormDialog open={!!student} onOpenChange={onClose} title={`Ingatkan via WA — ${student?.nama_lengkap}`} description="Preview pesan dari template payment_due. Pengiriman via dispatcher WhatsApp E1." onSubmit={send} submitLabel={sending ? "Mengirim..." : "Kirim & Catat"} testId="wa-remind-dialog">
      <div className="flex gap-1.5 mb-3">
        {[["siswa", "Siswa"], ["wali", "Wali"]].map(([k, l]) => <button key={k} type="button" onClick={() => { setRecipient(k); setPreview(null); loadPreview(k); }} className={`chip cursor-pointer ${recipient === k ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600"}`}>{l}</button>)}
        <button type="button" onClick={() => loadPreview()} className="chip cursor-pointer bg-white text-slate-600">Muat Preview</button>
      </div>
      {loading ? <Loading /> : preview ? (<>
        <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm whitespace-pre-wrap" data-testid="wa-preview-body">{preview.body}</div>
        <p className="text-xs text-slate-500 mt-1">Ke: {preview.recipient_name} ({preview.phone_masked}) · Template v{preview.template_version}{preview.dry_run ? " · DRY-RUN" : ""}{!preview.wa_enabled ? " · WA NONAKTIF" : ""}</p>
      </>) : <p className="text-sm text-slate-500">Klik Muat Preview untuk melihat pesan.</p>}
      <div className="grid grid-cols-2 gap-3 mt-3">
        <Field label="Outcome"><select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}>{Object.entries(OUTCOME_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Next Follow-up"><input type="date" className="input" value={fu} onChange={(e) => setFu(e.target.value)} /></Field>
      </div>
      <Field label="Catatan"><textarea className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="mis. Sudah diingatkan, janji transfer Jumat" /></Field>
    </FormDialog>
  );
}

export function LogDialog({ student, onClose, onSaved }) {
  const [form, setForm] = useState({ channel: "phone", outcome: "contacted", note: "", next_follow_up_at: "", next_follow_up_note: "" });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.note.trim()) return toast.error("Catatan wajib diisi");
    setSaving(true);
    try {
      const { data } = await api.post("/collections/activities", { student_id: student.id, channel: form.channel, outcome: form.outcome, note: form.note, next_follow_up_at: form.next_follow_up_at || null, next_follow_up_note: form.next_follow_up_note, idem_key: uid() });
      toast.success("Penagihan tercatat"); onSaved && onSaved(data); onClose();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setSaving(false); }
  };

  return (
    <FormDialog open={!!student} onOpenChange={onClose} title={`Catat Penagihan — ${student?.nama_lengkap}`} description="Untuk penagihan via telepon / tatap muka / channel lain." onSubmit={save} submitLabel={saving ? "Menyimpan..." : "Simpan"} testId="log-collection-dialog">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Channel"><select className="input" value={form.channel} onChange={(e) => set("channel", e.target.value)}>{Object.entries(CHANNEL_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Outcome"><select className="input" value={form.outcome} onChange={(e) => set("outcome", e.target.value)}>{Object.entries(OUTCOME_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Next Follow-up"><input type="date" className="input" value={form.next_follow_up_at} onChange={(e) => set("next_follow_up_at", e.target.value)} /></Field>
        <Field label="Catatan Follow-up"><input className="input" value={form.next_follow_up_note} onChange={(e) => set("next_follow_up_note", e.target.value)} placeholder="mis. Hubungi lagi Senin" /></Field>
      </div>
      <Field label="Catatan *"><textarea className="input" data-testid="log-collection-note" value={form.note} onChange={(e) => set("note", e.target.value)} placeholder="Hasil komunikasi..." required /></Field>
    </FormDialog>
  );
}

export function HistoryDialog({ student, onClose }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    if (!student) return;
    setRows(null);
    api.get(`/collections/students/${student.id}/activities`).then(({ data }) => setRows(data)).catch((e) => toast.error(errMsg(e)));
  }, [student]);
  return (
    <FormDialog open={!!student} onOpenChange={() => { setRows(null); onClose(); }} title={`Riwayat Penagihan — ${student?.nama_lengkap}`} description="Histori tercatat & beraudit." onSubmit={onClose} submitLabel="Tutup" testId="collection-history-dialog">
      {rows === null ? <Loading /> : rows.length === 0 ? <EmptyState text="Belum ada aktivitas penagihan" /> : (
        <div className="space-y-3 max-h-96 overflow-y-auto" data-testid="collection-history-list">
          {rows.map((a) => <div key={a.id} className="rounded-lg border p-3 text-sm">
            <div className="flex justify-between text-xs text-slate-500"><span>{fmtD(a.created_at?.slice(0, 10))} · {a.actor_name} ({a.actor_role})</span><span>{CHANNEL_LABELS[a.channel] || a.channel}</span></div>
            <div className="font-medium mt-1">Outcome: {OUTCOME_LABELS[a.outcome] || a.outcome}</div>
            {a.note && <p className="text-slate-600 mt-1">{a.note}</p>}
            <div className="text-xs text-slate-500 mt-1">Sisa saat itu: {rupiah(a.sisa_snapshot?.sisa ?? 0)}{a.wa_status ? ` · WA: ${a.wa_status}${a.wa_dry_run ? " (dry-run)" : ""}` : ""}{a.next_follow_up_at ? ` · Next: ${fmtD(a.next_follow_up_at)}${a.next_follow_up_note ? ` — ${a.next_follow_up_note}` : ""}` : ""}</div>
          </div>)}
        </div>)}
    </FormDialog>
  );
}

export function CollectionActions({ student, onChanged }) {
  const { can } = useAuth();
  const [wa, setWa] = useState(false);
  const [log, setLog] = useState(false);
  const [hist, setHist] = useState(false);
  return (<>
    <div className="flex gap-1 whitespace-nowrap">
      {can("whatsapp_send") && <button className="btn-ghost btn-sm" title="Ingatkan via WA" onClick={() => setWa(true)} data-testid={`col-wa-${student.id}`}><MessageCircle size={14} /></button>}
      <button className="btn-ghost btn-sm" title="Catat penagihan" onClick={() => setLog(true)} data-testid={`col-log-${student.id}`}><Phone size={14} /></button>
      <button className="btn-ghost btn-sm" title="Riwayat" onClick={() => setHist(true)} data-testid={`col-hist-${student.id}`}><History size={14} /></button>
    </div>
    {wa && <WaRemindDialog student={student} onClose={() => setWa(false)} onSaved={onChanged} />}
    {log && <LogDialog student={student} onClose={() => setLog(false)} onSaved={onChanged} />}
    {hist && <HistoryDialog student={student} onClose={() => setHist(false)} />}
  </>);
}
