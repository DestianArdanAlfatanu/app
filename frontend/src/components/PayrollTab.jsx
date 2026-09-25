import { useMemo, useState } from "react";
import { Plus, Check, Wallet, Receipt, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { Field, EmptyState, Loading, FormDialog, Money } from "@/components/common";
import { rupiah, fmtDate, fmtDateTime } from "@/lib/format";

const STATUS_CHIP = {
  draft: "bg-slate-100 text-slate-700 border-slate-200",
  disetujui: "bg-emerald-50 text-emerald-700 border-emerald-200",
  dibayar: "bg-blue-50 text-blue-700 border-blue-200",
};
const STATUS_LABEL = { draft: "Draft", disetujui: "Disetujui", dibayar: "Dibayar" };
const curPeriode = () => new Date().toISOString().slice(0, 7);

const isHonor = (e) => e.tipe === "guru" && Number(e.honor_per_pertemuan || 0) > 0;

export default function PayrollTab({ employees }) {
  const { can } = useAuth();
  const writable = can("payroll_write");
  const approver = can("payroll_approve");
  const payer = can("payroll_pay");
  const [periode, setPeriode] = useState(curPeriode());
  const [fTipe, setFTipe] = useState("");
  const [fStatus, setFStatus] = useState("");

  const qs = `/payrolls?periode=${periode}${fTipe ? `&tipe=${fTipe}` : ""}${fStatus ? `&status=${fStatus}` : ""}`;
  const { data, loading, reload } = useApi(qs, [qs]);
  const rows = data || [];

  const { data: accounts } = useApi("/finance/accounts", [], payer);

  // ---- calculate dialog ----
  const [calcOpen, setCalcOpen] = useState(false);
  const [sel, setSel] = useState({});
  const [meetings, setMeetings] = useState({});
  const [preview, setPreview] = useState(null);
  const [calcBusy, setCalcBusy] = useState(false);
  const [suggest, setSuggest] = useState({});
  const activeEmps = useMemo(() => (employees || []).filter((e) => e.aktif !== false), [employees]);

  const loadSuggest = async (empId) => {
    try {
      const { data } = await api.get(`/payrolls/suggest-meetings?employee_id=${empId}&periode=${periode}`);
      setSuggest((s) => ({ ...s, [empId]: data }));
    } catch (e) { /* suggestion unavailable; HR types manually */ }
  };

  const openCalc = () => {
    const s = {}; activeEmps.forEach((e) => { s[e.id] = true; });
    const m = {}; activeEmps.forEach((e) => { if (isHonor(e)) m[e.id] = ""; });
    setSel(s); setMeetings(m); setPreview(null); setSuggest({}); setCalcOpen(true);
    activeEmps.filter((e) => isHonor(e)).forEach((e) => loadSuggest(e.id));
  };
  const calcBody = (forPreview) => ({
    periode,
    preview: forPreview,
    items: activeEmps.filter((e) => sel[e.id]).map((e) => ({
      employee_id: e.id,
      honor_pertemuan: isHonor(e) ? (meetings[e.id] === "" ? null : Number(meetings[e.id])) : 0,
    })),
  });
  const doPreview = async () => {
    setCalcBusy(true);
    try { setPreview((await api.post("/payrolls/calculate", calcBody(true))).data.rows); }
    catch (e) { toast.error(errMsg(e)); } finally { setCalcBusy(false); }
  };
  const doSave = async () => {
    setCalcBusy(true);
    try {
      const { data: r } = await api.post("/payrolls/calculate", calcBody(false));
      toast.success(`Payroll tersimpan (${r.rows.length} baru${r.skipped.length ? `, ${r.skipped.length} sudah ada` : ""})`);
      setCalcOpen(false); reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setCalcBusy(false); }
  };

  // ---- detail / edit / approve / pay / slip ----
  const [detail, setDetail] = useState(null);
  const [edit, setEdit] = useState(null);
  const [editForm, setEditForm] = useState({ bonus: 0, lembur: 0, honor_pertemuan: 0, honor_note: "", bonus_reason: "", lembur_reason: "", lembur_source_note: "", potongan: [], alasan: "" });
  const [editSuggest, setEditSuggest] = useState(null);
  const [saving, setSaving] = useState(false);
  const [payOpen, setPayOpen] = useState(false);
  const [payAcc, setPayAcc] = useState("");
  const [slip, setSlip] = useState(null);

  const openDetail = async (id) => {
    try { setDetail((await api.get(`/payrolls/${id}`)).data); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const openEdit = (p) => {
    setEdit(p);
    const prov = p.komponen?.provenance || {};
    setEditForm({
      bonus: p.komponen.bonus || 0, lembur: p.komponen.lembur || 0,
      honor_pertemuan: p.komponen.honor_pertemuan || 0,
      honor_note: prov.meetings?.note || "",
      bonus_reason: prov.bonus?.reason || "",
      lembur_reason: prov.lembur?.reason || "",
      lembur_source_note: prov.lembur?.source_note || "",
      potongan: (p.komponen.potongan || []).map((x) => ({ ...x })), alasan: "",
    });
    setEditSuggest(null);
    if (p.snapshot?.model === "honor") {
      api.get(`/payrolls/suggest-meetings?employee_id=${p.employee_id}&periode=${p.periode}`)
        .then(({ data }) => setEditSuggest(data)).catch(() => setEditSuggest(null));
    }
  };
  const saveEdit = async () => {
    if (!editForm.alasan.trim()) { toast.error("Alasan perubahan wajib diisi untuk audit."); return; }
    if (Number(editForm.bonus) > 0 && !editForm.bonus_reason.trim()) { toast.error("Reason bonus wajib diisi bila bonus > 0."); return; }
    if (Number(editForm.lembur) > 0 && !editForm.lembur_reason.trim()) { toast.error("Reason lembur wajib diisi bila lembur > 0."); return; }
    setSaving(true);
    try {
      const body = {
        bonus: Number(editForm.bonus), lembur: Number(editForm.lembur),
        honor_pertemuan: Number(editForm.honor_pertemuan), honor_note: editForm.honor_note,
        bonus_reason: editForm.bonus_reason, lembur_reason: editForm.lembur_reason,
        lembur_source_note: editForm.lembur_source_note,
        potongan: editForm.potongan.map((x) => ({ jenis: x.jenis, nominal: Number(x.nominal), keterangan: x.keterangan, source_ref: x.source_ref || null })),
        alasan: editForm.alasan,
      };
      const { data: p } = await api.put(`/payrolls/${edit.id}`, body);
      toast.success(`Payroll dikoreksi. Bersih: ${rupiah(p.bersih)}`);
      setEdit(null); setDetail(p); reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const approve = async (p) => {
    if (!window.confirm(`Setujui payroll ${p.employee_nama} periode ${p.periode}?`)) return;
    try { const { data: r } = await api.post(`/payrolls/${p.id}/approve`); toast.success("Payroll disetujui."); setDetail(r); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const pay = async () => {
    if (!payAcc) { toast.error("Pilih rekening pembayaran."); return; }
    setSaving(true);
    try {
      const { data: r } = await api.post(`/payrolls/${detail.id}/pay`, { account_id: payAcc });
      toast.success(r.already_paid ? "Payroll ini sudah dibayar sebelumnya." : "Payroll dibayar, transaksi keuangan tercatat.");
      setPayOpen(false); setDetail(r); reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const potTotal = (p) => (p.komponen.potongan || []).reduce((a, x) => a + Number(x.nominal || 0), 0) + (p.komponen.potongan_alfa || 0);
  const tambahan = (p) => (p.komponen.lembur || 0) + (p.komponen.bonus || 0);

  return (
    <div>
      <div className="card p-4 mb-4 grid sm:grid-cols-[180px_160px_160px_auto] gap-3 items-end">
        <Field label="Periode"><input type="month" className="input" data-testid="payroll-periode-input" value={periode} onChange={(e) => setPeriode(e.target.value)} /></Field>
        <Field label="Tipe">
          <select className="input" data-testid="payroll-filter-tipe" value={fTipe} onChange={(e) => setFTipe(e.target.value)}>
            <option value="">Semua</option><option value="karyawan">Karyawan</option><option value="guru">Guru</option>
          </select>
        </Field>
        <Field label="Status">
          <select className="input" data-testid="payroll-filter-status" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
            <option value="">Semua</option><option value="draft">Draft</option><option value="disetujui">Disetujui</option><option value="dibayar">Dibayar</option>
          </select>
        </Field>
        {writable && <button className="btn-red h-10" onClick={openCalc} data-testid="calc-payroll-btn"><Plus size={16} />Hitung Payroll</button>}
      </div>

      {loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="payrolls-table">
          <thead><tr><th>Nama</th><th>Slip</th><th>Gaji / Honor</th><th>Tunjangan</th><th>Tambahan</th><th>Potongan</th><th>Bruto</th><th>Bersih</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={10}><EmptyState text="Belum ada payroll pada periode ini" /></td></tr>}
            {rows.map((p) => (
              <tr key={p.id} data-testid={`payroll-row-${p.id}`}>
                <td><button className="font-semibold text-left hover:underline" onClick={() => openDetail(p.id)}>{p.employee_nama}</button>
                  <p className="text-xs text-slate-400">{p.snapshot?.tipe} · {p.periode}</p></td>
                <td className="text-xs mono">{p.no_slip}</td>
                <td><Money value={p.komponen.base} /></td>
                <td><Money value={p.komponen.tunjangan_hitung} /></td>
                <td><Money value={tambahan(p)} /></td>
                <td><Money value={potTotal(p)} /></td>
                <td><Money value={p.bruto} /></td>
                <td><Money value={p.bersih} className="font-semibold" /></td>
                <td><span className={`chip ${STATUS_CHIP[p.status]}`}>{STATUS_LABEL[p.status]}</span></td>
                <td className="whitespace-nowrap">
                  {approver && p.status === "draft" && <button className="btn-ghost btn-sm text-emerald-700" title="Setujui" onClick={async () => { await approve(p); }} data-testid={`approve-payroll-${p.id}`}><Check size={15} /></button>}
                  {payer && p.status === "disetujui" && (p.bersih || 0) > 0 && <button className="btn-ghost btn-sm text-blue-700" title="Bayar" onClick={async () => { await openDetail(p.id); setPayAcc(""); setPayOpen(true); }} data-testid={`pay-payroll-${p.id}`}><Wallet size={15} /></button>}
                  <button className="btn-ghost btn-sm" title="Slip" onClick={async () => { await openDetail(p.id); setSlip(true); }} data-testid={`slip-payroll-${p.id}`}><Receipt size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}

      {/* Calculate dialog */}
      <FormDialog open={calcOpen} onOpenChange={setCalcOpen} title={`Hitung Payroll ${periode}`} description="Payroll baru berstatus draft. Guru honor wajib diisi jumlah pertemuan aktual." onSubmit={doSave} submitLabel="Simpan Draft" loading={calcBusy} testId="payroll-calc-dialog" wide footer={null}>
        <div className="max-h-64 overflow-y-auto border border-slate-200 rounded-md divide-y">
          {activeEmps.map((e) => (
            <label key={e.id} className="flex items-center gap-3 p-2.5 text-sm">
              <input type="checkbox" checked={!!sel[e.id]} onChange={(ev) => setSel({ ...sel, [e.id]: ev.target.checked })} data-testid={`calc-sel-${e.id}`} />
              <span className="flex-1"><b>{e.nama}</b> <span className="text-slate-400 text-xs">{e.tipe} · {isHonor(e) ? `honor ${rupiah(e.honor_per_pertemuan)}/pertemuan` : `gaji ${rupiah(e.gaji_pokok)}`}</span>
                {isHonor(e) && sel[e.id] && suggest[e.id] != null && <span className="block text-xs text-slate-500" title={(suggest[e.id].suggestions || []).map((x) => `${x.tanggal} ${x.class_nama}`).join(", ") || "tanpa aktivitas"}>Saran: {suggest[e.id].suggested_meetings} pertemuan (unverified-presence) <button type="button" className="text-red-600 font-semibold" onClick={() => setMeetings({ ...meetings, [e.id]: String(suggest[e.id].suggested_meetings) })} data-testid={`calc-use-suggest-${e.id}`}>pakai</button></span>}</span>
              {isHonor(e) && sel[e.id] && <input type="number" min={0} className="input mono w-28" placeholder="Pertemuan" data-testid={`calc-meet-${e.id}`} value={meetings[e.id] ?? ""} onChange={(ev) => setMeetings({ ...meetings, [e.id]: ev.target.value })} />}
            </label>
          ))}
        </div>
        {preview && (
          <div className="table-wrap"><table className="tbl" data-testid="payroll-preview-table">
            <thead><tr><th>Nama</th><th>Bruto</th><th>Bersih</th></tr></thead>
            <tbody>{preview.map((p) => <tr key={p.employee_id}><td>{p.snapshot.nama}</td><td><Money value={p.bruto} /></td><td><Money value={p.bersih} className="font-semibold" /></td></tr>)}</tbody>
          </table></div>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <button type="button" className="btn-outline" onClick={() => setCalcOpen(false)}>Batal</button>
          <button type="button" className="btn-outline" onClick={doPreview} disabled={calcBusy} data-testid="payroll-preview-btn">Preview</button>
          <button type="button" className="btn-primary" onClick={doSave} disabled={calcBusy} data-testid="payroll-save-btn">{calcBusy ? "Menyimpan..." : "Simpan Draft"}</button>
        </div>
      </FormDialog>

      {/* Detail dialog */}
      <FormDialog open={!!detail} onOpenChange={(v) => { if (!v) setDetail(null); }} title={detail ? `Payroll ${detail.employee_nama} · ${detail.periode}` : ""} description={detail?.no_slip} testId="payroll-detail-dialog" wide footer={null}>
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <p>Status: <span className={`chip ${STATUS_CHIP[detail.status]}`}>{STATUS_LABEL[detail.status]}</span></p>
              <p>Model: <b>{detail.snapshot?.model === "honor" ? "Honor pertemuan" : "Gaji bulanan"}</b></p>
              <p>Gaji pokok (snapshot): <Money value={detail.snapshot?.gaji_pokok} /></p>
              <p>Tunjangan (snapshot): <Money value={detail.snapshot?.tunjangan} /></p>
              {detail.snapshot?.model === "honor" && <p>Tarif: <Money value={detail.snapshot?.honor_per_pertemuan} /> × {detail.komponen.honor_pertemuan} pertemuan = <Money value={detail.komponen.honor_total} /></p>}
              <p>Kehadiran: hadir {detail.komponen.attendance.hadir}, terlambat {detail.komponen.attendance.terlambat}, izin {detail.komponen.attendance.izin}, sakit {detail.komponen.attendance.sakit}, cuti {detail.komponen.attendance.cuti}, alfa {detail.komponen.attendance.alfa}</p>
              <p>Hari aktif: {detail.komponen.hari_aktif}/{detail.komponen.hari_kalender}</p>
              <p>Lembur: <Money value={detail.komponen.lembur} /> · Bonus: <Money value={detail.komponen.bonus} /></p>
              <div>Potongan: {(detail.komponen.potongan || []).length === 0 && detail.komponen.potongan_alfa === 0 ? "-" : (
                <ul className="list-disc ml-5">{detail.komponen.potongan_alfa > 0 && <li>Alfa ({detail.komponen.attendance.alfa} hari): <Money value={detail.komponen.potongan_alfa} /></li>}
                  {detail.komponen.potongan.map((x, i) => <li key={i}>{x.jenis || "Potongan"}: <Money value={x.nominal} />{x.keterangan ? ` (${x.keterangan})` : ""}{x.source_ref?.source_note ? ` [ref: ${x.source_ref.source_note}]` : ""}</li>)}</ul>)}</div>
              {detail.komponen.provenance && (detail.komponen.provenance.bonus?.reason || detail.komponen.provenance.lembur?.reason || detail.komponen.provenance.meetings?.note) && (
                <div className="text-xs text-slate-500" data-testid="payroll-provenance">Provenance: {[detail.komponen.provenance.meetings?.note && `pertemuan: ${detail.komponen.provenance.meetings.note} (${detail.komponen.provenance.meetings.actor || "-"})`, detail.komponen.provenance.lembur?.reason && `lembur: ${detail.komponen.provenance.lembur.reason}`, detail.komponen.provenance.bonus?.reason && `bonus: ${detail.komponen.provenance.bonus.reason}`].filter(Boolean).join(" · ")}</div>)}
              <p className="text-base">Bruto: <Money value={detail.bruto} className="font-semibold" /> · Bersih: <Money value={detail.bersih} className="font-semibold" /></p>
              <p className="text-xs text-slate-400">Dihitung {detail.calculated_by} · {fmtDateTime(detail.calculated_at)}{detail.approved_by && ` · Disetujui ${detail.approved_by} · ${fmtDateTime(detail.approved_at)}`}{detail.paid_by && ` · Dibayar ${detail.paid_by} · ${fmtDateTime(detail.paid_at)}`}</p>
            </div>
            <div className="flex justify-end gap-2 flex-wrap">
              <button type="button" className="btn-outline" onClick={() => setSlip(true)} data-testid="payroll-slip-btn"><Receipt size={15} />Slip</button>
              {writable && detail.status === "draft" && <button type="button" className="btn-outline" onClick={() => openEdit(detail)} data-testid="payroll-edit-btn"><Pencil size={15} />Koreksi</button>}
              {approver && detail.status === "draft" && <button type="button" className="btn-primary" onClick={() => approve(detail)} data-testid="payroll-approve-btn"><Check size={15} />Setujui</button>}
              {payer && detail.status === "disetujui" && (detail.bersih || 0) > 0 && <button type="button" className="btn-primary" onClick={() => { setPayAcc(""); setPayOpen(true); }} data-testid="payroll-pay-btn"><Wallet size={15} />Bayar</button>}
              {payer && detail.status === "disetujui" && (detail.bersih || 0) <= 0 && <p className="text-xs text-red-600">Payroll bersih nol/negatif tidak dapat dibayar.</p>}
            </div>
          </div>
        )}
      </FormDialog>

      {/* Edit draft dialog */}
      <FormDialog open={!!edit} onOpenChange={(v) => { if (!v) setEdit(null); }} title="Koreksi Payroll Draft" description="Perubahan dihitung ulang, snapshot master tidak berubah, tercatat di audit." onSubmit={saveEdit} loading={saving} testId="payroll-edit-dialog" wide>
        {edit?.snapshot?.model === "honor" && <Field label="Pertemuan aktual"><input type="number" min={0} className="input mono" data-testid="edit-meetings-input" value={editForm.honor_pertemuan} onChange={(e) => setEditForm({ ...editForm, honor_pertemuan: e.target.value })} /></Field>}
        {edit?.snapshot?.model === "honor" && (
          <div className="rounded-md bg-slate-50 border border-slate-200 p-2.5 text-xs text-slate-600" data-testid="edit-suggest-panel">
            {editSuggest == null ? "Memuat saran pertemuan…" : <>Saran: <b>{editSuggest.suggested_meetings} pertemuan</b> (unverified-presence — kehadiran guru tidak dibuktikan)
              {editSuggest.suggestions.length > 0 && <ul className="list-disc ml-5 mt-1">{editSuggest.suggestions.map((s, i) => <li key={i}>{s.tanggal} · {s.class_nama} · {s.evidence_count} absensi siswa</li>)}</ul>}
              <button type="button" className="text-red-600 font-semibold mt-1" onClick={() => setEditForm({ ...editForm, honor_pertemuan: editSuggest.suggested_meetings, honor_note: `Dikonfirmasi dari saran ${editSuggest.suggested_meetings} pertemuan` })} data-testid="edit-use-suggest-btn">Gunakan sebagai actual (HR konfirmasi)</button></>}
          </div>)}
        {edit?.snapshot?.model === "honor" && <Field label="Catatan konfirmasi pertemuan"><input className="input" data-testid="edit-honor-note-input" value={editForm.honor_note} onChange={(e) => setEditForm({ ...editForm, honor_note: e.target.value })} placeholder="mis. Dikonfirmasi dari rekap kelas" /></Field>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Lembur (Rp)"><input type="number" min={0} className="input mono" data-testid="edit-lembur-input" value={editForm.lembur} onChange={(e) => setEditForm({ ...editForm, lembur: e.target.value })} /></Field>
          <Field label="Bonus (Rp)"><input type="number" min={0} className="input mono" data-testid="edit-bonus-input" value={editForm.bonus} onChange={(e) => setEditForm({ ...editForm, bonus: e.target.value })} /></Field>
          <Field label="Reason lembur *"><input className="input" data-testid="edit-lembur-reason-input" value={editForm.lembur_reason} onChange={(e) => setEditForm({ ...editForm, lembur_reason: e.target.value })} placeholder="wajib bila lembur > 0" /></Field>
          <Field label="Source ref lembur"><input className="input" data-testid="edit-lembur-source-input" value={editForm.lembur_source_note} onChange={(e) => setEditForm({ ...editForm, lembur_source_note: e.target.value })} placeholder="mis. 2026-01-05 s.d. 2026-01-07" /></Field>
        </div>
        <Field label="Reason bonus *"><input className="input" data-testid="edit-bonus-reason-input" value={editForm.bonus_reason} onChange={(e) => setEditForm({ ...editForm, bonus_reason: e.target.value })} placeholder="wajib bila bonus > 0" /></Field>
        <Field label="Potongan (satu per baris: jenis|nominal|keterangan|source_note)">
          <textarea className="input mono" rows={3} data-testid="edit-potongan-input"
            value={editForm.potongan.map((x) => `${x.jenis}|${x.nominal}|${x.keterangan || ""}|${x.source_ref?.source_note || ""}`).join("\n")}
            onChange={(e) => setEditForm({ ...editForm, potongan: e.target.value.split("\n").filter((l) => l.trim()).map((l) => { const [jenis, nominal, keterangan, source_note] = l.split("|"); return { jenis: (jenis || "").trim(), nominal: Number(nominal) || 0, keterangan: (keterangan || "").trim(), source_ref: (source_note || "").trim() ? { source_type: "manual_reason", source_note: source_note.trim() } : null }; }) })} />
        </Field>
        <Field label="Alasan perubahan (wajib)"><input className="input" data-testid="edit-alasan-input" value={editForm.alasan} onChange={(e) => setEditForm({ ...editForm, alasan: e.target.value })} required /></Field>
      </FormDialog>

      {/* Pay dialog */}
      <FormDialog open={payOpen} onOpenChange={setPayOpen} title="Bayar Payroll" description={detail ? `${detail.employee_nama} · ${detail.periode} · bersih ${rupiah(detail.bersih)}` : ""} onSubmit={pay} submitLabel="Bayar" loading={saving} testId="payroll-pay-dialog">
        <Field label="Rekening pembayaran">
          <select className="input" data-testid="pay-account-select" value={payAcc} onChange={(e) => setPayAcc(e.target.value)}>
            <option value="">— Pilih —</option>
            {(accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama} · {rupiah(a.saldo)}</option>)}
          </select>
        </Field>
      </FormDialog>

      {/* Slip dialog */}
      <FormDialog open={!!slip} onOpenChange={(v) => { if (!v) setSlip(null); }} title="Slip Gaji" testId="payroll-slip-dialog" footer={null} wide>
        {detail && (
          <div>
            <div className="print-area" data-testid="payroll-slip">
              <div className="text-center mb-4"><h2 className="font-bold text-lg">Slip Gaji / Honor</h2><p className="text-sm text-slate-500">LPK Penyaluran Kerja Jepang</p><p className="text-xs mono">{detail.no_slip} · Periode {detail.periode}</p></div>
              <table className="tbl"><tbody>
                <tr><td>Nama</td><td className="font-semibold">{detail.employee_nama}</td></tr>
                <tr><td>Jabatan / Tipe</td><td>{detail.snapshot?.jabatan} / {detail.snapshot?.tipe}</td></tr>
                <tr><td>Status</td><td>{STATUS_LABEL[detail.status]}{detail.paid_at ? ` · dibayar ${fmtDate(detail.paid_at)}` : ""}</td></tr>
                <tr><td colSpan={2} className="font-semibold bg-slate-50">Rincian</td></tr>
                {detail.snapshot?.model === "honor"
                  ? <tr><td>Honor ({detail.komponen.honor_pertemuan} pertemuan × {rupiah(detail.snapshot?.honor_per_pertemuan)})</td><td><Money value={detail.komponen.honor_total} /></td></tr>
                  : <tr><td>Gaji pokok (prorata {detail.komponen.hari_aktif}/{detail.komponen.hari_kalender} hari)</td><td><Money value={detail.komponen.base} /></td></tr>}
                <tr><td>Tunjangan</td><td><Money value={detail.komponen.tunjangan_hitung} /></td></tr>
                <tr><td>Lembur</td><td><Money value={detail.komponen.lembur} /></td></tr>
                <tr><td>Bonus</td><td><Money value={detail.komponen.bonus} /></td></tr>
                <tr><td>Potongan alfa ({detail.komponen.attendance.alfa} hari)</td><td><Money value={detail.komponen.potongan_alfa} /></td></tr>
                {(detail.komponen.potongan || []).map((x, i) => <tr key={i}><td>Potongan: {x.jenis}{x.keterangan ? ` (${x.keterangan})` : ""}</td><td><Money value={x.nominal} /></td></tr>)}
                <tr><td className="font-semibold">Bruto</td><td><Money value={detail.bruto} className="font-semibold" /></td></tr>
                <tr><td className="font-semibold">Bersih</td><td><Money value={detail.bersih} className="font-semibold" /></td></tr>
              </tbody></table>
              <p className="text-xs text-slate-400 mt-3">Dihitung {detail.calculated_by} · {fmtDate(detail.calculated_at)}{detail.approved_by ? ` · Disetujui ${detail.approved_by}` : ""}{detail.paid_by ? ` · Dibayar ${detail.paid_by}` : ""}</p>
            </div>
            <div className="flex justify-end gap-2 pt-3 no-print">
              <button type="button" className="btn-outline" onClick={() => window.print()} data-testid="slip-print-btn">Cetak / PDF</button>
            </div>
          </div>
        )}
      </FormDialog>
    </div>
  );
}
