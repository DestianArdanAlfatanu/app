import { useNavigate } from "react-router-dom";
import { useApi } from "@/hooks/useApi";
import { PageHeader, StatCard, Loading, Money, EmptyState } from "@/components/common";
import { rupiah, fmtDate } from "@/lib/format";
import { Users, GraduationCap, Wallet, FolderOpen, Bell, MessageCircle, Plane } from "lucide-react";

export default function PortalDashboard() {
  const nav = useNavigate();
  const { data, loading } = useApi("/student/dashboard");
  const { data: dep } = useApi("/student/departure");
  if (loading && !data) return <Loading />;
  if (!data) return <EmptyState text="Data dashboard tidak tersedia" />;
  const { profile, academic, finance, documents, notifications, whatsapp } = data;
  return (
    <div>
      <PageHeader title={`Halo, ${profile.nama?.split(" ")[0] || "Siswa"}`} subtitle={`${profile.status || "-"}${profile.kelas ? ` · ${profile.kelas}` : ""}`} />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <StatCard label="Kehadiran" value={`${academic.kehadiran ?? "-"}%`} icon={Users} onClick={() => nav("/portal/academic")} />
        <StatCard label="Nilai Rata-rata" value={academic.nilai_rata ?? "-"} icon={GraduationCap} tone="green" onClick={() => nav("/portal/academic")} />
        <StatCard label="Sisa Tagihan" value={rupiah(finance.sisa)} hint={finance.jatuh_tempo ? `Jatuh tempo ${fmtDate(finance.jatuh_tempo)}` : ""} icon={Wallet} tone={finance.sisa > 0 ? "amber" : "green"} onClick={() => nav("/portal/finance")} />
        <StatCard label="Dokumen" value={`${documents.total}`} hint={`${documents.with_expiry} ber-expiry`} icon={FolderOpen} tone="blue" onClick={() => nav("/portal/documents")} />
      </div>
      <div className="grid sm:grid-cols-2 gap-3">
        <div className="card card-pad">
          <div className="flex items-center justify-between mb-2"><h3 className="font-semibold text-sm flex items-center gap-2"><Bell size={15} />Notifikasi{notifications.unread > 0 && <span className="chip bg-red-600 text-white border-red-600">{notifications.unread} baru</span>}</h3><button className="text-xs text-red-600 font-semibold" onClick={() => nav("/portal/notifications")}>Lihat semua</button></div>
          {notifications.recent.length === 0 && <p className="text-xs text-slate-400">Belum ada notifikasi.</p>}
          {notifications.recent.map((n) => <p key={n.id} className="text-xs py-1.5 border-b border-slate-100 last:border-0"><b>{n.judul}</b> — {n.pesan}</p>)}
        </div>
        <div className="card card-pad">
          <h3 className="font-semibold text-sm flex items-center gap-2 mb-2"><MessageCircle size={15} />WhatsApp</h3>
          <p className="text-xs text-slate-500">Notifikasi pembayaran ke nomor Anda: <b>{whatsapp.opt_in ? "Aktif" : "Nonaktif"}</b></p>
          <button className="btn-outline btn-sm mt-2" onClick={() => nav("/portal/settings")}>Kelola</button>
        </div>
        {dep?.profile && (
          <div className="card card-pad sm:col-span-2">
            <h3 className="font-semibold text-sm flex items-center gap-2 mb-2"><Plane size={15} />Keberangkatan</h3>
            <p className="text-xs text-slate-600">Status: <b>{dep.readiness?.readiness_status}</b>
              {dep.profile.target_departure_date ? ` · Target ${fmtDate(dep.profile.target_departure_date)}` : ""}
              {dep.profile.destination ? ` · ${dep.profile.destination}` : ""}</p>
            <p className="text-xs text-slate-500 mt-1">Checklist {dep.readiness?.checklist_verified}/{dep.readiness?.checklist_total} verified</p>
          </div>)}
      </div>
    </div>
  );
}
