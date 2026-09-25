import { useState, useEffect } from "react";
import { toast } from "sonner";
import { ClipboardPen, History } from "lucide-react";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { FormDialog, Field, Loading, EmptyState } from "@/components/common";
import { fmtDate as fmtD } from "@/lib/format";

export const CF_OUTCOME_LABELS = { terhubungi: "Terhubungi", janji_datang: "Janji Datang", minat: "Berminat", mendaftar: "Mendaftar", tidak_aktif: "Tidak Aktif", nomor_salah: "Nomor Salah", menolak: "Menolak", lainnya: "Lainnya" };
export const CF_CHANNEL_LABELS = { whatsapp: "WhatsApp", phone: "Telepon", in_person: "Tatap Muka", sosmed: "Sosmed", kunjungan: "Kunjungan", other: "Lainnya" };

const uid = () => (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

export function CfWaDialog({ student, onClose, onSaved }) {
  const [preview, setPreview] = useState(null);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState("");
  const [fu, setFu] = useState("");
  const [tgl, setTgl] = useState("");
  const [outcome, setOutcome] = useState("terhubungi");
  const [sending, setSending] = useState(false);

  const loadPreview = async () => {
    setLoading(true);
    try { const { data } = await api.get(`/candidate-followups/preview?student_id=${student.id}&tanggal_follow_up=${encodeURIComponent(tgl)}`); setPreview(data); }
    catch (e) { toast.error(errMsg(e)); }
    finally { setLoading(false); }
  };

  const send = async () => {
    setSending(true);
    try {
      const { data } = await api.post("/candidate-followups/activities/send-wa", { student_id: student.id, idem_key: uid(), outcome, note, next_follow_up_at: fu || null, tanggal_follow_up: tgl });
      if (data.wa_sent) toast.success(data.wa_dry_run ? "Terkirim (dry-run) & tercatat" : "WA terkirim & tercatat");
      else toast.warning(`Tercatat, status WA: ${data.wa_status || "tidak terkirim"} — cek log WA`);
      onSaved && onSaved(data);
      onClose();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setSending(false); }
  };

  return (
    <FormDialog open={!!student} onOpenChange={onClose} title={`Sapa via WA — ${student?.nama_lengkap}`} description="Preview dari template followup_calon. Pengiriman via dispatcher WhatsApp E1." onSubmit={send} submitLabel={sending ? "Mengirim..." : "Kirim & Catat"} testId="cf-wa-dialog">
      <div className="grid sm:grid-cols-2 gap-3 mb-3">
        <Field label="Rencana follow-up (untuk pesan)"><input type="date" className="input" value={tgl} onChange={(e) => setTgl(e.target.value)} /></Field>
        <div className="flex items-end"><button type="button" onClick={loadPreview} className="chip cursor-pointer bg-white text-slate-600">Muat Preview</button></div>
      </div>
      {loading ? <Loading /> : preview ? (<>
        <div className="rounded-lg bg-emerald-50 border border-emerald-200 p-3 text-sm whitespace-pre-wrap" data-testid="cf-wa-preview-body">{preview.body}</div>
        <p className="text-xs text-slate-500 mt-1">Ke: {preview.recipient_name} ({preview.phone_masked}) · Template v{preview.template_version}{preview.dry_run ? " · DRY-RUN" : ""}{!preview.wa_enabled ? " · WA NONAKTIF" : ""}</p>
      </>) : <p className="text-sm text-slate-500">Klik Muat Preview untuk melihat pesan.</p>}
      <div className="grid grid-cols-2 gap-3 mt-3">
        <Field label="Outcome"><select className="input" value={outcome} onChange={(e) => setOutcome(e.target.value)}>{Object.entries(CF_OUTCOME_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Next Follow-up"><input type="date" className="input" value={fu} onChange={(e) => setFu(e.target.value)} /></Field>
      </div>
      <Field label="Catatan"><textarea className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="mis. Tertarik, minta brosur biaya" /></Field>
    </FormDialog>
  );
}

export function CfLogDialog({ student, onClose, onSaved }) {
  const [form, setForm] = useState({ channel: "phone", outcome: "terhubungi", note: "", next_follow_up_at: "", next_follow_up_note: "" });
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const save = async () => {
    if (!form.note.trim()) return toast.error("Catatan wajib diisi");
    setSaving(true);
    try {
      const { data } = await api.post("/candidate-followups/activities", { student_id: student.id, channel: form.channel, outcome: form.outcome, note: form.note, next_follow_up_at: form.next_follow_up_at || null, next_follow_up_note: form.next_follow_up_note, idem_key: uid() });
      toast.success("Follow-up tercatat"); onSaved && onSaved(data); onClose();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setSaving(false); }
  };

  return (
    <FormDialog open={!!student} onOpenChange={onClose} title={`Catat Follow-up — ${student?.nama_lengkap}`} description="Untuk kontak via telepon / kunjungan / sosmed / channel lain." onSubmit={save} submitLabel={saving ? "Menyimpan..." : "Simpan"} testId="cf-log-dialog">
      <div className="grid grid-cols-2 gap-3">
        <Field label="Channel"><select className="input" value={form.channel} onChange={(e) => set("channel", e.target.value)}>{Object.entries(CF_CHANNEL_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Outcome"><select className="input" value={form.outcome} onChange={(e) => set("outcome", e.target.value)}>{Object.entries(CF_OUTCOME_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Next Follow-up"><input type="date" className="input" value={form.next_follow_up_at} onChange={(e) => set("next_follow_up_at", e.target.value)} /></Field>
        <Field label="Catatan Follow-up"><input className="input" value={form.next_follow_up_note} onChange={(e) => set("next_follow_up_note", e.target.value)} placeholder="mis. Hubungi lagi Senin" /></Field>
      </div>
      <Field label="Catatan *"><textarea className="input" data-testid="cf-log-note" value={form.note} onChange={(e) => set("note", e.target.value)} placeholder="Hasil komunikasi..." required /></Field>
    </FormDialog>
  );
}

export function CfHistoryDialog({ student, onClose }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    if (!student) return;
    setRows(null);
    api.get(`/candidate-followups/students/${student.id}/activities`).then(({ data }) => setRows(data)).catch((e) => toast.error(errMsg(e)));
  }, [student]);
  return (
    <FormDialog open={!!student} onOpenChange={onClose} title={`Riwayat Follow-up — ${student?.nama_lengkap}`} description="Histori tercatat & beraudit." onSubmit={onClose} submitLabel="Tutup" testId="cf-history-dialog">
      {rows === null ? <Loading /> : rows.length === 0 ? <EmptyState text="Belum ada follow-up" /> : (
        <div className="space-y-3 max-h-96 overflow-y-auto" data-testid="cf-history-list">
          {rows.map((a) => <div key={a.id} className="rounded-lg border p-3 text-sm">
            <div className="flex justify-between text-xs text-slate-500"><span>{fmtD(a.created_at?.slice(0, 10))} · {a.actor_name} ({a.actor_role})</span><span>{CF_CHANNEL_LABELS[a.channel] || a.channel}</span></div>
            <div className="font-medium mt-1">Outcome: {CF_OUTCOME_LABELS[a.outcome] || a.outcome}</div>
            {a.note && <p className="text-slate-600 mt-1">{a.note}</p>}
            <div className="text-xs text-slate-500 mt-1">{a.wa_status ? `WA: ${a.wa_status}${a.wa_dry_run ? " (dry-run)" : ""} · ` : ""}{a.next_follow_up_at ? `Next: ${fmtD(a.next_follow_up_at)}${a.next_follow_up_note ? ` — ${a.next_follow_up_note}` : ""}` : "Tanpa follow-up lanjutan"}</div>
          </div>)}
        </div>)}
    </FormDialog>
  );
}

export function CfActions({ student, onChanged }) {
  const { can } = useAuth();
  const [log, setLog] = useState(false);
  const [hist, setHist] = useState(false);
  if (!can("followup")) return null;
  return (<>
    <div className="flex gap-1 whitespace-nowrap">
      <button className="btn-ghost btn-sm" title="Catat follow-up" onClick={() => setLog(true)} data-testid={`cf-log-${student.id}`}><ClipboardPen size={14} /></button>
      <button className="btn-ghost btn-sm" title="Riwayat" onClick={() => setHist(true)} data-testid={`cf-hist-${student.id}`}><History size={14} /></button>
    </div>
    {log && <CfLogDialog student={student} onClose={() => setLog(false)} onSaved={onChanged} />}
    {hist && <CfHistoryDialog student={student} onClose={() => setHist(false)} />}
  </>);
}
