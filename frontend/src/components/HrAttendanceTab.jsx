import { useEffect, useMemo, useState } from "react";
import { Save } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { Field, EmptyState, Loading } from "@/components/common";
import { today } from "@/lib/format";

// Status UI tahap 1 — "cuti" disiapkan di backend untuk fase Leave,
// tetapi sengaja tidak ditampilkan di sini.
const OPTS = [
  ["hadir", "bg-emerald-600 text-white border-emerald-600", "bg-white text-emerald-700 border-emerald-200", "Hadir"],
  ["terlambat", "bg-orange-500 text-white border-orange-500", "bg-white text-orange-700 border-orange-200", "Terlambat"],
  ["izin", "bg-amber-500 text-white border-amber-500", "bg-white text-amber-700 border-amber-200", "Izin"],
  ["sakit", "bg-blue-600 text-white border-blue-600", "bg-white text-blue-700 border-blue-200", "Sakit"],
  ["alfa", "bg-red-600 text-white border-red-600", "bg-white text-red-700 border-red-200", "Alfa"],
];

const monthStart = () => today().slice(0, 7) + "-01";

export default function HrAttendanceTab({ employees, loadingEmployees }) {
  const { can } = useAuth();
  const writable = can("hr_attendance_write");
  const [tanggal, setTanggal] = useState(today());
  const [marks, setMarks] = useState({});
  const [showInactive, setShowInactive] = useState(false);
  const [range, setRange] = useState({ dari: monthStart(), sampai: today() });
  const [saving, setSaving] = useState(false);

  const list = useMemo(
    () => (employees || []).filter((e) => showInactive || e.aktif !== false),
    [employees, showInactive]
  );

  // Muat absensi tanggal terpilih, default semua "hadir".
  useEffect(() => {
    if (!list.length) return;
    api.get(`/hr/attendance?dari=${tanggal}&sampai=${tanggal}`)
      .then((r) => {
        const m = {};
        list.forEach((e) => { m[e.id] = { status: "hadir", jam_masuk: "", jam_pulang: "", keterangan: "" }; });
        r.data.forEach((x) => {
          if (m[x.employee_id]) {
            m[x.employee_id] = {
              status: x.status, jam_masuk: x.jam_masuk || "",
              jam_pulang: x.jam_pulang || "", keterangan: x.keterangan || "",
            };
          }
        });
        setMarks(m);
      })
      .catch((e) => toast.error(errMsg(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tanggal, employees, showInactive]);

  const recapPath = `/hr/attendance/recap?dari=${range.dari}&sampai=${range.sampai}`;
  const { data: recapData, loading: loadingRecap, reload: reloadRecap } = useApi(recapPath, [range.dari, range.sampai]);
  const recapRows = useMemo(() => recapData || [], [recapData]);

  const setMark = (id, patch) => setMarks((m) => ({ ...m, [id]: { ...m[id], ...patch } }));

  const save = async () => {
    setSaving(true);
    try {
      await api.post("/hr/attendance", {
        tanggal,
        records: list.map((e) => ({
          employee_id: e.id,
          status: marks[e.id]?.status || "hadir",
          jam_masuk: marks[e.id]?.jam_masuk || null,
          jam_pulang: marks[e.id]?.jam_pulang || null,
          keterangan: marks[e.id]?.keterangan || "",
        })),
      });
      toast.success("Absensi berhasil disimpan.");
      reloadRecap();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  const counts = Object.values(marks).reduce((a, r) => ({ ...a, [r.status]: (a[r.status] || 0) + 1 }), {});
  const recapById = useMemo(() => Object.fromEntries(recapRows.map((r) => [r.employee_id, r])), [recapRows]);

  return (
    <div>
      <div className="card p-4 mb-4 grid sm:grid-cols-[200px_1fr_auto] gap-3 items-end">
        <Field label="Tanggal"><input type="date" className="input" data-testid="hr-att-date-input" value={tanggal} max={today()} onChange={(e) => setTanggal(e.target.value)} disabled={!writable} /></Field>
        <label className="flex items-center gap-2 text-sm text-slate-600">
          <input type="checkbox" checked={showInactive} onChange={(e) => setShowInactive(e.target.checked)} data-testid="hr-att-show-inactive" />
          Tampilkan nonaktif
        </label>
        {writable && <button className="btn-red h-10" onClick={save} disabled={saving || !list.length} data-testid="hr-att-save-btn"><Save size={16} />{saving ? "Menyimpan..." : "Simpan Absensi"}</button>}
      </div>
      <div className="flex gap-2 flex-wrap mb-4 text-xs" data-testid="hr-attendance-summary">
        {OPTS.map(([k, on, , label]) => <span key={k} className={`chip ${on}`}>{label}: {counts[k] || 0}</span>)}
      </div>
      {loadingEmployees ? <Loading /> : list.length === 0 ? <div className="card"><EmptyState text="Belum ada data karyawan/guru aktif" /></div> : (
        <div className="space-y-2 mb-8">
          {list.map((e) => (
            <div key={e.id} className="card p-3 sm:p-4 flex flex-col gap-3 fade-up" data-testid={`hr-att-row-${e.id}`}>
              <div className="flex flex-col sm:flex-row sm:items-center gap-3">
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-slate-900">{e.nama}</p>
                  <p className="text-xs text-slate-500">{e.jabatan || e.tipe}{recapById[e.id] != null && <> · Kehadiran: <b>{recapById[e.id].persentase}%</b></>}</p>
                </div>
                <div className="grid grid-cols-5 gap-1.5 sm:w-[420px]">
                  {OPTS.map(([k, on, off, label]) => (
                    <button key={k} onClick={() => writable && setMark(e.id, { status: k })} disabled={!writable}
                      data-testid={`hr-att-${k}-${e.id}`}
                      className={`h-11 rounded-md border text-xs font-semibold transition-colors ${marks[e.id]?.status === k ? on : off}`}>
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-[140px_140px_1fr] gap-2">
                <input type="time" className="input mono" aria-label="Jam masuk" data-testid={`hr-att-in-${e.id}`}
                  value={marks[e.id]?.jam_masuk || ""} onChange={(ev) => setMark(e.id, { jam_masuk: ev.target.value })} disabled={!writable} />
                <input type="time" className="input mono" aria-label="Jam pulang" data-testid={`hr-att-out-${e.id}`}
                  value={marks[e.id]?.jam_pulang || ""} onChange={(ev) => setMark(e.id, { jam_pulang: ev.target.value })} disabled={!writable} />
                <input className="input col-span-2 sm:col-span-1" placeholder="Keterangan (opsional)" data-testid={`hr-att-note-${e.id}`}
                  value={marks[e.id]?.keterangan || ""} onChange={(ev) => setMark(e.id, { keterangan: ev.target.value })} disabled={!writable} />
              </div>
            </div>
          ))}
          {writable && <div className="sm:hidden sticky bottom-3"><button className="btn-red w-full h-12 shadow-lg" onClick={save} disabled={saving} data-testid="hr-att-save-btn-mobile"><Save size={16} />Simpan Absensi</button></div>}
        </div>
      )}

      <h3 className="font-bold text-slate-900 mb-3">Rekap Kehadiran</h3>
      <div className="flex gap-2 mb-4 flex-wrap">
        <input type="date" className="input w-44" data-testid="hr-att-dari-input" value={range.dari} onChange={(ev) => setRange({ ...range, dari: ev.target.value })} />
        <input type="date" className="input w-44" data-testid="hr-att-sampai-input" value={range.sampai} onChange={(ev) => setRange({ ...range, sampai: ev.target.value })} />
      </div>
      {loadingRecap && !recapRows.length ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="hr-att-recap-table">
          <thead><tr><th>Nama</th><th>Total</th><th>Hadir</th><th>Terlambat</th><th>Izin</th><th>Sakit</th><th>Alfa</th><th>%</th></tr></thead>
          <tbody>
            {recapRows.length === 0 && <tr><td colSpan={8}><EmptyState text="Belum ada data pada periode ini" /></td></tr>}
            {recapRows.map((r) => (
              <tr key={r.employee_id}>
                <td className="font-medium">{r.nama}</td><td>{r.total}</td><td>{r.hadir}</td>
                <td>{r.terlambat}</td><td>{r.izin}</td><td>{r.sakit}</td><td>{r.alfa}</td>
                <td className={r.persentase >= 80 ? "text-emerald-700 font-semibold" : "text-red-600 font-semibold"}>{r.persentase}%</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}
    </div>
  );
}
