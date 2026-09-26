import { createContext, useContext, useEffect, useState } from "react";
import { api, TOKEN_KEY } from "@/lib/api";

const AuthCtx = createContext(null);
const HIDDEN_MODULES = ["whatsapp", "whatsapp_send", "whatsapp_admin"];

const MODULES = {
  dashboard: ["owner", "admin", "finance", "hr", "guru", "marketing", "staff"],
  siswa: ["owner", "admin", "finance", "hr", "guru", "marketing", "staff"],
  siswa_write: ["owner", "admin", "marketing", "staff"],
  kelas: ["owner", "admin", "guru", "hr", "marketing", "staff"],
  kelas_write: ["owner", "admin"],
  absensi: ["owner", "admin", "guru"],
  nilai: ["owner", "admin", "guru"],
  pembayaran: ["owner", "admin", "finance"],
  pembayaran_write: ["owner", "finance"],
  keuangan: ["owner", "admin", "finance"],
  keuangan_write: ["owner", "finance"],
  expense: ["owner", "admin", "finance", "staff", "marketing"],
  expense_write: ["owner", "finance", "staff", "marketing"],
  expense_approve: ["owner", "finance"],
  expense_pay: ["owner", "finance"],
  joborder: ["owner", "admin", "marketing", "staff"],
  joborder_write: ["owner", "admin", "marketing"],
  sdm: ["owner", "admin", "hr"],
  sdm_write: ["owner", "hr"],
  hr_attendance: ["owner", "admin", "hr"],
  hr_attendance_write: ["owner", "hr"],
  leave: ["owner", "admin", "hr"],
  leave_write: ["owner", "admin", "hr"],
  leave_approve: ["owner", "hr"],
  payroll: ["owner", "admin", "hr", "finance"],
  payroll_write: ["owner", "hr"],
  payroll_approve: ["owner"],
  payroll_pay: ["owner", "finance"],
  laporan: ["owner", "admin", "finance", "hr"],
  audit: ["owner", "admin", "finance", "hr"],
  whatsapp: [],
  followup: ["owner", "admin", "marketing", "staff"],
  departure: ["owner", "admin", "staff", "finance", "hr", "guru", "marketing"],
  departure_write: ["owner", "admin", "staff"],
  departure_verify: ["owner", "admin", "staff", "finance", "hr"],
  whatsapp_send: [],
  whatsapp_admin: [],
  pengguna: ["owner", "admin"],
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY)) { setChecking(false); return; }
    api.get("/auth/me").then((r) => setUser(r.data)).catch(() => setUser(null)).finally(() => setChecking(false));
  }, []);

  const login = async (email, password) => {
    const { data } = await api.post("/auth/login", { email, password });
    localStorage.setItem(TOKEN_KEY, data.token);
    setUser(data.user);
    return data.user;
  };

  const logout = async () => {
    try { await api.post("/auth/logout"); } catch (_) { /* ignore */ }
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
  };

  const can = (module) => {
    if (HIDDEN_MODULES.includes(module)) return false;
    return !!user && (user.role === "owner" || (MODULES[module] || []).includes(user.role));
  };

  return <AuthCtx.Provider value={{ user, checking, login, logout, can }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
