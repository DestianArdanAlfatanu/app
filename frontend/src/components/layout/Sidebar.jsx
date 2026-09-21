import { NavLink } from "react-router-dom";
import { LayoutDashboard, Users, BookOpen, ClipboardCheck, GraduationCap, Wallet, Landmark, Briefcase, UserCog, FileBarChart, History, ShieldCheck, X } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const NAV = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard, mod: "dashboard", end: true },
  { section: "Siswa" },
  { to: "/siswa", label: "Data Siswa", icon: Users, mod: "siswa" },
  { to: "/kelas", label: "Kelas & Jadwal", icon: BookOpen, mod: "kelas" },
  { to: "/absensi", label: "Absensi", icon: ClipboardCheck, mod: "absensi" },
  { to: "/nilai", label: "Nilai & Ujian", icon: GraduationCap, mod: "nilai" },
  { to: "/job-order", label: "Job Order Jepang", icon: Briefcase, mod: "joborder" },
  { section: "Keuangan" },
  { to: "/pembayaran", label: "Pembayaran Siswa", icon: Wallet, mod: "pembayaran" },
  { to: "/keuangan", label: "Kas & Keuangan", icon: Landmark, mod: "keuangan" },
  { section: "Manajemen" },
  { to: "/sdm", label: "Guru & Karyawan", icon: UserCog, mod: "sdm" },
  { to: "/laporan", label: "Laporan", icon: FileBarChart, mod: "laporan" },
  { to: "/audit", label: "Audit Trail", icon: History, mod: "audit" },
  { to: "/pengguna", label: "Pengguna & Akses", icon: ShieldCheck, mod: "pengguna" },
];

export const Sidebar = ({ open, onClose }) => {
  const { can } = useAuth();
  const items = NAV.filter((n) => n.section || can(n.mod));
  const cleaned = items.filter((n, i) => !n.section || (items[i + 1] && !items[i + 1].section));
  return (
    <>
      {open && <div className="fixed inset-0 bg-slate-900/50 z-30 lg:hidden" onClick={onClose} data-testid="sidebar-overlay" />}
      <aside data-testid="sidebar" className={`fixed z-40 inset-y-0 left-0 w-[260px] bg-[#0F172A] text-white flex flex-col transition-transform duration-200 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="h-16 flex items-center gap-3 px-5 border-b border-white/10">
          <div className="h-9 w-9 rounded-md bg-white flex items-center justify-center"><span className="h-4 w-4 rounded-full bg-red-600 block" /></div>
          <div className="leading-tight">
            <p className="font-bold text-sm tracking-tight">Sistem LPK</p>
            <p className="font-jp text-[10px] text-slate-400">技能実習生管理システム</p>
          </div>
          <button className="ml-auto lg:hidden text-slate-400 hover:text-white" onClick={onClose} data-testid="sidebar-close-btn"><X size={18} /></button>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {cleaned.map((n, i) => n.section
            ? <p key={i} className="px-3 pt-4 pb-1 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500">{n.section}</p>
            : <NavLink key={n.to} to={n.to} end={n.end} onClick={onClose} data-testid={`nav-${n.to === "/" ? "dashboard" : n.to.slice(1)}`}
                className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}><n.icon size={17} strokeWidth={1.8} />{n.label}</NavLink>)}
        </nav>
        <div className="px-5 py-4 border-t border-white/10 text-[11px] text-slate-500">LPK Penyaluran Kerja Jepang · v1.0</div>
      </aside>
    </>
  );
};
