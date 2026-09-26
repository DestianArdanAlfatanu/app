import axios from "axios";
import { toast } from "sonner";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const TOKEN_KEY = "lpk_token";

export const api = axios.create({ baseURL: API });

api.interceptors.request.use((cfg) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  return cfg;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    const path = window.location.pathname;
    if (e.response?.status === 401) {
      const portal = path.startsWith("/portal");
      const loginPage = portal ? "/portal/login" : "/login";
      if (path !== loginPage) {
        localStorage.removeItem(TOKEN_KEY);
        window.location.href = loginPage;
      }
    }
    return Promise.reject(e);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Terjadi kesalahan";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(", ");
  return d.msg || String(d);
}

// Blob URL berjalan di origin aplikasi, jadi hanya tipe yang tidak bisa menjalankan skrip
// yang boleh dirender. HTML/SVG/tipe lain selalu diunduh, tidak pernah dibuka.
const INLINE_SAFE_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/webp"];

function filenameFrom(headers) {
  const m = /filename\*=UTF-8''([^;]+)/i.exec(headers?.["content-disposition"] || "");
  return m ? decodeURIComponent(m[1]) : "file";
}

export function showBlob(blob, headers, win) {
  const type = (blob.type || "").split(";")[0].trim().toLowerCase();
  if (INLINE_SAFE_TYPES.includes(type)) {
    const url = URL.createObjectURL(blob);
    if (win) win.location.href = url;
    else window.open(url, "_blank", "noopener");
    setTimeout(() => URL.revokeObjectURL(url), 60000);
    return;
  }
  if (win) win.close();
  const url = URL.createObjectURL(new Blob([blob], { type: "application/octet-stream" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filenameFrom(headers);
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 60000);
}

// Buka file lewat header Authorization (token tidak ikut di URL, riwayat browser, atau log server).
// Jendela dibuka dulu secara sinkron supaya tidak diblokir popup blocker.
export async function openFile(id) {
  const win = window.open("", "_blank");
  try {
    const r = await api.get(`/files/${id}`, { responseType: "blob" });
    showBlob(r.data, r.headers, win);
  } catch (e) {
    if (win) win.close();
    let msg = errMsg(e);
    if (e?.response?.data instanceof Blob) {
      try { msg = JSON.parse(await e.response.data.text()).detail || msg; } catch (_) { /* bukan JSON */ }
    }
    toast.error(msg);
  }
}
