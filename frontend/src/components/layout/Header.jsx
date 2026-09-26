import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell, LogOut, Menu, Search } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { ROLE_LABELS, rupiah } from "@/lib/format";
import { StatusBadge } from "@/components/common";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export const Header = ({ onMenu }) => {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const [results, setResults] = useState(null);
  const [notifs, setNotifs] = useState([]);
  const [unread, setUnread] = useState(0);
  const [notifOpen, setNotifOpen] = useState(false);
  const timer = useRef();

  useEffect(() => { loadNotifs(); }, []);

  const loadNotifs = async () => {
    try {
      const n = await api.get("/notifications");
      setNotifs(n.data); setUnread(n.data.filter((x) => !x.read).length);
    } catch (_) { /* ignore */ }
  };
  const markRead = async (n) => {
    try { await api.post(`/notifications/${n.id}/read`); } catch (_) { /* ignore */ }
    nav(n.link); loadNotifs();
  };
  const markAllRead = async () => { try { await api.post("/notifications/read-all"); } catch (_) {} loadNotifs(); };

  useEffect(() => {
    clearTimeout(timer.current);
    if (q.trim().length < 2) { setResults(null); return; }
    timer.current = setTimeout(() => api.get(`/search?q=${encodeURIComponent(q)}`).then((r) => setResults(r.data)).catch(() => {}), 300);
  }, [q]);

  const go = (id) => { setQ(""); setResults(null); nav(`/siswa/${id}`); };
  const goRoute = (route) => { setQ(""); setResults(null); nav(route); };
  const sRows = results?.students || [];
  const eRows = results?.employees || [];
  const jRows = results?.job_orders || [];
  const emptySearch = results && sRows.length === 0 && eRows.length === 0 && jRows.length === 0;

  return (
    <header className="sticky top-0 z-20 h-16 bg-white/85 backdrop-blur-md border-b border-slate-200 flex items-center gap-3 px-4 sm:px-6">
      <button className="lg:hidden btn-ghost h-9 w-9 px-0" onClick={onMenu} data-testid="menu-toggle-btn"><Menu size={20} /></button>
      <div className="relative flex-1 max-w-xl">
        <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
        <input data-testid="global-search-input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Cari siswa, guru, karyawan, job order..." className="input pl-9 h-9 bg-slate-50" />
        {results && (
          <div data-testid="global-search-results" className="absolute top-11 left-0 right-0 card shadow-xl overflow-hidden max-h-[70vh] overflow-y-auto">
            {emptySearch && <p className="p-4 text-sm text-slate-500">Tidak ditemukan</p>}
            {sRows.length > 0 && <p className="px-3 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Siswa</p>}
            {sRows.map((s) => (
              <button key={s.id} onClick={() => go(s.id)} data-testid={`search-result-${s.id}`} className="w-full text-left p-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
                <div className="flex items-center justify-between gap-2"><span className="font-semibold text-sm">{s.nama_lengkap}</span><StatusBadge status={s.status} /></div>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-x-3 gap-y-0.5 mt-1.5 text-[11px] text-slate-500">
                  <span>Kelas: <b className="text-slate-700">{s.kelas || "-"}</b></span>
                  {s.pembayaran && <span>Bayar: <b className="text-slate-700 mono">{rupiah(s.pembayaran.bayar)} / {rupiah(s.pembayaran.total)}</b></span>}
                  <span>Hadir: <b className="text-slate-700">{s.absensi.persentase}%</b></span>
                  <span>Nilai: <b className="text-slate-700">{s.nilai ?? "-"}</b></span>
                  <span>Job Order: <b className="text-slate-700">{s.job_order || "-"}</b></span>
                  <span>Dokumen: <b className="text-slate-700">{s.dokumen.lengkap}/{s.dokumen.total}</b></span>
                </div>
              </button>
            ))}
            {eRows.length > 0 && <p className="px-3 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Guru & Karyawan</p>}
            {eRows.map((e) => (
              <button key={e.entity_id} onClick={() => goRoute(e.route)} data-testid={`search-emp-${e.entity_id}`} className="w-full text-left p-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
                <div className="font-semibold text-sm">{e.title}</div>
                <div className="text-[11px] text-slate-500">{e.subtitle}</div>
              </button>
            ))}
            {jRows.length > 0 && <p className="px-3 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">Job Order</p>}
            {jRows.map((j) => (
              <button key={j.entity_id} onClick={() => goRoute(j.route)} data-testid={`search-job-${j.entity_id}`} className="w-full text-left p-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors">
                <div className="font-semibold text-sm">{j.title}</div>
                <div className="text-[11px] text-slate-500">{j.subtitle}</div>
              </button>
            ))}
          </div>
        )}
      </div>
      <Popover open={notifOpen} onOpenChange={(o) => { setNotifOpen(o); if (o) loadNotifs(); }}>
        <PopoverTrigger asChild>
          <button className="relative btn-ghost h-9 w-9 px-0" data-testid="notifications-btn">
            <Bell size={18} />
            {unread > 0 && <span className="absolute top-1 right-1 h-4 min-w-4 px-1 rounded-full bg-red-600 text-white text-[10px] font-bold flex items-center justify-center">{unread}</span>}
          </button>
        </PopoverTrigger>
        <PopoverContent align="end" className="w-96 p-0 bg-white" data-testid="notifications-panel">
          <div className="px-4 py-3 border-b border-slate-100 font-semibold text-sm flex items-center justify-between">
            <span>Notifikasi ({notifs.length})</span>
            {unread > 0 && <button className="text-xs text-red-600 font-semibold" onClick={markAllRead} data-testid="notif-read-all-btn">Tandai dibaca</button>}
          </div>
          <div className="max-h-96 overflow-y-auto">
            {notifs.length === 0 && <p className="p-4 text-sm text-slate-500">Tidak ada notifikasi</p>}
            {notifs.map((n) => (
              <button key={n.id || n.dedupe_key} onClick={() => markRead(n)} className={`w-full text-left px-4 py-3 border-b border-slate-100 last:border-0 hover:bg-slate-50 transition-colors flex gap-3 ${n.read ? "opacity-60" : ""}`}>
                <span className={`mt-1.5 h-2 w-2 rounded-full shrink-0 ${n.level === "danger" ? "bg-red-600" : n.level === "warning" ? "bg-amber-500" : "bg-blue-500"}`} />
                <div><p className="text-sm font-medium text-slate-800">{n.judul}</p><p className="text-xs text-slate-500">{n.pesan}</p></div>
              </button>
            ))}
          </div>
        </PopoverContent>
      </Popover>
      <div className="hidden sm:flex items-center gap-3 pl-3 border-l border-slate-200">
        <div className="text-right leading-tight">
          <p className="text-sm font-semibold text-slate-800" data-testid="header-user-name">{user?.name}</p>
          <p className="text-[11px] text-red-600 font-semibold uppercase tracking-wider" data-testid="header-user-role">{ROLE_LABELS[user?.role]}</p>
        </div>
        <div className="h-9 w-9 rounded-full bg-slate-900 text-white flex items-center justify-center text-sm font-bold">{user?.name?.[0]}</div>
      </div>
      <button className="btn-ghost h-9 w-9 px-0" onClick={async () => { await logout(); nav("/login"); }} title="Keluar" data-testid="logout-btn"><LogOut size={18} /></button>
    </header>
  );
};
