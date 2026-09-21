import { createContext, useContext, useEffect, useState } from "react";
import { api, TOKEN_KEY } from "@/lib/api";

const AuthCtx = createContext(null);

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
  joborder: ["owner", "admin", "marketing", "staff"],
  joborder_write: ["owner", "admin", "marketing"],
  sdm: ["owner", "admin", "hr"],
  sdm_write: ["owner", "hr"],
  laporan: ["owner", "admin", "finance", "hr"],
  audit: ["owner", "admin", "finance", "hr"],
  pengguna: ["owner"],
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

  const can = (module) => !!user && (user.role === "owner" || (MODULES[module] || []).includes(user.role));

  return <AuthCtx.Provider value={{ user, checking, login, logout, can }}>{children}</AuthCtx.Provider>;
}

export const useAuth = () => useContext(AuthCtx);
