import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Plus } from "lucide-react";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, Loading, EmptyState } from "@/components/common";
import { ChecklistDialog, ProfileDialog, DecisionDialog, READINESS_LABELS, READINESS_TONE } from "@/components/DepartureDialogs";
import { fmtDate } from "@/lib/format";

const FILTERS = [["all", "Semua"], ["blocked", "Blocked"], ["notready", "Belum Ready"], ["ready", "Ready"], ["siap", "Siap Berangkat"]];

export default function DeparturePage() {
  const { can, user } = useAuth();
  const [params, setParams] = useSearchParams();
  const onlyMine = params.get("student") || "";
  const [f, setF] = useState("all");
  const [q, setQ] = useState("");
  const { data, loading, reload } = useApi("/departures");
  const [check, setCheck] = useState(null);
  const [edit, setEdit] = useState(null);
  const [createFor, setCreateFor] = useState(null);
  const [decision, setDecision] = useState(null);
  const { data: students } = useApi("/students?status=pemberkasan,visa,lulus,matching", [], can("departure_write"));
  const refreshed = () => reload();

  const rows = useMemo(() => {
    let list = data || [];
    if (onlyMine) list = list.filter((p) => p.student_id === onlyMine);
    if (f === "blocked") list = list.filter((p) => p.readiness?.readiness_status === "BLOCKED");
    if (f === "notready") list = list.filter((p) => p.readiness?.readiness_status === "NOT_READY");
    if (f === "ready") list = list.filter((p) => p.readiness?.readiness_status === "READY");
    if (f === "siap") list = list.filter((p) => ["siap", "berangkat"].includes(p.status));
    if (q) list = list.filter((p) => p.student_nama.toLowerCase().includes(q.toLowerCase()));
    return list;
  }, [data, f, q, onlyMine]);

  const stats = useMemo(() => {
    const l = data || [];
    return { total: l.length, blocked: l.filter((p) => p.readiness?.readiness_status === "BLOCKED").length, ready: l.filter((p) => p.readiness?.readiness_status === "READY").length, notready: l.filter((p) => p.readiness?.readiness_status === "NOT_READY").length };
  }, [data]);

  const isOwner = user?.role === "owner";

  return (
    <div>
      <PageHeader title="Keberangkatan" jp="出発管理" subtitle="Checklist, verifikasi, dan readiness keberangkatan siswa.">
        {can("departure_write") && students && (
          <select className="input max-w-xs" value="" onChange={(e) => { const s = students.find((x) => x.id === e.target.value); if (s) setCreateFor(s); }} data-testid="dep-create-select">
            <option value="">+ Buat profile departure…</option>
            {students.filter((s) => !(data || []).some((p) => p.student_id === s.id)).map((s) => <option key={s.id} value={s.id}>{s.nama_lengkap}</option>)}
          </select>)}
      </PageHeader>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard testId="stat-dep-total" label="Profile" value={stats.total} />
        <StatCard testId="stat-dep-blocked" label="Blocked" value={stats.blocked} tone="red" />
        <StatCard testId="stat-dep-ready" label="Ready" value={stats.ready} tone="green" />
        <StatCard testId="stat-dep-notready" label="Belum Ready" value={stats.notready} tone="amber" />
      </div>
      <div className="flex gap-1.5 mb-3 flex-wrap" data-testid="dep-filter">
        {FILTERS.map(([k, l]) => <button key={k} onClick={() => setF(k)} data-testid={`dep-filter-${k}`} className={`chip cursor-pointer ${f === k ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600"}`}>{l}</button>)}
      </div>
      <div className="mb-4"><input className="input max-w-sm" placeholder="Cari nama..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="dep-search-input" /></div>
      {loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="dep-table"><thead><tr><th>Siswa</th><th>Company / Job</th><th>Destination</th><th>Target</th><th>Readiness</th><th>Checklist</th><th>Blocker</th><th>Status</th><th>PIC</th><th></th></tr></thead>
          <tbody>{rows.length === 0 && <tr><td colSpan={10}><EmptyState text="Belum ada departure profile" /></td></tr>}
            {rows.map((p) => <tr key={p.id} data-testid={`dep-row-${p.id}`}>
              <td><Link to={`/siswa/${p.student_id}`} className="font-medium hover:text-red-600">{p.student_nama}</Link></td>
              <td className="text-xs">{p.company ? <>{p.company}<br />{p.position}</> : <span className="text-slate-400">-</span>}</td>
              <td className="text-xs">{p.destination || "-"}</td>
              <td className="text-xs">{p.target_departure_date ? fmtDate(p.target_departure_date) : "-"}{p.readiness?.days_to_departure != null ? ` (H-${p.readiness.days_to_departure})` : ""}</td>
              <td><span className={`chip ${READINESS_TONE[p.readiness?.readiness_status]}`}>{READINESS_LABELS[p.readiness?.readiness_status] || "-"}</span></td>
              <td className="text-xs">{p.readiness ? `${p.readiness.checklist_verified}/${p.readiness.checklist_total}` : "-"}</td>
              <td className="text-xs text-red-600 max-w-[220px]">{p.readiness?.blockers?.[0] || "-"}</td>
              <td className="text-xs capitalize">{p.status}{p.final_decision ? ` · ${p.final_decision}` : ""}</td>
              <td className="text-xs">{p.pic_name || "-"}</td>
              <td className="whitespace-nowrap flex gap-1">
                <button className="btn-ghost btn-sm" onClick={() => setCheck(p)} data-testid={`dep-check-${p.id}`}>Checklist</button>
                {can("departure_write") && <button className="btn-ghost btn-sm" onClick={() => setEdit(p)} data-testid={`dep-edit-${p.id}`}>Edit</button>}
                {isOwner && <button className="btn-ghost btn-sm" onClick={() => setDecision({ p, mode: "ready" })} data-testid={`dep-ready-${p.id}`}>Ready</button>}
                {isOwner && <button className="btn-ghost btn-sm" onClick={() => setDecision({ p, mode: "block" })} data-testid={`dep-block-${p.id}`}>Block</button>}
              </td>
            </tr>)}
          </tbody></table></div>)}
      {check && <ChecklistDialog profile={check} onClose={() => setCheck(null)} onChanged={refreshed} />}
      {edit && <ProfileDialog profile={edit} onClose={() => setEdit(null)} onSaved={refreshed} />}
      {createFor && <ProfileDialog student={createFor} onClose={() => setCreateFor(null)} onSaved={refreshed} />}
      {decision && <DecisionDialog profile={decision.p} mode={decision.mode} onClose={() => setDecision(null)} onSaved={refreshed} />}
    </div>
  );
}
