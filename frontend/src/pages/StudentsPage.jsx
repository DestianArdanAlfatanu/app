import { useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Plus, Download } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, StatusBadge, EmptyState, Loading, FormDialog, Progress } from "@/components/common";
import { StudentForm, EMPTY_STUDENT, normalizeStudent } from "@/components/StudentForm";
import { rupiah, STATUS_LABELS, STATUS_ORDER, downloadCSV } from "@/lib/format";

export default function StudentsPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status") || "";
  const [q, setQ] = useState("");
  const { can } = useAuth();
  const nav = useNavigate();
  const { data, loading, reload } = useApi(`/students${status ? `?status=${status}` : ""}`);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY_STUDENT);
  const [saving, setSaving] = useState(false);

  const rows = useMemo(() => (data || []).filter((s) => !q || s.nama_lengkap.toLowerCase().includes(q.toLowerCase()) || (s.nik || "").includes(q)), [data, q]);
  const counts = useMemo(() => (data || []).reduce((a, s) => ({ ...a, [s.status]: (a[s.status] || 0) + 1 }), {}), [data]);

  const save = async () => {
    setSaving(true);
    try {
      const { data: s } = await api.post("/students", normalizeStudent(form));
      toast.success("Calon siswa berhasil didaftarkan");
      setOpen(false); setForm(EMPTY_STUDENT); reload(); nav(`/siswa/${s.id}`);
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  return (
    <div>
      <PageHeader title="Data Siswa" jp="生徒データ" subtitle="Satu profil siswa untuk seleksi, kelas, pembayaran, dokumen, dan job order.">
        <button className="btn-outline" onClick={() => downloadCSV(rows.map((s) => ({ nama: s.nama_lengkap, nik: s.nik, status: STATUS_LABELS[s.status], kelas: s.kelas_nama, total: s.pembayaran.total, bayar: s.pembayaran.bayar, sisa: s.pembayaran.sisa, hp: s.no_hp })), "siswa.csv")} data-testid="export-students-btn"><Download size={16} />Ekspor</button>
        {can("siswa_write") && <button className="btn-red" onClick={() => setOpen(true)} data-testid="add-student-btn"><Plus size={16} />Daftarkan Calon Siswa</button>}
      </PageHeader>

      <div className="flex gap-1.5 overflow-x-auto pb-3 mb-4 -mx-1 px-1" data-testid="status-pipeline-filter">
        <button onClick={() => setParams({})} data-testid="filter-status-all" className={`chip cursor-pointer transition-colors ${!status ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 hover:bg-slate-50"}`}>Semua {data ? data.length : ""}</button>
        {STATUS_ORDER.map((st) => (
          <button key={st} onClick={() => setParams({ status: st })} data-testid={`filter-status-${st}`} className={`chip cursor-pointer transition-colors ${status === st ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600 hover:bg-slate-50"}`}>
            {STATUS_LABELS[st]} {!status && counts[st] ? <span className="ml-1 text-slate-400">{counts[st]}</span> : null}
          </button>
        ))}
      </div>

      <div className="mb-4"><input data-testid="students-search-input" className="input max-w-sm" placeholder="Cari nama / NIK..." value={q} onChange={(e) => setQ(e.target.value)} /></div>

      {loading && !data ? <Loading /> : rows.length === 0 ? <div className="card"><EmptyState text="Tidak ada siswa pada filter ini" testId="students-empty" /></div> : (
        <div className="table-wrap fade-up">
          <table className="tbl" data-testid="students-table">
            <thead><tr><th>Nama</th><th>Status</th><th>Kelas</th><th>Usia / JK</th><th>Bahasa</th><th>Pembayaran</th><th>Kontak</th></tr></thead>
            <tbody>
              {rows.map((s) => (
                <tr key={s.id} data-testid={`student-row-${s.id}`} className="cursor-pointer" onClick={() => nav(`/siswa/${s.id}`)}>
                  <td><Link to={`/siswa/${s.id}`} className="font-semibold text-slate-900 hover:text-red-600 transition-colors" onClick={(e) => e.stopPropagation()}>{s.nama_lengkap}</Link><p className="text-xs text-slate-400 mono">{s.nik || "-"}</p></td>
                  <td><StatusBadge status={s.status} /></td>
                  <td>{s.kelas_nama || <span className="text-slate-400">-</span>}</td>
                  <td>{s.usia ?? "-"} th · {s.jenis_kelamin}</td>
                  <td><span className="chip bg-slate-50 border-slate-200 text-slate-700">{s.kemampuan_bahasa_jepang || "-"}</span></td>
                  <td className="min-w-[180px]">
                    <div className="flex justify-between text-xs mb-1"><span className="mono">{rupiah(s.pembayaran.bayar)}</span><span className={`mono ${s.pembayaran.sisa > 0 ? "text-red-600" : "text-emerald-600"}`}>{s.pembayaran.sisa > 0 ? `sisa ${rupiah(s.pembayaran.sisa)}` : "Lunas"}</span></div>
                    <Progress value={s.pembayaran.total ? (s.pembayaran.bayar / s.pembayaran.total) * 100 : 0} tone={s.pembayaran.sisa > 0 ? "bg-amber-500" : "bg-emerald-500"} />
                  </td>
                  <td className="text-xs text-slate-500">{s.no_hp}<br />{s.alamat?.kabupaten}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title="Pendaftaran Calon Siswa" description="Data cukup diinput sekali, akan dipakai oleh semua modul." onSubmit={save} loading={saving} testId="student-form-dialog" wide>
        <StudentForm form={form} setForm={setForm} />
      </FormDialog>
    </div>
  );
}
