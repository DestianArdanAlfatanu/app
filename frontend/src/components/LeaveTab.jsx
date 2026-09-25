import { useMemo, useState } from "react";
import { Plus, Check, X } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { Field, EmptyState, Loading, FormDialog } from "@/components/common";
import { fmtDate, today } from "@/lib/format";

const STATUS_CHIP = {
  menunggu: "bg-amber-50 text-amber-700 border-amber-200",
  disetujui: "bg-emerald-50 text-emerald-700 border-emerald-200",
  ditolak: "bg-red-50 text-red-700 border-red-200",
};
const STATUS_LABEL = { menunggu: "Menunggu", disetujui: "Disetujui", ditolak: "Ditolak" };

function calcDurasi(dari, sampai) {
  if (!dari || !sampai || dari > sampai) return 0;
  return Math.round((new Date(sampai) - new Date(dari)) / 86400000) + 1;
}

const EMPTY = { employee_id: "", jenis: "Cuti", dari: today(), sampai: today(), alasan: "" };

export default function LeaveTab({ employees }) {
  const { can } = useAuth();
  const writable = can("leave_write");
  const approver = can("leave_approve");
  const [filter, setFilter] = useState({ status: "", employee_id: "", dari: "", sampai: "" });
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [rejectId, setRejectId] = useState(null);
  const [rejectReason, setRejectReason] = useState("");

  const qs = useMemo(() => {
    const p = new URLSearchParams();
    if (filter.status) p.set("status", filter.status);
    if (filter.employee_id) p.set("employee_id", filter.employee_id);
    if (filter.dari) p.set("dari", filter.dari);
    if (filter.sampai) p.set("sampai", filter.sampai);
    const s = p.toString();
    return s ? `/leaves?${s}` : "/leaves";
  }, [filter]);
  const { data, loading, reload } = useApi(qs, [qs]);

  const activeEmployees = useMemo(
    () => (employees || []).filter((e) => e.aktif !== false),
    [employees]
  );
  const pendingCount = useMemo(() => (data || []).filter((l) => l.status === "menunggu").length, [data]);

  const create = async () => {
    if (!form.employee_id) { toast.error("Pilih karyawan terlebih dahulu."); return; }
    setSaving(true);
    try {
      await api.post("/leaves", { ...form, alasan: form.alasan || "" });
      toast.success("Pengajuan cuti berhasil dibuat.");
      setOpen(false); setForm(EMPTY); reload();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const approve = async (lv) => {
    if (!window.confirm("Setujui pengajuan cuti ini?")) return;
    try {
      await api.put(`/leaves/${lv.id}/decide`, { setuju: true });
      toast.success("Pengajuan cuti berhasil disetujui. Attendance pada periode cuti telah ditandai sebagai cuti.");
      reload();
    } catch (e) { toast.error(errMsg(e)); }
  };

  const reject = async () => {
    if (!rejectReason.trim()) { toast.error("Alasan penolakan wajib diisi."); return; }
    try {
      await api.put(`/leaves/${rejectId}/decide`, { setuju: false, alasan: rejectReason });
      toast.success("Pengajuan cuti ditolak.");
      setRejectId(null); setRejectReason(""); reload();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div>
      <div className="card p-4 mb-4 grid sm:grid-cols-[160px_1fr_160px_160px_auto] gap-3 items-end">
        <Field label="Status">
          <select className="input" data-testid="leave-filter-status" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
            <option value="">Semua</option>
            <option value="menunggu">Menunggu{pendingCount > 0 ? ` (${pendingCount})` : ""}</option>
            <option value="disetujui">Disetujui</option>
            <option value="ditolak">Ditolak</option>
          </select>
        </Field>
        <Field label="Karyawan">
          <select className="input" data-testid="leave-filter-employee" value={filter.employee_id} onChange={(e) => setFilter({ ...filter, employee_id: e.target.value })}>
            <option value="">Semua</option>
            {(employees || []).map((e) => <option key={e.id} value={e.id}>{e.nama}</option>)}
          </select>
        </Field>
        <Field label="Dari"><input type="date" className="input" data-testid="leave-filter-dari" value={filter.dari} onChange={(e) => setFilter({ ...filter, dari: e.target.value })} /></Field>
        <Field label="Sampai"><input type="date" className="input" data-testid="leave-filter-sampai" value={filter.sampai} onChange={(e) => setFilter({ ...filter, sampai: e.target.value })} /></Field>
        {writable && <button className="btn-red h-10" onClick={() => { setForm({ ...EMPTY, dari: today(), sampai: today() }); setOpen(true); }} data-testid="add-leave-btn"><Plus size={16} />Ajukan Cuti</button>}
      </div>

      {loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="leaves-table">
          <thead><tr><th>Nama</th><th>Jenis</th><th>Dari</th><th>Sampai</th><th>Durasi</th><th>Status</th><th>Pengaju</th><th>Approver</th><th></th></tr></thead>
          <tbody>
            {(data || []).length === 0 && <tr><td colSpan={9}><EmptyState text="Belum ada pengajuan cuti" /></td></tr>}
            {(data || []).map((lv) => (
              <tr key={lv.id} data-testid={`leave-row-${lv.id}`}>
                <td><p className="font-semibold">{lv.employee_nama || "-"}</p><p className="text-xs text-slate-400">{lv.jabatan || lv.tipe || ""}</p>{lv.alasan && <p className="text-xs text-slate-500 mt-1 max-w-[220px]">{lv.alasan}</p>}</td>
                <td>{lv.jenis}</td>
                <td className="whitespace-nowrap">{fmtDate(lv.dari)}</td>
                <td className="whitespace-nowrap">{fmtDate(lv.sampai)}</td>
                <td>{lv.durasi_hari} hari</td>
                <td><span className={`chip ${STATUS_CHIP[lv.status] || "bg-slate-100"}`}>{STATUS_LABEL[lv.status] || lv.status}</span>
                  {lv.status === "ditolak" && lv.reject_reason && <p className="text-xs text-slate-400 mt-1">{lv.reject_reason}</p>}</td>
                <td className="text-xs">{lv.created_by || "-"}</td>
                <td className="text-xs">{lv.approver_name || "-"}{lv.decided_at && <><br /><span className="text-slate-400">{fmtDate(lv.decided_at)}</span></>}</td>
                <td className="whitespace-nowrap">
                  {approver && lv.status === "menunggu" && (
                    <><button className="btn-ghost btn-sm text-emerald-700" title="Setujui" onClick={() => approve(lv)} data-testid={`approve-leave-${lv.id}`}><Check size={15} /></button>
                      <button className="btn-ghost btn-sm text-red-600" title="Tolak" onClick={() => { setRejectId(lv.id); setRejectReason(""); }} data-testid={`reject-leave-${lv.id}`}><X size={15} /></button></>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
      <p className="text-xs text-slate-400 mt-3">Cuti yang disetujui otomatis menandai absensi pada periode tersebut sebagai cuti.</p>

      <FormDialog open={open} onOpenChange={setOpen} title="Pengajuan Cuti" description="Isi data pengajuan. Durasi dihitung otomatis (kalender inklusif)." onSubmit={create} loading={saving} testId="leave-dialog">
        <Field label="Karyawan">
          <select className="input" data-testid="leave-employee-select" value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })} required>
            <option value="">— Pilih —</option>
            {activeEmployees.map((e) => <option key={e.id} value={e.id}>{e.nama} · {e.jabatan || e.tipe}</option>)}
          </select>
        </Field>
        <Field label="Jenis"><input className="input" data-testid="leave-jenis-input" value={form.jenis} onChange={(e) => setForm({ ...form, jenis: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Dari"><input type="date" className="input" data-testid="leave-dari-input" value={form.dari} onChange={(e) => setForm({ ...form, dari: e.target.value })} required /></Field>
          <Field label="Sampai"><input type="date" className="input" data-testid="leave-sampai-input" value={form.sampai} onChange={(e) => setForm({ ...form, sampai: e.target.value })} required /></Field>
        </div>
        <p className="text-sm text-slate-600" data-testid="leave-durasi-preview">Durasi: <b>{calcDurasi(form.dari, form.sampai)} hari</b></p>
        <Field label="Alasan"><textarea className="input" rows={3} data-testid="leave-alasan-input" value={form.alasan} onChange={(e) => setForm({ ...form, alasan: e.target.value })} placeholder="Alasan pengajuan cuti (opsional)" /></Field>
      </FormDialog>

      <FormDialog open={!!rejectId} onOpenChange={(v) => { if (!v) setRejectId(null); }} title="Tolak Pengajuan Cuti" description="Alasan penolakan wajib diisi dan tercatat di audit." onSubmit={reject} submitLabel="Tolak" testId="leave-reject-dialog">
        <Field label="Alasan penolakan"><textarea className="input" rows={3} data-testid="leave-reject-reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} required /></Field>
      </FormDialog>
    </div>
  );
}
