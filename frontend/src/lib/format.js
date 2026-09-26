export const rupiah = (n) => "Rp" + Number(n || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 });

export const fmtDate = (s) => {
  if (!s) return "-";
  const d = new Date(s.length === 10 ? s + "T00:00:00" : s);
  if (isNaN(d)) return s;
  return d.toLocaleDateString("id-ID", { day: "2-digit", month: "short", year: "numeric" });
};

export const fmtDateTime = (s) => {
  if (!s) return "-";
  const d = new Date(s);
  return d.toLocaleString("id-ID", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
};

export const today = () => new Date().toISOString().slice(0, 10);

export const STATUS_ORDER = ["calon_siswa", "pendaftaran", "seleksi", "diterima", "pelatihan", "ujian", "lulus", "matching", "pemberkasan", "visa", "berangkat", "alumni", "gagal"];

export const STATUS_LABELS = {
  calon_siswa: "Calon Siswa", pendaftaran: "Pendaftaran", seleksi: "Seleksi", diterima: "Diterima", pelatihan: "Pelatihan",
  ujian: "Ujian", lulus: "Lulus", matching: "Matching / Job Order", pemberkasan: "Pemberkasan", visa: "Visa / Dokumen",
  berangkat: "Berangkat", alumni: "Alumni", gagal: "Gagal",
};

export const STATUS_CLASSES = {
  calon_siswa: "bg-slate-100 text-slate-700 border-slate-200", pendaftaran: "bg-blue-50 text-blue-700 border-blue-200",
  seleksi: "bg-purple-50 text-purple-700 border-purple-200", diterima: "bg-teal-50 text-teal-700 border-teal-200",
  pelatihan: "bg-amber-50 text-amber-700 border-amber-200", ujian: "bg-orange-50 text-orange-700 border-orange-200",
  lulus: "bg-emerald-50 text-emerald-700 border-emerald-200", matching: "bg-indigo-50 text-indigo-700 border-indigo-200",
  pemberkasan: "bg-cyan-50 text-cyan-700 border-cyan-200", visa: "bg-violet-50 text-violet-700 border-violet-200",
  berangkat: "bg-rose-50 text-rose-700 border-rose-200", alumni: "bg-slate-900 text-white border-slate-900",
  gagal: "bg-red-50 text-red-700 border-red-200",
};

export const ROLE_LABELS = { owner: "Owner", admin: "Admin", finance: "Keuangan", hr: "HR", guru: "Guru", marketing: "Marketing", staff: "Staff", student: "Siswa" };

export const ATT_LABELS = { hadir: "Hadir", izin: "Izin", sakit: "Sakit", alfa: "Alfa" };

export const METODE = [["cash", "Cash"], ["transfer", "Transfer Bank"], ["qris", "QRIS"], ["ewallet", "E-Wallet"]];

export function downloadCSV(rows, filename) {
  if (!rows?.length) return;
  const cols = Object.keys(rows[0]);
  // Teks diawali = + - @ dianggap formula oleh Excel (formula injection); beri prefiks apostrof.
  const neutral = (v) => (typeof v === "string" && /^[=+\-@\t\r]/.test(v) ? `'${v}` : v);
  const esc = (v) => `"${String(neutral(v) ?? "").replace(/"/g, '""')}"`;
  const csv = [cols.join(","), ...rows.map((r) => cols.map((c) => esc(typeof r[c] === "object" ? JSON.stringify(r[c]) : r[c])).join(","))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" }));
  a.download = filename;
  a.click();
}
