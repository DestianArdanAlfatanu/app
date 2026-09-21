import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Pencil, ArrowRightCircle } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, StatusBadge, Loading, FormDialog, Field, Tabs, Progress } from "@/components/common";
import { StudentForm, normalizeStudent } from "@/components/StudentForm";
import { rupiah, STATUS_LABELS, STATUS_ORDER, fmtDate } from "@/lib/format";
import { BiodataTab, SeleksiTab, DokumenTab } from "@/components/student/ProfileTabs";
import { PembayaranTab, AkademikTab, JepangTab } from "@/components/student/ProgressTabs";

export default function StudentDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const { can } = useAuth();
  const { data: s, loading, reload } = useApi(`/students/${id}`);
  const [tab, setTab] = useState("biodata");
  const [edit, setEdit] = useState(false);
  const [form, setForm] = useState(null);
  const [statusOpen, setStatusOpen] = useState(false);
  const [st, setSt] = useState({ status: "", catatan: "" });
  const [saving, setSaving] = useState(false);

  if (loading && !s) return <Loading />;
  if (!s) return <p>Siswa tidak ditemukan</p>;

  const saveEdit = async () => {
    setSaving(true);
    try { await api.put(`/students/${id}`, normalizeStudent(form)); toast.success("Data siswa diperbarui"); setEdit(false); reload(); }
    catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const saveStatus = async () => {
    setSaving(true);
    try { await api.put(`/students/${id}/status`, st); toast.success(`Status diubah ke ${STATUS_LABELS[st.status]}`); setStatusOpen(false); reload(); }
    catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const pct = s.pembayaran.total ? Math.round((s.pembayaran.bayar / s.pembayaran.total) * 100) : 0;
  const idx = STATUS_ORDER.indexOf(s.status);

  return (
    <div>
      <button onClick={() => nav(-1)} className="btn-ghost btn-sm mb-3 -ml-2" data-testid="back-btn"><ArrowLeft size={14} />Kembali</button>
      <PageHeader title={s.nama_lengkap} subtitle={`NIK ${s.nik || "-"} · ${s.usia ?? "-"} tahun · ${s.jenis_kelamin === "L" ? "Laki-laki" : "Perempuan"} · ${s.alamat?.kabupaten || ""}`}>
        <StatusBadge status={s.status} testId="student-status-badge" />
        {can("siswa_write") && <>
          <button className="btn-outline" onClick={() => { setForm({ ...s, alamat: s.alamat || {} }); setEdit(true); }} data-testid="edit-student-btn"><Pencil size={15} />Edit</button>
          <button className="btn-primary" onClick={() => { setSt({ status: STATUS_ORDER[Math.min(idx + 1, 11)] || s.status, catatan: "" }); setStatusOpen(true); }} data-testid="change-status-btn"><ArrowRightCircle size={15} />Ubah Status</button>
        </>}
      </PageHeader>

      <div className="card p-3 mb-5 overflow-x-auto fade-up" data-testid="status-stepper">
        <div className="flex items-center min-w-max">
          {STATUS_ORDER.filter((x) => x !== "gagal").map((x, i) => {
            const done = i < idx, cur = x === s.status;
            return (
              <div key={x} className="flex items-center">
                <div className={`flex items-center gap-1.5 px-2.5 py-1 rounded text-[11px] font-semibold whitespace-nowrap ${cur ? "bg-red-600 text-white" : done ? "text-emerald-700" : "text-slate-400"}`}>
                  <span className={`h-1.5 w-1.5 rounded-full ${cur ? "bg-white" : done ? "bg-emerald-500" : "bg-slate-300"}`} />{STATUS_LABELS[x].split(" ")[0]}
                </div>
                {i < 11 && <span className={`h-px w-4 ${done ? "bg-emerald-400" : "bg-slate-200"}`} />}
              </div>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-6">
        <div className="card p-4 col-span-2 lg:col-span-2">
          <p className="label">Pembayaran</p>
          <div className="flex items-baseline justify-between gap-2"><span className="mono font-semibold text-slate-900">{rupiah(s.pembayaran.bayar)}</span><span className="text-xs text-slate-500 mono">dari {rupiah(s.pembayaran.total)}</span></div>
          <Progress value={pct} tone={s.pembayaran.sisa > 0 ? "bg-amber-500" : "bg-emerald-500"} />
          <p className={`text-xs mt-1.5 font-medium ${s.pembayaran.sisa > 0 ? "text-red-600" : "text-emerald-600"}`} data-testid="student-sisa">{s.pembayaran.sisa > 0 ? `Sisa ${rupiah(s.pembayaran.sisa)}${s.jatuh_tempo ? ` · jatuh tempo ${fmtDate(s.jatuh_tempo)}` : ""}` : "Lunas"}</p>
        </div>
        <div className="card p-4"><p className="label">Kehadiran</p><p className="stat-num text-xl" data-testid="student-kehadiran">{s.absensi.persentase}%</p><p className="text-xs text-slate-500">{s.absensi.hadir} hadir · {s.absensi.alfa} alfa</p></div>
        <div className="card p-4"><p className="label">Nilai Rata-rata</p><p className="stat-num text-xl" data-testid="student-nilai">{s.nilai_rata ?? "-"}</p><p className="text-xs text-slate-500">{s.kelas?.nama || "Belum masuk kelas"}</p></div>
        <div className="card p-4"><p className="label">Dokumen</p><p className="stat-num text-xl" data-testid="student-dokumen">{s.dokumen.lengkap}/{s.dokumen.total}</p><p className="text-xs text-slate-500">{s.dokumen.total - s.dokumen.lengkap} belum tersedia</p></div>
      </div>

      <Tabs active={tab} onChange={setTab} testPrefix="student-tab" tabs={[
        { key: "biodata", label: "Biodata" }, { key: "seleksi", label: "Seleksi", count: s.selections.length }, { key: "dokumen", label: "Dokumen" },
        { key: "pembayaran", label: "Pembayaran", count: s.payments.length }, { key: "akademik", label: "Absensi & Nilai" }, { key: "jepang", label: "Job Order & Jepang", count: s.interviews.length },
      ]} />
      {tab === "biodata" && <BiodataTab s={s} />}
      {tab === "seleksi" && <SeleksiTab s={s} reload={reload} />}
      {tab === "dokumen" && <DokumenTab s={s} reload={reload} />}
      {tab === "pembayaran" && <PembayaranTab s={s} reload={reload} />}
      {tab === "akademik" && <AkademikTab s={s} />}
      {tab === "jepang" && <JepangTab s={s} />}

      {form && <FormDialog open={edit} onOpenChange={setEdit} title="Edit Data Siswa" onSubmit={saveEdit} loading={saving} testId="edit-student-dialog" wide><StudentForm form={form} setForm={setForm} /></FormDialog>}
      <FormDialog open={statusOpen} onOpenChange={setStatusOpen} title="Ubah Status Siswa" description="Perubahan status tercatat di histori & audit trail." onSubmit={saveStatus} loading={saving} testId="status-dialog">
        <Field label="Status Baru"><select className="input" data-testid="status-select" value={st.status} onChange={(e) => setSt({ ...st, status: e.target.value })}>{STATUS_ORDER.map((x) => <option key={x} value={x}>{STATUS_LABELS[x]}</option>)}</select></Field>
        <Field label="Catatan"><textarea className="input" data-testid="status-catatan-input" value={st.catatan} onChange={(e) => setSt({ ...st, catatan: e.target.value })} placeholder="Alasan / keterangan perubahan" /></Field>
      </FormDialog>
    </div>
  );
}
