import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, Loading, EmptyState } from "@/components/common";
import { CfActions, CF_OUTCOME_LABELS } from "@/components/CandidateDialogs";
import { fmtDate } from "@/lib/format";

const FILTERS = [["all", "Semua"], ["never", "Belum Dihubungi"], ["due", "Due Hari Ini"], ["overdue", "Overdue"], ["closed", "Closed"]];

export default function FollowupPage() {
  const { can } = useAuth();
  const [f, setF] = useState("all");
  const [fsumber, setFsumber] = useState("");
  const [foutcome, setFoutcome] = useState("");
  const [q, setQ] = useState("");
  const { data: students, loading, reload } = useApi("/students?status=calon_siswa");
  const { data: cmap, reload: reloadMap } = useApi("/candidate-followups/summary-map");
  const { data: overview, reload: reloadOverview } = useApi("/candidate-followups/overview");
  const refreshed = () => { reload(); reloadMap(); reloadOverview(); };

  const rows = useMemo(() => {
    const map = cmap || {};
    let list = (students || []).map((s) => ({ ...s, cf: map[s.id] || null }));
    if (f === "never") list = list.filter((s) => !s.cf);
    if (f === "due") list = list.filter((s) => s.cf?.next_follow_up_at === new Date().toISOString().slice(0, 10) && s.cf?.follow_up_status === "open");
    if (f === "overdue") list = list.filter((s) => s.cf?.next_follow_up_at && s.cf.next_follow_up_at < new Date().toISOString().slice(0, 10) && s.cf?.follow_up_status === "open");
    if (f === "closed") list = list.filter((s) => s.cf?.follow_up_status === "closed");
    if (fsumber) list = list.filter((s) => (s.sumber_prospek || "") === fsumber);
    if (foutcome) list = list.filter((s) => s.cf?.last_outcome === foutcome);
    if (q) list = list.filter((s) => s.nama_lengkap.toLowerCase().includes(q.toLowerCase()) || (s.no_hp || "").includes(q));
    return list;
  }, [students, cmap, f, fsumber, foutcome, q]);

  const sumbers = useMemo(() => [...new Set((students || []).map((s) => s.sumber_prospek).filter(Boolean))], [students]);

  return (
    <div>
      <PageHeader title="Follow-up Calon Siswa" jp="見込み客管理" subtitle="Antrean, pencatatan, dan reminder follow-up prospek." />
      {overview && (
        <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
          <StatCard testId="stat-total-calon" label="Total Calon" value={overview.total_calon} />
          <StatCard testId="stat-belum-hubungi" label="Belum Dihubungi" value={overview.never_contacted?.length ?? "-"} tone="amber" />
          <StatCard testId="stat-fu-today" label="Due Hari Ini" value={overview.due_today?.length ?? "-"} tone="red" />
          <StatCard testId="stat-fu-overdue" label="Overdue" value={overview.overdue?.length ?? "-"} tone="red" />
          <StatCard testId="stat-fu-closed" label="Closed" value={overview.closed?.length ?? "-"} tone="green" />
        </div>)}
      <div className="flex gap-1.5 mb-3 flex-wrap" data-testid="cf-filter">
        {FILTERS.map(([k, l]) => <button key={k} onClick={() => setF(k)} data-testid={`cf-filter-${k}`} className={`chip cursor-pointer ${f === k ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600"}`}>{l}</button>)}
      </div>
      <div className="flex gap-2 mb-4 flex-wrap">
        <input className="input max-w-xs" placeholder="Cari nama / HP..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="cf-search-input" />
        <select className="input max-w-[180px]" value={fsumber} onChange={(e) => setFsumber(e.target.value)} data-testid="cf-filter-sumber"><option value="">Semua sumber</option>{sumbers.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <select className="input max-w-[180px]" value={foutcome} onChange={(e) => setFoutcome(e.target.value)} data-testid="cf-filter-outcome"><option value="">Semua outcome</option>{Object.entries(CF_OUTCOME_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
      </div>
      {loading && !students ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="cf-table"><thead><tr><th>Nama</th><th>Kontak</th><th>Sumber</th><th>Pemilik</th><th>Last Contact</th><th>Outcome</th><th>Next Follow-up</th><th></th></tr></thead>
          <tbody>{rows.length === 0 && <tr><td colSpan={8}><EmptyState text="Tidak ada calon pada filter ini" /></td></tr>}
            {rows.map((s) => <tr key={s.id} data-testid={`cf-row-${s.id}`}>
              <td><Link to={`/siswa/${s.id}`} className="font-medium hover:text-red-600">{s.nama_lengkap}</Link></td>
              <td className="text-xs">{s.no_hp || "-"}</td>
              <td className="text-xs">{s.sumber_prospek || <span className="text-slate-400">-</span>}</td>
              <td className="text-xs">{s.pemilik_lead || <span className="text-slate-400">-</span>}</td>
              <td className="text-xs">{s.cf ? fmtDate(s.cf.last_contacted?.slice(0, 10)) : <span className="text-slate-400">Belum dihubungi</span>}</td>
              <td className="text-xs">{s.cf ? (CF_OUTCOME_LABELS[s.cf.last_outcome] || s.cf.last_outcome) : "-"}</td>
              <td className="text-xs">{s.cf?.next_follow_up_at ? fmtDate(s.cf.next_follow_up_at) : "-"}</td>
              <td>{can("followup") && <CfActions student={s} onChanged={refreshed} />}</td>
            </tr>)}
          </tbody></table></div>)}
    </div>
  );
}
