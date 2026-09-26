import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, ClipboardList } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Tabs, FormDialog, Field, EmptyState, Loading } from "@/components/common";
import { fmtDate, today } from "@/lib/format";

const KOMP = ["hiragana", "katakana", "kanji", "grammar", "listening", "speaking", "reading", "writing", "budaya", "kedisiplinan"];
const EXAM_TYPES = ["Ujian bulanan", "Ujian tengah pelatihan", "Ujian akhir", "Try Out JLPT", "Tes bahasa", "Tes keterampilan"];

export default function GradesPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState("nilai");
  const { data: classes } = useApi("/classes");
  const [classId, setClassId] = useState("");
  const { data: grades, reload } = useApi(classId ? `/grades?class_id=${classId}` : null, [classId], !!classId);
  const { data: exams, reload: reloadExams } = useApi("/exams");
  const [cls, setCls] = useState(null);
  const [gOpen, setGOpen] = useState(false);
  const [g, setG] = useState({ student_id: "", periode: "Bulan 1", komponen: Object.fromEntries(KOMP.map((k) => [k, ""])), catatan: "" });
  const [eOpen, setEOpen] = useState(false);
  const [ex, setEx] = useState({ nama: "", jenis: EXAM_TYPES[0], tanggal: today(), class_id: "", passing_grade: 70, keterangan: "" });
  const [resExam, setResExam] = useState(null);
  const [results, setResults] = useState({});

  useEffect(() => { if (classes?.length && !classId) setClassId(classes[0].id); }, [classes, classId]);
  const [loadError, setLoadError] = useState(null);
  useEffect(() => {
    if (!classId) return;
    setLoadError(null);
    api.get(`/classes/${classId}`).then((r) => setCls(r.data)).catch((e) => { setLoadError(errMsg(e)); toast.error(errMsg(e)); });
  }, [classId]);

  const avg = Object.values(g.komponen).filter((v) => v !== "").map(Number);
  const nilaiAkhir = avg.length ? (avg.reduce((a, b) => a + b, 0) / avg.length).toFixed(1) : "-";
  const saveGrade = async () => {
    const komponen = Object.fromEntries(Object.entries(g.komponen).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)]));
    try { await api.post("/grades", { ...g, class_id: classId, komponen }); toast.success(`Nilai tersimpan, nilai akhir ${nilaiAkhir}`); setGOpen(false); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const saveExam = async () => {
    try { await api.post("/exams", { ...ex, class_id: ex.class_id || null, passing_grade: Number(ex.passing_grade) }); toast.success("Ujian dibuat"); setEOpen(false); reloadExams(); } catch (e) { toast.error(errMsg(e)); }
  };
  const openResults = async (e) => {
    const c = e.class_id ? (await api.get(`/classes/${e.class_id}`)).data : null;
    const r = {}; e.results.forEach((x) => { r[x.student_id] = x.nilai; });
    setResults(r); setResExam({ ...e, students: c?.students || [] });
  };
  const saveResults = async () => {
    try { await api.put(`/exams/${resExam.id}/results`, { results: Object.entries(results).map(([student_id, nilai]) => ({ student_id, nilai })) }); toast.success("Hasil ujian tersimpan"); setResExam(null); reloadExams(); } catch (e) { toast.error(errMsg(e)); }
  };
  const byStudent = (grades || []).reduce((a, r) => ({ ...a, [r.student_id]: [...(a[r.student_id] || []), r] }), {});

  return (
    <div>
      <PageHeader title="Nilai & Ujian" jp="成績・試験" subtitle="Nilai akhir dihitung otomatis dari rata-rata komponen. Semua terhubung ke profil siswa.">
        {can("nilai") && (tab === "nilai" ? <button className="btn-red" onClick={() => setGOpen(true)} data-testid="add-grade-btn"><Plus size={16} />Input Nilai</button> : <button className="btn-red" onClick={() => setEOpen(true)} data-testid="add-exam-btn"><Plus size={16} />Buat Ujian</button>)}
      </PageHeader>
      <Tabs active={tab} onChange={setTab} testPrefix="grades-tab" tabs={[{ key: "nilai", label: "Nilai Kelas" }, { key: "ujian", label: "Ujian", count: exams?.length }]} />

      {tab === "nilai" && (<>
        <div className="mb-4 max-w-sm"><label className="label">Kelas</label><select className="input" data-testid="grades-class-select" value={classId} onChange={(e) => setClassId(e.target.value)}>{(classes || []).map((c) => <option key={c.id} value={c.id}>{c.nama}</option>)}</select></div>
        {classes && classes.length === 0 ? <div className="card"><EmptyState text="Belum ada kelas. Buat kelas di menu Kelas & Jadwal." /></div>
          : loadError ? <div className="card"><EmptyState text={`Data kelas gagal dimuat: ${loadError}`} /></div>
          : !cls ? <Loading /> : (
          <div className="table-wrap fade-up"><table className="tbl" data-testid="grades-table"><thead><tr><th>Siswa</th><th>Periode</th>{KOMP.map((k) => <th key={k} className="capitalize">{k.slice(0, 5)}</th>)}<th>Akhir</th></tr></thead>
            <tbody>{cls.students.length === 0 && <tr><td colSpan={13}><EmptyState text="Kelas belum memiliki siswa" /></td></tr>}
              {cls.students.map((s) => { const list = byStudent[s.id] || []; return list.length === 0 ? <tr key={s.id}><td><Link to={`/siswa/${s.id}`} className="font-medium hover:text-red-600">{s.nama_lengkap}</Link></td><td colSpan={12} className="text-slate-400 text-xs">Belum ada nilai</td></tr>
                : list.map((r, i) => <tr key={r.id}><td>{i === 0 && <Link to={`/siswa/${s.id}`} className="font-medium hover:text-red-600">{s.nama_lengkap}</Link>}</td><td>{r.periode}</td>{KOMP.map((k) => <td key={k} className="mono text-xs">{r.komponen[k] ?? "-"}</td>)}<td className={`mono font-bold ${r.nilai_akhir >= 75 ? "text-emerald-600" : "text-amber-600"}`}>{r.nilai_akhir}</td></tr>); })}
            </tbody></table></div>)}
      </>)}

      {tab === "ujian" && (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
          {(exams || []).map((e) => (
            <div key={e.id} className="card p-5 fade-up" data-testid={`exam-card-${e.id}`}>
              <p className="text-xs font-semibold uppercase tracking-wider text-red-600">{e.jenis}</p><h3 className="font-bold tracking-tight">{e.nama}</h3>
              <p className="text-sm text-slate-500">{fmtDate(e.tanggal)} · {(classes || []).find((c) => c.id === e.class_id)?.nama || "Semua kelas"} · KKM {e.passing_grade}</p>
              <div className="grid grid-cols-3 gap-2 mt-4 text-center">
                <div className="bg-slate-50 rounded p-2"><p className="mono font-bold">{e.jumlah_peserta}</p><p className="text-[10px] uppercase text-slate-500">Peserta</p></div>
                <div className="bg-slate-50 rounded p-2"><p className="mono font-bold">{e.rata_rata ?? "-"}</p><p className="text-[10px] uppercase text-slate-500">Rata-rata</p></div>
                <div className="bg-slate-50 rounded p-2"><p className="mono font-bold text-emerald-600">{e.jumlah_lulus}</p><p className="text-[10px] uppercase text-slate-500">Lulus</p></div>
              </div>
              {can("nilai") && <button className="btn-outline w-full mt-4" onClick={() => openResults(e)} data-testid={`exam-results-btn-${e.id}`}><ClipboardList size={15} />Input / Lihat Hasil</button>}
            </div>))}
        </div>
      )}

      <FormDialog open={gOpen} onOpenChange={setGOpen} title="Input Nilai Siswa" description={`Nilai akhir otomatis: ${nilaiAkhir}`} onSubmit={saveGrade} testId="grade-dialog">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Siswa"><select className="input" data-testid="grade-student-select" value={g.student_id} onChange={(e) => setG({ ...g, student_id: e.target.value })} required><option value="">Pilih...</option>{(cls?.students || []).map((s) => <option key={s.id} value={s.id}>{s.nama_lengkap}</option>)}</select></Field>
          <Field label="Periode"><input className="input" data-testid="grade-periode-input" value={g.periode} onChange={(e) => setG({ ...g, periode: e.target.value })} /></Field>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">{KOMP.map((k) => <Field key={k} label={k}><input type="number" min="0" max="100" className="input mono" data-testid={`grade-${k}-input`} value={g.komponen[k]} onChange={(e) => setG({ ...g, komponen: { ...g.komponen, [k]: e.target.value } })} /></Field>)}</div>
        <Field label="Catatan"><input className="input" value={g.catatan} onChange={(e) => setG({ ...g, catatan: e.target.value })} /></Field>
      </FormDialog>

      <FormDialog open={eOpen} onOpenChange={setEOpen} title="Buat Ujian" onSubmit={saveExam} testId="exam-dialog">
        <Field label="Nama Ujian"><input className="input" data-testid="exam-nama-input" value={ex.nama} onChange={(e) => setEx({ ...ex, nama: e.target.value })} required /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Jenis"><select className="input" value={ex.jenis} onChange={(e) => setEx({ ...ex, jenis: e.target.value })}>{EXAM_TYPES.map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Tanggal"><input type="date" className="input" value={ex.tanggal} onChange={(e) => setEx({ ...ex, tanggal: e.target.value })} /></Field>
          <Field label="Kelas"><select className="input" data-testid="exam-class-select" value={ex.class_id} onChange={(e) => setEx({ ...ex, class_id: e.target.value })}><option value="">Pilih kelas...</option>{(classes || []).map((c) => <option key={c.id} value={c.id}>{c.nama}</option>)}</select></Field>
          <Field label="Nilai Minimum (KKM)"><input type="number" className="input" value={ex.passing_grade} onChange={(e) => setEx({ ...ex, passing_grade: e.target.value })} /></Field>
        </div>
      </FormDialog>

      <FormDialog open={!!resExam} onOpenChange={() => setResExam(null)} title={`Hasil ${resExam?.nama}`} onSubmit={saveResults} testId="exam-results-dialog">
        <div className="max-h-96 overflow-y-auto divide-y divide-slate-100 border border-slate-200 rounded-md">
          {resExam?.students?.length === 0 && <p className="p-4 text-sm text-slate-500">Ujian tidak terhubung ke kelas.</p>}
          {resExam?.students?.map((s) => <div key={s.id} className="flex items-center gap-3 px-3 py-2"><span className="flex-1 text-sm font-medium">{s.nama_lengkap}</span><input type="number" min="0" max="100" className="input w-24 mono" data-testid={`exam-result-${s.id}`} value={results[s.id] ?? ""} onChange={(e) => setResults({ ...results, [s.id]: e.target.value })} /></div>)}
        </div>
      </FormDialog>
    </div>
  );
}
