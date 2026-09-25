import { useState } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { Field, Loading } from "@/components/common";

export default function PortalLogin() {
  const { user, checking } = useAuth();
  const nav = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [saving, setSaving] = useState(false);

  if (!checking && user?.role === "student") return <Navigate to="/portal" replace />;

  const submit = async () => {
    setSaving(true);
    try {
      const { data } = await api.post("/student/auth/login", form);
      localStorage.setItem("lpk_token", data.token);
      window.location.href = data.user?.must_change_password ? "/portal/settings" : "/portal";
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.1fr_1fr] bg-[#F8FAFC]">
      <div className="hidden lg:flex flex-col justify-center px-16 bg-[#0F172A] text-white">
        <p className="font-jp text-sm text-slate-400">生徒ポータル</p>
        <h1 className="text-4xl font-bold tracking-tight mt-2">Portal Siswa</h1>
        <p className="text-slate-300 mt-4 text-sm leading-relaxed">Lihat jadwal, kehadiran, nilai, tagihan, dokumen, dan progres training Anda.</p>
      </div>
      <div className="flex items-center justify-center p-6">
        <form className="card card-pad w-full max-w-sm fade-up" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <h2 className="text-xl font-bold">Masuk Portal Siswa</h2>
          <p className="text-xs text-slate-500 mt-1 mb-4">Gunakan email & password dari admin LPK.</p>
          <Field label="Email"><input type="email" className="input" data-testid="portal-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></Field>
          <Field label="Password"><input type="password" className="input" data-testid="portal-password-input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required /></Field>
          <button className="btn-primary w-full mt-2" disabled={saving} data-testid="portal-login-btn">{saving ? "Memeriksa..." : "Masuk"}</button>
        </form>
      </div>
    </div>
  );
}

export function PortalGuard({ children }) {
  const { user, checking } = useAuth();
  if (checking) return <Loading />;
  if (!user) return <Navigate to="/portal/login" replace />;
  if (user.role !== "student") return <div className="p-6 card card-pad text-sm text-slate-600" data-testid="forbidden">Halaman ini khusus siswa.</div>;
  return children;
}
