import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { LayoutDashboard, User, GraduationCap, Wallet, FolderOpen, Bell, Settings, LogOut } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { Loading, EmptyState } from "@/components/common";

const NAV = [
  { to: "/portal", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/portal/profile", label: "Profil", icon: User },
  { to: "/portal/academic", label: "Akademik", icon: GraduationCap },
  { to: "/portal/finance", label: "Keuangan", icon: Wallet },
  { to: "/portal/documents", label: "Dokumen", icon: FolderOpen },
  { to: "/portal/notifications", label: "Notifikasi", icon: Bell },
  { to: "/portal/settings", label: "Pengaturan", icon: Settings },
];

export default function PortalLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();
  const { data: me, error: meError } = useApi("/student/auth/me", [loc.pathname]);

  const doLogout = async () => { try { await api.post("/student/auth/logout"); } catch (_) { /* ignore */ } await logout(); nav("/portal/login"); };

  if (me?.must_change_password && loc.pathname !== "/portal/settings") {
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-[#F8FAFC]">
        <div className="card card-pad max-w-sm text-center">
          <p className="font-bold">Ganti password terlebih dahulu</p>
          <p className="text-xs text-slate-500 mt-1 mb-4">Akun baru wajib mengganti password awal.</p>
          <button className="btn-primary" onClick={() => nav("/portal/settings")}>Ke Pengaturan</button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <header className="sticky top-0 z-20 h-16 bg-white/85 backdrop-blur-md border-b border-slate-200 flex items-center gap-3 px-4 sm:px-6">
        <div className="leading-tight">
          <p className="font-bold text-sm">Portal Siswa</p>
          <p className="text-[11px] text-slate-500">{user?.name}</p>
        </div>
        <button className="btn-ghost h-9 w-9 px-0 ml-auto" onClick={doLogout} title="Keluar" data-testid="portal-logout-btn"><LogOut size={18} /></button>
      </header>
      <nav className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-3 sticky top-16 z-10">
        {NAV.map((n) => (
          <NavLink key={n.to} to={n.to} end={n.end} data-testid={`portal-nav-${n.to === "/portal" ? "dashboard" : n.to.split("/")[2]}`}
            className={({ isActive }) => `px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px flex items-center gap-1.5 ${isActive ? "border-red-600 text-slate-900" : "border-transparent text-slate-500"}`}>
            <n.icon size={15} />{n.label}
          </NavLink>
        ))}
      </nav>
      <main className="p-4 sm:p-6 max-w-[1100px] mx-auto">
        {me ? <Outlet /> : meError ? <EmptyState text={`Data akun gagal dimuat: ${errMsg(meError)}. Muat ulang halaman.`} /> : <Loading />}
      </main>
    </div>
  );
}
