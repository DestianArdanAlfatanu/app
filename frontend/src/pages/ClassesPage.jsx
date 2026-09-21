import { useState } from "react";
import { Plus, Users, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Loading, FormDialog, Field, EmptyState, StatusBadge } from "@/components/common";

const HARI = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const EMPTY = { nama: "", guru_id: "", level: "N5", ruangan: "", materi: "", status: "aktif", jadwal: [{ hari: "Senin", jam_mulai: "08:00", jam_selesai: "10:00" }], tanggal_mulai: "", tanggal_selesai: "" };

export default function ClassesPage() {
  const { can } = useAuth();
  const { data: classes, loading, reload } = useApi("/classes");
  const { data: teachers } = useApi("/employees?tipe=guru");
  const { data: students } = useApi("/students", [], can("kelas_write"));
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [enroll, setEnroll] = useState(null);
  const [picked, setPicked] = useState([]);
  const [detail, setDetail] = useState(null);

  const save = async () => {
    const body = { ...form, guru_id: form.guru_id || null, tanggal_mulai: form.tanggal_mulai || null, tanggal_selesai: form.tanggal_selesai || null };
    try { editId ? await api.put(`/classes/${editId}`, body) : await api.post("/classes", body); toast.success("Kelas tersimpan"); setOpen(false); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const doEnroll = async () => {
    try { await api.post(`/classes/${enroll.id}/students`, { student_ids: picked }); toast.success(`${picked.length} siswa dimasukkan ke ${enroll.nama}`); setEnroll(null); setPicked([]); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const openDetail = async (c) => { try { setDetail((await api.get(`/classes/${c.id}`)).data); } catch (e) { toast.error(errMsg(e)); } };
  const remove = async (c) => { if (!window.confirm(`Hapus kelas ${c.nama}?`)) return; try { await api.delete(`/classes/${c.id}`); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const unenroll = async (sid) => { try { await api.delete(`/classes/${detail.id}/students/${sid}`); openDetail(detail); reload(); } catch (e) { toast.error(errMsg(e)); } };
  const eligible = (students || []).filter((s) => !enroll?.student_ids?.includes(s.id) && ["diterima", "pelatihan", "ujian"].includes(s.status));

  return (
    <div>
      <PageHeader title="Kelas & Jadwal" jp="クラス・時間割" subtitle="Kelas, pengajar, jadwal, ruangan, dan siswa dalam satu tempat.">
        {can("kelas_write") && <button className="btn-red" onClick={() => { setForm(EMPTY); setEditId(null); setOpen(true); }} data-testid="add-class-btn"><Plus size={16} />Buat Kelas</button>}
      </PageHeader>
      {loading && !classes ? <Loading /> : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {(classes || []).length === 0 && <div className="card col-span-full"><EmptyState text="Belum ada kelas" /></div>}
          {(classes || []).map((c) => (
            <div key={c.id} className="card p-5 fade-up flex flex-col" data-testid={`class-card-${c.id}`}>
              <div className="flex items-start justify-between gap-2">
                <div><p className="text-xs font-semibold uppercase tracking-wider text-red-600">{c.level}</p><h3 className="font-bold text-lg tracking-tight">{c.nama}</h3><p className="text-sm text-slate-500">Sensei: <b className="text-slate-700">{c.guru_nama || "-"}</b> · {c.ruangan || "-"}</p></div>
                <span className={`chip ${c.status === "aktif" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100 text-slate-600"}`}>{c.status}</span>
              </div>
              <div className="mt-4 space-y-1">{c.jadwal.map((j, i) => <div key={i} className="flex justify-between text-sm border-b border-slate-50 py-1"><span className="text-slate-600">{j.hari}</span><span className="mono text-slate-800">{j.jam_mulai}–{j.jam_selesai}</span></div>)}</div>
              {c.materi && <p className="text-xs text-slate-500 mt-3">Materi: {c.materi}</p>}
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-slate-100">
                <button className="btn-ghost btn-sm -ml-2" onClick={() => openDetail(c)} data-testid={`class-students-btn-${c.id}`}><Users size={14} />{c.jumlah_siswa} siswa</button>
                {can("kelas_write") && <div className="flex gap-1">
                  <button className="btn-outline btn-sm" onClick={() => { setEnroll(c); setPicked([]); }} data-testid={`enroll-btn-${c.id}`}><Plus size={13} />Siswa</button>
                  <button className="btn-ghost btn-sm" onClick={() => { setForm({ ...EMPTY, ...c, guru_id: c.guru_id || "" }); setEditId(c.id); setOpen(true); }} data-testid={`edit-class-${c.id}`}><Pencil size={13} /></button>
                  <button className="btn-ghost btn-sm text-red-600" onClick={() => remove(c)}><Trash2 size={13} /></button></div>}
              </div>
            </div>
          ))}
        </div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Edit Kelas" : "Buat Kelas Baru"} onSubmit={save} testId="class-dialog">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Nama Kelas" className="col-span-2"><input className="input" data-testid="class-nama-input" value={form.nama} onChange={(e) => setForm({ ...form, nama: e.target.value })} required /></Field>
          <Field label="Guru"><select className="input" data-testid="class-guru-select" value={form.guru_id} onChange={(e) => setForm({ ...form, guru_id: e.target.value })}><option value="">Pilih guru...</option>{(teachers || []).map((t) => <option key={t.id} value={t.id}>{t.nama}</option>)}</select></Field>
          <Field label="Level"><select className="input" value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>{["Dasar", "N5", "N4", "N3", "Budaya", "Keterampilan"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Ruangan"><input className="input" value={form.ruangan} onChange={(e) => setForm({ ...form, ruangan: e.target.value })} /></Field>
          <Field label="Status"><select className="input" value={form.status} onChange={(e) => setForm({ ...form, status: e.target.value })}><option value="aktif">Aktif</option><option value="selesai">Selesai</option></select></Field>
          <Field label="Materi" className="col-span-2"><input className="input" value={form.materi} onChange={(e) => setForm({ ...form, materi: e.target.value })} /></Field>
        </div>
        <div><label className="label">Jadwal</label>
          {form.jadwal.map((j, i) => (
            <div key={i} className="grid grid-cols-[1fr_1fr_1fr_32px] gap-2 mb-2">
              <select className="input" value={j.hari} onChange={(e) => setForm({ ...form, jadwal: form.jadwal.map((x, k) => k === i ? { ...x, hari: e.target.value } : x) })}>{HARI.map((h) => <option key={h}>{h}</option>)}</select>
              <input type="time" className="input" value={j.jam_mulai} onChange={(e) => setForm({ ...form, jadwal: form.jadwal.map((x, k) => k === i ? { ...x, jam_mulai: e.target.value } : x) })} />
              <input type="time" className="input" value={j.jam_selesai} onChange={(e) => setForm({ ...form, jadwal: form.jadwal.map((x, k) => k === i ? { ...x, jam_selesai: e.target.value } : x) })} />
              <button type="button" className="btn-ghost h-10 px-0 text-red-600" onClick={() => setForm({ ...form, jadwal: form.jadwal.filter((_, k) => k !== i) })}>×</button>
            </div>))}
          <button type="button" className="btn-outline btn-sm" onClick={() => setForm({ ...form, jadwal: [...form.jadwal, { hari: "Senin", jam_mulai: "08:00", jam_selesai: "10:00" }] })} data-testid="add-jadwal-btn">+ Tambah sesi</button>
        </div>
      </FormDialog>

      <FormDialog open={!!enroll} onOpenChange={() => setEnroll(null)} title={`Masukkan Siswa ke ${enroll?.nama}`} description="Hanya siswa berstatus Diterima / Pelatihan / Ujian yang ditampilkan. Data siswa tidak perlu diinput ulang." onSubmit={doEnroll} submitLabel={`Masukkan ${picked.length} siswa`} testId="enroll-dialog">
        <div className="max-h-80 overflow-y-auto border border-slate-200 rounded-md divide-y divide-slate-100">
          {eligible.length === 0 && <p className="p-4 text-sm text-slate-500">Tidak ada siswa yang bisa dimasukkan.</p>}
          {eligible.map((s) => (
            <label key={s.id} className="flex items-center gap-3 px-3 py-2.5 text-sm cursor-pointer hover:bg-slate-50" data-testid={`enroll-option-${s.id}`}>
              <input type="checkbox" checked={picked.includes(s.id)} onChange={(e) => setPicked(e.target.checked ? [...picked, s.id] : picked.filter((x) => x !== s.id))} />
              <span className="flex-1 font-medium">{s.nama_lengkap}</span><StatusBadge status={s.status} />{s.kelas_nama && <span className="text-xs text-slate-400">{s.kelas_nama}</span>}
            </label>))}
        </div>
      </FormDialog>

      <FormDialog open={!!detail} onOpenChange={() => setDetail(null)} title={`Siswa Kelas ${detail?.nama}`} footer={null} testId="class-detail-dialog">
        <div className="divide-y divide-slate-100 border border-slate-200 rounded-md">
          {detail?.students?.length === 0 && <p className="p-4 text-sm text-slate-500">Belum ada siswa.</p>}
          {detail?.students?.map((s) => <div key={s.id} className="flex items-center gap-3 px-3 py-2.5 text-sm"><span className="flex-1 font-medium">{s.nama_lengkap}</span><StatusBadge status={s.status} />{can("kelas_write") && <button type="button" className="btn-ghost btn-sm text-red-600" onClick={() => unenroll(s.id)}><Trash2 size={13} /></button>}</div>)}
        </div>
      </FormDialog>
    </div>
  );
}
