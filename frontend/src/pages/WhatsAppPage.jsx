import { useState } from "react";
import { RefreshCw, PlugZap, Send } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Tabs, FormDialog, Field, EmptyState, Loading } from "@/components/common";
import { fmtDateTime } from "@/lib/format";

const STATUS_CHIP = {
  queued: "bg-slate-100 text-slate-700 border-slate-200", sending: "bg-blue-50 text-blue-700 border-blue-200",
  sent: "bg-emerald-50 text-emerald-700 border-emerald-200", delivered: "bg-teal-50 text-teal-700 border-teal-200",
  read: "bg-emerald-100 text-emerald-800 border-emerald-300", failed: "bg-red-50 text-red-700 border-red-200",
  skipped_no_consent: "bg-amber-50 text-amber-700 border-amber-200",
};

export default function WhatsAppPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState("status");
  const isAdmin = can("whatsapp_admin");
  const { data: status, loading: loadingStatus, reload: reloadStatus } = useApi("/wa/status");
  const { data: templates, loading: loadingTpl, reload: reloadTpl } = useApi("/wa/templates", [], tab === "templates" && isAdmin);
  const [fStatus, setFStatus] = useState("");
  const logQs = `/wa/messages${fStatus ? `?status=${fStatus}` : ""}`;
  const { data: logs, loading: loadingLog, reload: reloadLog } = useApi(logQs, [logQs, tab === "log"]);

  const testConn = async () => {
    try {
      const { data } = await api.post("/wa/test-connection");
      toast.success(data.detail || `Mode: ${data.mode}`);
      reloadStatus();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const toggleTpl = async (t) => {
    try {
      await api.put(`/wa/templates/${t.key}`, { ...t, active: !t.active });
      toast.success(`Template ${t.key} ${t.active ? "dinonaktifkan" : "diaktifkan"}.`);
      reloadTpl();
    } catch (e) { toast.error(errMsg(e)); }
  };
  const retry = async (id) => {
    try {
      await api.post(`/wa/messages/${id}/retry`);
      toast.success("Retry dibuat, pengiriman diulang.");
      reloadLog();
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div>
      <PageHeader title="WhatsApp" jp="ワッツアップ" subtitle="Integrasi notifikasi eksternal — dry-run aman bila provider belum dikonfigurasi.">
        {isAdmin && <button className="btn-outline" onClick={testConn} data-testid="wa-test-btn"><PlugZap size={16} />Tes Koneksi</button>}
      </PageHeader>
      <Tabs active={tab} onChange={setTab} testPrefix="wa-tab" tabs={[
        { key: "status", label: "Status" },
        ...(isAdmin ? [{ key: "templates", label: "Template" }] : []),
        { key: "log", label: "Log Pesan" },
      ]} />

      {tab === "status" && (
        loadingStatus && !status ? <Loading /> : status ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 fade-up">
            {[["Provider", status.provider], ["Mode", status.enabled ? (status.dry_run ? "Dry-run" : "Live") : "Nonaktif"],
              ["Pengirim", status.sender_id || "-"], ["Webhook", status.webhook_configured ? "Terkonfigurasi" : "-"]].map(([l, v]) => (
              <div key={l} className="card p-4" data-testid={`wa-status-${l}`}><p className="label">{l}</p><p className="font-semibold">{v}</p></div>
            ))}
          </div>
        ) : <EmptyState />
      )}

      {tab === "templates" && (
        loadingTpl && !templates ? <Loading /> : (
          <div className="table-wrap fade-up"><table className="tbl" data-testid="wa-templates-table">
            <thead><tr><th>Key</th><th>Versi</th><th>Bahasa</th><th>Body</th><th>Aktif</th><th></th></tr></thead>
            <tbody>
              {(templates || []).length === 0 && <tr><td colSpan={6}><EmptyState text="Belum ada template" /></td></tr>}
              {(templates || []).map((t) => (
                <tr key={t.key} data-testid={`wa-tpl-${t.key}`}>
                  <td className="mono font-semibold">{t.key}</td><td>v{t.version}</td><td>{t.language}</td>
                  <td className="text-xs max-w-md">{t.body}</td>
                  <td><span className={`chip ${t.active ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100"}`}>{t.active ? "Aktif" : "Nonaktif"}</span></td>
                  <td><button className="btn-ghost btn-sm" onClick={() => toggleTpl(t)} data-testid={`wa-tpl-toggle-${t.key}`}>{t.active ? "Nonaktifkan" : "Aktifkan"}</button></td>
                </tr>
              ))}
            </tbody>
          </table></div>
        )
      )}

      {tab === "log" && (
        <>
          <div className="flex gap-2 mb-4 flex-wrap">
            <select className="input w-52" data-testid="wa-log-status" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
              <option value="">Semua status</option>
              {["queued", "sending", "sent", "delivered", "read", "failed", "skipped_no_consent"].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
            <button className="btn-ghost btn-sm" onClick={() => { reloadLog(); reloadStatus(); }} data-testid="wa-log-reload"><RefreshCw size={14} /></button>
          </div>
          {loadingLog && !logs ? <Loading /> : (
            <div className="table-wrap fade-up"><table className="tbl" data-testid="wa-log-table">
              <thead><tr><th>Waktu</th><th>Penerima</th><th>Template</th><th>Status</th><th>Percobaan</th><th></th></tr></thead>
              <tbody>
                {(logs || []).length === 0 && <tr><td colSpan={6}><EmptyState text="Belum ada pesan" /></td></tr>}
                {(logs || []).map((m) => (
                  <tr key={m.id} data-testid={`wa-msg-${m.id}`}>
                    <td className="text-xs whitespace-nowrap">{fmtDateTime(m.created_at)}</td>
                    <td><p className="font-medium text-sm">{m.recipient_name || "-"}</p><p className="text-xs text-slate-400 mono">{m.phone} · {m.recipient_role}</p>
                      {m.fail_reason && <p className="text-xs text-red-600">{m.fail_reason}</p>}</td>
                    <td className="text-xs mono">{m.template_key} v{m.template_version}{m.dry_run && <span className="chip ml-1 bg-slate-100">dry-run</span>}</td>
                    <td><span className={`chip ${STATUS_CHIP[m.status] || "bg-slate-100"}`}>{m.status}</span></td>
                    <td className="text-xs">{m.attempts}x</td>
                    <td>{m.status === "failed" && m.retryable && can("whatsapp_send") && <button className="btn-ghost btn-sm text-blue-700" title="Kirim ulang" onClick={() => retry(m.id)} data-testid={`wa-retry-${m.id}`}><Send size={14} /></button>}</td>
                  </tr>
                ))}
              </tbody>
            </table></div>
          )}
        </>
      )}
    </div>
  );
}
