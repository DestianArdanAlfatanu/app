import { useEffect, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Loading, Field, EmptyState } from "@/components/common";
import { today, ATT_LABELS } from "@/lib/format";

const OPTS = [["hadir", "bg-emerald-600 text-white border-emerald-600", "bg-white text-emerald-700 border-emerald-200"], ["izin", "bg-amber-500 text-white border-amber-500", "bg-white text-amber-700 border-amber-200"],
  ["sakit", "bg-blue-600 text-white border-blue-600", "bg-white text-blue-700 border-blue-200"], ["alfa", "bg-red-600 text-white border-red-600", "bg-white text-red-700 border-red-200"]];

export default function AttendancePage() {
  const { data: classes } = useApi("/classes");
  const [classId, setClassId] = useState("");
  const [tanggal, setTanggal] = useState(today());
  const [cls, setCls] = useState(null);
  const [marks, setMarks] = useState({});
  const [recap, setRecap] = useState({});
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState(null);

  useEffect(() => { if (classes?.length && !classId) setClassId(classes[0].id); }, [classes, classId]);
  useEffect(() => {
    if (!classId) return;
    setLoadError(null);
    Promise.all([api.get(`/classes/${classId}`), api.get(`/attendance?class_id=${classId}&tanggal=${tanggal}`), api.get(`/attendance/recap?class_id=${classId}`)]).then(([c, a, r]) => {
      setCls(c.data); setRecap(r.data);
      const m = {}; c.data.students.forEach((s) => { m[s.id] = "hadir"; }); a.data.forEach((x) => { m[x.student_id] = x.status; }); setMarks(m);
    }).catch((e) => { setLoadError(errMsg(e)); toast.error(errMsg(e)); });
  }, [classId, tanggal]);

  const save = async () => {
    setSaving(true);
    try {
      await api.post("/attendance", { class_id: classId, tanggal, records: Object.entries(marks).map(([student_id, status]) => ({ student_id, status })) });
      toast.success("Absensi tersimpan, rekap kehadiran otomatis diperbarui");
      setRecap((await api.get(`/attendance/recap?class_id=${classId}`)).data);
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const counts = Object.values(marks).reduce((a, s) => ({ ...a, [s]: (a[s] || 0) + 1 }), {});

  return (
    <div>
      <PageHeader title="Absensi Siswa" jp="出席" subtitle="Ketuk status untuk setiap siswa, lalu simpan. Persentase kehadiran dihitung otomatis." />
      <div className="card p-4 mb-4 grid sm:grid-cols-[1fr_200px_auto] gap-3 items-end">
        <Field label="Kelas"><select className="input" data-testid="attendance-class-select" value={classId} onChange={(e) => setClassId(e.target.value)}>{(classes || []).map((c) => <option key={c.id} value={c.id}>{`${c.nama} · ${c.guru_nama || "-"}`}</option>)}</select></Field>
        <Field label="Tanggal"><input type="date" className="input" data-testid="attendance-date-input" value={tanggal} onChange={(e) => setTanggal(e.target.value)} /></Field>
        <button className="btn-red h-10" onClick={save} disabled={saving || !cls?.students?.length} data-testid="save-attendance-btn"><Save size={16} />{saving ? "Menyimpan..." : "Simpan Absensi"}</button>
      </div>
      <div className="flex gap-2 flex-wrap mb-4 text-xs" data-testid="attendance-summary">{OPTS.map(([k, on]) => <span key={k} className={`chip ${on}`}>{ATT_LABELS[k]}: {counts[k] || 0}</span>)}</div>
      {classes && classes.length === 0 ? <div className="card"><EmptyState text="Belum ada kelas. Buat kelas di menu Kelas & Jadwal." /></div>
        : loadError ? <div className="card"><EmptyState text={`Data kelas gagal dimuat: ${loadError}`} /></div>
        : !cls ? <Loading /> : cls.students.length === 0 ? <div className="card"><EmptyState text="Kelas ini belum memiliki siswa" /></div> : (
        <div className="space-y-2">
          {cls.students.map((s) => (
            <div key={s.id} className="card p-3 sm:p-4 flex flex-col sm:flex-row sm:items-center gap-3 fade-up" data-testid={`attendance-row-${s.id}`}>
              <div className="flex-1 min-w-0"><p className="font-semibold text-slate-900">{s.nama_lengkap}</p><p className="text-xs text-slate-500">Kehadiran: <b>{recap[s.id]?.persentase ?? 0}%</b> · {recap[s.id]?.hadir ?? 0} hadir · {recap[s.id]?.izin ?? 0} izin · {recap[s.id]?.sakit ?? 0} sakit · {recap[s.id]?.alfa ?? 0} alfa</p></div>
              <div className="grid grid-cols-4 gap-1.5 sm:w-[340px]">
                {OPTS.map(([k, on, off]) => <button key={k} onClick={() => setMarks({ ...marks, [s.id]: k })} data-testid={`att-${k}-${s.id}`} className={`h-11 rounded-md border text-sm font-semibold transition-colors ${marks[s.id] === k ? on : off}`}>{ATT_LABELS[k]}</button>)}
              </div>
            </div>
          ))}
          <div className="sm:hidden sticky bottom-3"><button className="btn-red w-full h-12 shadow-lg" onClick={save} disabled={saving} data-testid="save-attendance-btn-mobile"><Save size={16} />Simpan Absensi</button></div>
        </div>
      )}
    </div>
  );
}
