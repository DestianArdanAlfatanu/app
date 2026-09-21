import { useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Users, CheckCircle2, XCircle, CalendarPlus } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, FormDialog, Field, EmptyState, Loading, StatusBadge, Tabs } from "@/components/common";
import { fmtDate, today } from "@/lib/format";

const EMPTY = { perusahaan: "", posisi: "", lokasi: "", jumlah_kebutuhan: 1, gaji: "", jam_kerja: "", persyaratan: "", usia_min: 18, usia_max: 30, jenis_kelamin: "semua", min_jlpt: "N4", jenis_pekerjaan: "", tanggal_interview: "", status: "terbuka" };
const HASIL = { menunggu: "bg-amber-50 text-amber-700 border-amber-200", lulus: "bg-emerald-50 text-emerald-700 border-emerald-200", gagal: "bg-red-50 text-red-700 border-red-200" };

export default function JobOrdersPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState("lowongan");
  const { data: jobs, loading, reload } = useApi("/job-orders");
  const { data: interviews, reload: reloadIv } = useApi("/interviews");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [match, setMatch] = useState(null);
  const [ivForm, setIvForm] = useState(null);

  const save = async () => {
    const body = { ...form, jumlah_kebutuhan: Number(form.jumlah_kebutuhan), usia_min: Number(form.usia_min), usia_max: Number(form.usia_max), tanggal_interview: form.tanggal_interview || null };
    try { editId ? await api.put(`/job-orders/${editId}`, body) : await api.post("/job-orders", body); toast.success("Job order tersimpan"); setOpen(false); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const openMatch = async (j) => { try { setMatch((await api.get(`/job-orders/${j.id}/candidates`)).data); } catch (e) { toast.error(errMsg(e)); } };
  const schedule = async () => {
    try { await api.post("/interviews", ivForm); toast.success("Interview dijadwalkan, status siswa → Matching"); setIvForm(null); setMatch(null); reload(); reloadIv(); } catch (e) { toast.error(errMsg(e)); }
  };
  const setHasil = async (iv, hasil) => {
    try { await api.put(`/interviews/${iv.id}`, { job_order_id: iv.job_order_id, student_id: iv.student_id, tanggal: iv.tanggal, hasil, catatan: iv.catatan }); toast.success(hasil === "lulus" ? "Lulus! Status siswa → Pemberkasan" : "Hasil disimpan"); reloadIv(); reload(); } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div>
      <PageHeader title="Job Order Jepang" jp="求人管理" subtitle="Lowongan perusahaan Jepang, matching otomatis kandidat, dan hasil interview.">
        {can("joborder_write") && <button className="btn-red" onClick={() => { setForm(EMPTY); setEditId(null); setOpen(true); }} data-testid="add-job-btn"><Plus size={16} />Job Order Baru</button>}
      </PageHeader>
      <Tabs active={tab} onChange={setTab} testPrefix="job-tab" tabs={[{ key: "lowongan", label: "Lowongan", count: jobs?.length }, { key: "interview", label: "Interview", count: interviews?.length }]} />

      {tab === "lowongan" && (loading && !jobs ? <Loading /> : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {(jobs || []).length === 0 && <div className="card col-span-full"><EmptyState text="Belum ada job order" /></div>}
          {(jobs || []).map((j) => (
            <div key={j.id} className="card p-5 fade-up flex flex-col" data-testid={`job-card-${j.id}`}>
              <div className="flex justify-between items-start gap-2"><div><p className="text-xs font-semibold uppercase tracking-wider text-red-600">{j.jenis_pekerjaan || "Umum"} · {j.lokasi}</p><h3 className="font-bold text-lg tracking-tight">{j.posisi}</h3><p className="text-sm text-slate-600">{j.perusahaan}</p></div><span className={`chip ${j.status === "terbuka" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-600"}`}>{j.status}</span></div>
              <div className="grid grid-cols-2 gap-2 mt-4 text-xs text-slate-600">
                <p>Kebutuhan: <b>{j.jumlah_kebutuhan} orang</b></p><p>Gaji: <b>{j.gaji || "-"}</b></p><p>Usia: <b>{j.usia_min}–{j.usia_max}</b></p><p>Bahasa: <b>{j.min_jlpt}</b> · {j.jenis_kelamin === "semua" ? "L/P" : j.jenis_kelamin}</p><p>Jam kerja: <b>{j.jam_kerja || "-"}</b></p><p>Interview: <b>{fmtDate(j.tanggal_interview)}</b></p>
              </div>
              {j.persyaratan && <p className="text-xs text-slate-500 mt-3">{j.persyaratan}</p>}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100"><span className="text-xs text-slate-500">{j.jumlah_kandidat} kandidat · {j.jumlah_lulus} lulus</span>
                <div className="flex gap-1">{can("joborder_write") && <button className="btn-ghost btn-sm" onClick={() => { setForm({ ...EMPTY, ...j, tanggal_interview: j.tanggal_interview || "" }); setEditId(j.id); setOpen(true); }} data-testid={`edit-job-${j.id}`}>Edit</button>}<button className="btn-primary btn-sm" onClick={() => openMatch(j)} data-testid={`match-btn-${j.id}`}><Users size={13} />Matching</button></div></div>
            </div>))}
        </div>))}

      {tab === "interview" && (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="interviews-table"><thead><tr><th>Tanggal</th><th>Siswa</th><th>Perusahaan</th><th>Posisi</th><th>Hasil</th><th>Catatan</th><th></th></tr></thead>
          <tbody>{(interviews || []).length === 0 && <tr><td colSpan={7}><EmptyState /></td></tr>}
            {(interviews || []).map((iv) => <tr key={iv.id} data-testid={`interview-row-${iv.id}`}><td>{fmtDate(iv.tanggal)}</td><td><Link to={`/siswa/${iv.student_id}`} className="font-medium hover:text-red-600">{iv.student_nama}</Link></td><td>{iv.perusahaan}</td><td>{iv.posisi}</td><td><span className={`chip ${HASIL[iv.hasil]}`}>{iv.hasil}</span></td><td className="text-xs">{iv.catatan || "-"}</td>
              <td className="whitespace-nowrap">{can("joborder_write") && iv.hasil === "menunggu" && <><button className="btn-ghost btn-sm text-emerald-700" onClick={() => setHasil(iv, "lulus")} data-testid={`iv-lulus-${iv.id}`}><CheckCircle2 size={14} />Lulus</button><button className="btn-ghost btn-sm text-red-600" onClick={() => setHasil(iv, "gagal")} data-testid={`iv-gagal-${iv.id}`}><XCircle size={14} />Gagal</button></>}</td></tr>)}
          </tbody></table></div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Edit Job Order" : "Job Order Baru"} onSubmit={save} testId="job-dialog" wide>
        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Perusahaan" className="sm:col-span-2"><input className="input" data-testid="job-perusahaan-input" value={form.perusahaan} onChange={(e) => setForm({ ...form, perusahaan: e.target.value })} required /></Field>
          <Field label="Posisi"><input className="input" data-testid="job-posisi-input" value={form.posisi} onChange={(e) => setForm({ ...form, posisi: e.target.value })} required /></Field>
          <Field label="Lokasi"><input className="input" value={form.lokasi} onChange={(e) => setForm({ ...form, lokasi: e.target.value })} /></Field>
          <Field label="Jenis Pekerjaan"><input className="input" value={form.jenis_pekerjaan} onChange={(e) => setForm({ ...form, jenis_pekerjaan: e.target.value })} placeholder="Manufaktur / Kaigo / Konstruksi" /></Field>
          <Field label="Jumlah Kebutuhan"><input type="number" className="input" value={form.jumlah_kebutuhan} onChange={(e) => setForm({ ...form, jumlah_kebutuhan: e.target.value })} /></Field>
          <Field label="Gaji"><input className="input" value={form.gaji} onChange={(e) => setForm({ ...form, gaji: e.target.value })} placeholder="¥180.000/bulan" /></Field>
          <Field label="Jam Kerja"><input className="input" value={form.jam_kerja} onChange={(e) => setForm({ ...form, jam_kerja: e.target.value })} /></Field>
          <Field label="Tanggal Interview"><input type="date" className="input" value={form.tanggal_interview} onChange={(e) => setForm({ ...form, tanggal_interview: e.target.value })} /></Field>
          <Field label="Usia Min"><input type="number" className="input" data-testid="job-usia-min" value={form.usia_min} onChange={(e) => setForm({ ...form, usia_min: e.target.value })} /></Field>
          <Field label="Usia Maks"><input type="number" className="input" data-testid="job-usia-max" value={form.usia_max} onChange={(e) => setForm({ ...form, usia_max: e.target.value })} /></Field>
          <Field label="Jenis Kelamin"><select className="input" value={form.jenis_kelamin} onChange={(e) => setForm({ ...form, jenis_kelamin: e.target.value })}><option value="semua">Semua</option><option value="L">Laki-laki</option><option value="P">Perempuan</option></select></Field>
          <Field label="Min. Bahasa Jepang"><select className="input" data-testid="job-jlpt-select" value={form.min_jlpt} onChange={(e) => setForm({ ...form, min_jlpt: e.target.value })}>{["-", "N5", "N4", "N3", "N2"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Status"><select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="terbuka">Terbuka</option><option value="selesai">Selesai</option><option value="batal">Batal</option></select></Field>
          <Field label="Persyaratan" className="sm:col-span-3"><textarea className="input" value={form.persyaratan} onChange={(e) => setForm({ ...form, persyaratan: e.target.value })} /></Field>
        </div>
      </FormDialog>

      <FormDialog open={!!match} onOpenChange={() => setMatch(null)} title={`Kandidat: ${match?.job?.posisi} — ${match?.job?.perusahaan}`} description={`Syarat: usia ${match?.job?.usia_min}–${match?.job?.usia_max} · ${match?.job?.jenis_kelamin === "semua" ? "L/P" : match?.job?.jenis_kelamin} · min ${match?.job?.min_jlpt}. Kandidat diurutkan dari yang paling memenuhi.`} footer={null} testId="matching-dialog" wide>
        <div className="table-wrap max-h-[60vh] overflow-y-auto"><table className="tbl" data-testid="candidates-table"><thead><tr><th>Siswa</th><th>Status</th><th>Usia</th><th>JK</th><th>Bahasa</th><th>Nilai</th><th>Memenuhi</th><th></th></tr></thead>
          <tbody>{match?.candidates?.length === 0 && <tr><td colSpan={8}><EmptyState text="Belum ada siswa pada tahap pelatihan/lulus" /></td></tr>}
            {match?.candidates?.map((c) => <tr key={c.id} data-testid={`candidate-row-${c.id}`} className={c.memenuhi ? "" : "opacity-60"}><td><Link to={`/siswa/${c.id}`} className="font-medium hover:text-red-600">{c.nama_lengkap}</Link></td><td><StatusBadge status={c.status} /></td>
              <td className={c.checks.usia ? "text-emerald-700" : "text-red-600"}>{c.usia ?? "-"}</td><td className={c.checks.jenis_kelamin ? "text-emerald-700" : "text-red-600"}>{c.jenis_kelamin}</td><td className={c.checks.bahasa ? "text-emerald-700" : "text-red-600"}>{c.kemampuan_bahasa_jepang}</td><td className="mono">{c.nilai_rata ?? "-"}</td>
              <td>{c.memenuhi ? <span className="chip bg-emerald-50 text-emerald-700 border-emerald-200">✓ {c.skor}/3</span> : <span className="chip bg-red-50 text-red-700 border-red-200">{c.skor}/3</span>}</td>
              <td>{c.sudah_interview ? <span className="text-xs text-slate-400">Sudah dijadwalkan</span> : can("joborder_write") && <button type="button" className="btn-outline btn-sm" onClick={() => setIvForm({ job_order_id: match.job.id, student_id: c.id, tanggal: match.job.tanggal_interview || today(), hasil: "menunggu", catatan: "", nama: c.nama_lengkap })} data-testid={`schedule-iv-${c.id}`}><CalendarPlus size={13} />Interview</button>}</td></tr>)}
          </tbody></table></div>
      </FormDialog>

      <FormDialog open={!!ivForm} onOpenChange={() => setIvForm(null)} title={`Jadwalkan Interview — ${ivForm?.nama}`} onSubmit={schedule} testId="interview-dialog" submitLabel="Jadwalkan">
        <Field label="Tanggal Interview"><input type="date" className="input" data-testid="iv-tanggal-input" value={ivForm?.tanggal || ""} onChange={(e) => setIvForm({ ...ivForm, tanggal: e.target.value })} required /></Field>
        <Field label="Catatan"><textarea className="input" value={ivForm?.catatan || ""} onChange={(e) => setIvForm({ ...ivForm, catatan: e.target.value })} /></Field>
      </FormDialog>
    </div>
  );
}
