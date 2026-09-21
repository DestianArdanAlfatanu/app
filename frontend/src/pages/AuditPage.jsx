import { useState } from "react";
import { useApi } from "@/hooks/useApi";
import { PageHeader, Loading, EmptyState } from "@/components/common";
import { fmtDateTime, ROLE_LABELS } from "@/lib/format";

const ENTITIES = [["", "Semua"], ["payment", "Pembayaran"], ["transaction", "Transaksi"], ["student", "Siswa"], ["document", "Dokumen"], ["grade", "Nilai"], ["attendance", "Absensi"], ["employee", "SDM"], ["user", "Pengguna"], ["interview", "Interview"], ["reconciliation", "Rekonsiliasi"]];
const fmt = (v) => v == null ? "-" : typeof v === "object" ? Object.entries(v).map(([k, x]) => `${k}: ${typeof x === "number" ? x.toLocaleString("id-ID") : Array.isArray(x) ? x.length + " item" : String(x)}`).join(" · ") : String(v);

export default function AuditPage() {
  const [entity, setEntity] = useState("");
  const { data, loading } = useApi(`/audit-logs${entity ? `?entity=${entity}` : ""}`);
  return (
    <div>
      <PageHeader title="Audit Trail" jp="監査ログ" subtitle="Setiap perubahan penting tercatat: siapa, kapan, data sebelum & sesudah, dan alasannya." />
      <div className="flex gap-1.5 flex-wrap mb-4" data-testid="audit-filter">{ENTITIES.map(([k, l]) => <button key={k} onClick={() => setEntity(k)} data-testid={`audit-filter-${k || "all"}`} className={`chip cursor-pointer ${entity === k ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600"}`}>{l}</button>)}</div>
      {loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="audit-table"><thead><tr><th>Waktu</th><th>Pengguna</th><th>Aksi</th><th>Entitas</th><th>Sebelum</th><th>Sesudah</th><th>Alasan</th></tr></thead>
          <tbody>{(data || []).length === 0 && <tr><td colSpan={7}><EmptyState /></td></tr>}
            {(data || []).map((a) => <tr key={a.id} data-testid={`audit-row-${a.id}`}><td className="whitespace-nowrap text-xs">{fmtDateTime(a.timestamp)}</td><td><p className="font-medium">{a.user_name}</p><p className="text-[11px] text-red-600 uppercase font-semibold">{ROLE_LABELS[a.user_role] || a.user_role}</p></td><td><span className="chip bg-slate-50">{a.action}</span></td><td className="text-xs">{a.entity}<br /><span className="mono text-slate-400">{String(a.entity_id).slice(0, 8)}</span></td>
              <td className="text-xs text-slate-500 max-w-[220px]">{fmt(a.before)}</td><td className="text-xs text-slate-800 max-w-[220px]">{fmt(a.after)}</td><td className="text-xs">{a.alasan || "-"}</td></tr>)}
          </tbody></table></div>)}
    </div>
  );
}
