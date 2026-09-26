import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { errMsg } from "@/lib/api";

// Akun demo hanya untuk lingkungan dev (REACT_APP_DEMO=1); tidak ikut di build production.
const SHOW_DEMO = process.env.REACT_APP_DEMO === "1";
const DEMO = [
  ["Owner", "owner@lpk.id", "owner123"], ["Admin", "admin@lpk.id", "password123"], ["Keuangan", "finance@lpk.id", "password123"],
  ["HR", "hr@lpk.id", "password123"], ["Guru", "guru@lpk.id", "password123"], ["Marketing", "marketing@lpk.id", "password123"],
];

export default function LoginPage() {
  const { user, login, checking } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  if (!checking && user) return <Navigate to="/" replace />;

  const submit = async (e) => {
    e?.preventDefault();
    setErr(""); setLoading(true);
    try { await login(email.trim(), password); nav("/"); } catch (ex) { setErr(errMsg(ex)); } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr]">
      <div className="hidden lg:flex flex-col justify-between bg-[#0F172A] text-white p-12 relative overflow-hidden">
        <div className="absolute -right-32 -top-32 h-[520px] w-[520px] rounded-full bg-red-600/90" />
        <div className="absolute right-24 bottom-16 font-jp text-[220px] leading-none text-white/[0.04] select-none">日本</div>
        <div className="relative flex items-center gap-3">
          <div className="h-10 w-10 rounded-md bg-white flex items-center justify-center"><span className="h-4 w-4 rounded-full bg-red-600 block" /></div>
          <div><p className="font-bold tracking-tight">Sistem LPK</p><p className="font-jp text-xs text-slate-400">技能実習生管理システム</p></div>
        </div>
        <div className="relative max-w-md">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-red-300">Pusat Operasional Lembaga</p>
          <h2 className="text-4xl font-bold tracking-tight mt-3 leading-tight">Satu sistem untuk siswa, keuangan, dan penyaluran kerja ke Jepang.</h2>
          <p className="text-slate-300 mt-4 text-sm leading-relaxed">Pendaftaran, seleksi, pelatihan, pembayaran, dokumen, job order, hingga alumni — terintegrasi, otomatis menghitung, dan memiliki jejak audit.</p>
        </div>
        <p className="relative text-xs text-slate-500">© {new Date().getFullYear()} LPK Penyaluran Kerja Jepang</p>
      </div>
      <div className="flex items-center justify-center p-6 sm:p-12 bg-[#F8FAFC]">
        <div className="w-full max-w-md fade-up">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="h-10 w-10 rounded-md bg-slate-900 flex items-center justify-center"><span className="h-4 w-4 rounded-full bg-red-600 block" /></div>
            <p className="font-bold tracking-tight text-lg">Sistem LPK</p>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">Masuk ke sistem</h1>
          <p className="text-sm text-slate-500 mt-1">Gunakan akun yang diberikan oleh Super Admin.</p>
          <form onSubmit={submit} className="mt-8 space-y-4" data-testid="login-form">
            <div><label className="label">Email</label><input data-testid="login-email-input" className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nama@lpk.id" required /></div>
            <div><label className="label">Password</label><input data-testid="login-password-input" className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required /></div>
            {err && <p data-testid="login-error" className="text-sm text-red-600 bg-red-50 border border-red-100 rounded-md px-3 py-2">{err}</p>}
            <button data-testid="login-submit-btn" className="btn-red w-full h-11" disabled={loading}>{loading ? "Memproses..." : "Masuk"}</button>
          </form>
          {SHOW_DEMO && <div className="mt-8">
            <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-2">Akun demo</p>
            <div className="grid grid-cols-3 gap-2">
              {DEMO.map(([r, e, p]) => (
                <button key={r} type="button" data-testid={`demo-login-${r.toLowerCase()}`} onClick={() => { setEmail(e); setPassword(p); }}
                  className="btn-outline btn-sm justify-start text-slate-600">{r}</button>
              ))}
            </div>
          </div>}
        </div>
      </div>
    </div>
  );
}
