import { useState } from "react";
import { CheckCircle2, XCircle, Upload, Eye, Plus, Trash2, Clock, Check, X } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { useApi } from "@/hooks/useApi";
import { api, errMsg, openFile } from "@/lib/api";
import { FormDialog, Field, EmptyState, StatusBadge } from "@/components/common";
import { fmtDate, fmtDateTime } from "@/lib/format";

const Row = ({ l, v }) => <div className="flex justify-between gap-4 py-2 border-b border-slate-100 last:border-0 text-sm"><span className="text-slate-500">{l}</span><span className="font-medium text-slate-800 text-right">{v || "-"}</span></div>;

export const BiodataTab = ({ s }) => (
  <div className="grid lg:grid-cols-3 gap-4 fade-up">
    <div className="card card-pad"><h3 className="font-semibold mb-2">Data Pribadi</h3>
      <Row l="NIK" v={s.nik} /><Row l="No. KK" v={s.no_kk} /><Row l="TTL" v={`${s.tempat_lahir || "-"}, ${fmtDate(s.tanggal_lahir)}`} /><Row l="Jenis Kelamin" v={s.jenis_kelamin === "L" ? "Laki-laki" : "Perempuan"} />
      <Row l="Alamat" v={[s.alamat?.desa, s.alamat?.kecamatan, s.alamat?.kabupaten, s.alamat?.provinsi].filter(Boolean).join(", ")} /><Row l="No. HP" v={s.no_hp} /><Row l="Email" v={s.email} />
      <Row l="Orang Tua" v={s.nama_orang_tua} /><Row l="HP Orang Tua" v={s.no_hp_orang_tua} /></div>
    <div className="card card-pad"><h3 className="font-semibold mb-2">Pendidikan & Tambahan</h3>
      <Row l="Pendidikan" v={s.pendidikan_terakhir} /><Row l="Sekolah" v={s.nama_sekolah} /><Row l="Jurusan" v={s.jurusan} /><Row l="Tahun Lulus" v={s.tahun_lulus} />
      <Row l="Tinggi / Berat" v={`${s.tinggi_badan || "-"} cm / ${s.berat_badan || "-"} kg`} /><Row l="Status Nikah" v={s.status_pernikahan?.replace("_", " ")} /><Row l="Bahasa Jepang" v={s.kemampuan_bahasa_jepang} />
      <Row l="Riwayat Kerja" v={s.riwayat_pekerjaan} /><Row l="Riwayat Kesehatan" v={s.riwayat_kesehatan} /><Row l="Didaftarkan oleh" v={s.created_by} /></div>
    <div className="card card-pad"><h3 className="font-semibold mb-3">Histori Status</h3>
      <div className="space-y-3" data-testid="status-history">
        {[...(s.status_history || [])].reverse().map((h, i) => (
          <div key={i} className="flex gap-3"><span className="mt-1.5 h-2 w-2 rounded-full bg-red-600 shrink-0" />
            <div><StatusBadge status={h.status} /><p className="text-xs text-slate-500 mt-1">{fmtDateTime(h.tanggal)} · {h.oleh}{h.catatan ? ` · ${h.catatan}` : ""}</p></div></div>
        ))}
      </div></div>
  </div>
);

const SEL_TYPES = [["administrasi", "Seleksi Administrasi"], ["kesehatan", "Tes Kesehatan"], ["fisik", "Tes Fisik"], ["bahasa", "Tes Bahasa Jepang"], ["wawancara", "Wawancara"]];

export const SeleksiTab = ({ s, reload }) => {
  const { can } = useAuth();
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ jenis: "administrasi", hasil: "lulus", nilai: "", catatan: "", tanggal: "" });
  const save = async () => {
    try { await api.post(`/students/${s.id}/selections`, { ...f, nilai: f.nilai === "" ? null : Number(f.nilai), tanggal: f.tanggal || null }); toast.success("Hasil seleksi disimpan"); setOpen(false); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const latest = Object.fromEntries(SEL_TYPES.map(([k]) => [k, s.selections.find((x) => x.jenis === k)]));
  return (
    <div className="fade-up">
      <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3 mb-5">
        {SEL_TYPES.map(([k, l]) => { const r = latest[k]; return (
          <div key={k} className="card p-4" data-testid={`selection-card-${k}`}>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{l}</p>
            <div className="mt-2 flex items-center gap-2">{!r ? <span className="text-sm text-slate-400">Belum</span> : r.hasil === "lulus" ? <><CheckCircle2 size={18} className="text-emerald-600" /><span className="text-sm font-semibold text-emerald-700">Lulus</span></> : <><XCircle size={18} className="text-red-600" /><span className="text-sm font-semibold text-red-700">Tidak Lulus</span></>}</div>
            {r?.nilai != null && <p className="mono text-lg font-semibold mt-1">{r.nilai}</p>}
          </div>); })}
      </div>
      {can("siswa_write") && <button className="btn-primary mb-4" onClick={() => setOpen(true)} data-testid="add-selection-btn"><Plus size={15} />Catat Hasil Seleksi</button>}
      <div className="table-wrap"><table className="tbl" data-testid="selection-history-table"><thead><tr><th>Tanggal</th><th>Jenis</th><th>Hasil</th><th>Nilai</th><th>Catatan</th><th>Petugas</th></tr></thead>
        <tbody>{s.selections.length === 0 && <tr><td colSpan={6}><EmptyState text="Belum ada histori seleksi" /></td></tr>}
          {s.selections.map((r) => <tr key={r.id}><td>{fmtDate(r.tanggal)}</td><td className="capitalize">{r.jenis}</td><td><span className={`chip ${r.hasil === "lulus" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"}`}>{r.hasil === "lulus" ? "Lulus" : "Tidak Lulus"}</span></td><td className="mono">{r.nilai ?? "-"}</td><td>{r.catatan || "-"}</td><td>{r.petugas}</td></tr>)}
        </tbody></table></div>
      <FormDialog open={open} onOpenChange={setOpen} title="Catat Hasil Seleksi" onSubmit={save} testId="selection-dialog">
        <Field label="Jenis Seleksi"><select className="input" data-testid="selection-jenis-select" value={f.jenis} onChange={(e) => setF({ ...f, jenis: e.target.value })}>{SEL_TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Hasil"><select className="input" data-testid="selection-hasil-select" value={f.hasil} onChange={(e) => setF({ ...f, hasil: e.target.value })}><option value="lulus">Lulus</option><option value="tidak_lulus">Tidak Lulus</option></select></Field>
          <Field label="Nilai (opsional)"><input type="number" className="input" data-testid="selection-nilai-input" value={f.nilai} onChange={(e) => setF({ ...f, nilai: e.target.value })} /></Field>
        </div>
        <Field label="Tanggal"><input type="date" className="input" value={f.tanggal} onChange={(e) => setF({ ...f, tanggal: e.target.value })} /></Field>
        <Field label="Catatan"><textarea className="input" data-testid="selection-catatan-input" value={f.catatan} onChange={(e) => setF({ ...f, catatan: e.target.value })} /></Field>
      </FormDialog>
    </div>
  );
};

const KAT = { identitas: "Identitas", pendidikan: "Pendidikan", kesehatan: "Kesehatan", jepang: "Jepang", kontrak: "Kontrak", lainnya: "Lainnya" };

export const DokumenTab = ({ s, reload }) => {
  const { can } = useAuth();
  const { data: docs, reload: reloadDocs } = useApi(`/students/${s.id}/documents`);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ jenis: "", kategori: "identitas", tanggal_kadaluarsa: "", file: null });
  const [saving, setSaving] = useState(false);
  const today = new Date().toISOString().slice(0, 10);
  const soon = new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10);

  const openUpload = (d) => { setF({ jenis: d?.jenis || "", kategori: d?.kategori || "identitas", tanggal_kadaluarsa: d?.tanggal_kadaluarsa || "", file: null }); setOpen(true); };
  const save = async () => {
    setSaving(true);
    const fd = new FormData();
    fd.append("jenis", f.jenis); fd.append("kategori", f.kategori);
    if (f.tanggal_kadaluarsa) fd.append("tanggal_kadaluarsa", f.tanggal_kadaluarsa);
    if (f.file) fd.append("file", f.file);
    try { await api.post(`/students/${s.id}/documents`, fd); toast.success("Dokumen tersimpan — menunggu verifikasi"); setOpen(false); reloadDocs(); reload(); }
    catch (e) {
      console.error("Upload dokumen gagal:", e);
      const msg = errMsg(e);
      toast.error(/storage|penyimpanan|Upload gagal|502/i.test(msg)
        ? "Upload dokumen gagal karena penyimpanan file belum tersedia. Silakan coba lagi setelah konfigurasi penyimpanan diperbaiki."
        : msg);
    } finally { setSaving(false); }
  };
  const verify = async (d) => {
    try { await api.put(`/students/${s.id}/documents/${d.id}/verify`, { note: "" }); toast.success("Dokumen terverifikasi"); reloadDocs(); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const reject = async (d) => {
    const reason = window.prompt(`Alasan penolakan dokumen ${d.jenis}:`, "");
    if (reason === null) return;
    if (!reason.trim()) { toast.error("Alasan penolakan wajib diisi"); return; }
    try { await api.put(`/students/${s.id}/documents/${d.id}/reject`, { reason: reason.trim() }); toast.success("Dokumen ditolak"); reloadDocs(); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  const unset = async (d) => {
    if (!window.confirm(`Tandai ${d.jenis} sebagai belum tersedia?`)) return;
    try { await api.put(`/students/${s.id}/documents/status`, { jenis: d.jenis, kategori: d.kategori, status: "belum" }); reloadDocs(); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const groups = (docs || []).reduce((a, d) => ({ ...a, [d.kategori]: [...(a[d.kategori] || []), d] }), {});
  const doneCount = (list) => list.filter((d) => d.status === "tersedia" || d.status === "verified").length;
  const statusChip = (d) => {
    if (d.status === "verified") return <span className="chip bg-emerald-50 text-emerald-700 border-emerald-200">Terverifikasi</span>;
    if (d.status === "pending_verification") return <span className="chip bg-amber-50 text-amber-700 border-amber-200">Menunggu verifikasi</span>;
    if (d.status === "rejected") return <span className="chip bg-red-50 text-red-700 border-red-200">Ditolak</span>;
    if (d.status === "tersedia") return <span className="chip bg-slate-100 text-slate-600 border-slate-200">Tersedia</span>;
    return null;
  };
  return (
    <div className="fade-up">
      {can("siswa_write") && <button className="btn-primary mb-4" onClick={() => openUpload(null)} data-testid="upload-document-btn"><Upload size={15} />Upload Dokumen</button>}
      <div className="grid md:grid-cols-2 gap-4">
        {Object.entries(groups).map(([k, list]) => (
          <div key={k} className="card"><div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between"><h3 className="font-semibold text-sm">{KAT[k] || k}</h3><span className="text-xs text-slate-500">{doneCount(list)}/{list.length} lengkap</span></div>
            <ul>{list.map((d) => (
              <li key={d.jenis} data-testid={`doc-item-${d.jenis.replace(/\s+/g, "-").toLowerCase()}`} className="flex items-center gap-3 px-5 py-3 border-b border-slate-50 last:border-0">
                {d.status === "tersedia" || d.status === "verified" ? <CheckCircle2 size={18} className="text-emerald-600 shrink-0" /> : d.status === "rejected" ? <XCircle size={18} className="text-red-500 shrink-0" /> : d.status === "pending_verification" ? <Clock size={18} className="text-amber-500 shrink-0" /> : <XCircle size={18} className="text-slate-300 shrink-0" />}
                <div className="flex-1 min-w-0"><p className="text-sm font-medium text-slate-800">{d.jenis} {statusChip(d)}</p>
                  <p className="text-xs text-slate-500 truncate">{d.status === "belum" ? "Belum tersedia" : `Upload ${fmtDate(d.tanggal_upload)} · ${d.uploaded_by}${d.original_filename ? ` · ${d.original_filename}` : ""}`}
                    {!d.file_id && d.status !== "belum" ? " · File belum tersedia" : ""}
                    {d.status === "verified" && d.verified_by ? ` · Diverifikasi ${d.verified_by}` : ""}
                    {d.status === "rejected" && d.rejected_reason ? ` · Alasan: ${d.rejected_reason}` : ""}
                    {d.tanggal_kadaluarsa && <span className={`ml-2 font-semibold ${d.tanggal_kadaluarsa < today ? "text-red-600" : d.tanggal_kadaluarsa <= soon ? "text-amber-600" : "text-slate-400"}`}>{d.tanggal_kadaluarsa < today ? "Expired" : "Exp"} {fmtDate(d.tanggal_kadaluarsa)}</span>}</p></div>
                {d.file_id && <a href="#" onClick={(e) => { e.preventDefault(); openFile(d.file_id); }} className="btn-ghost btn-sm" title="Lihat / unduh file" data-testid={`doc-view-${d.jenis.replace(/\s+/g, "-").toLowerCase()}`}><Eye size={14} /></a>}
                {can("siswa_write") && d.status === "pending_verification" && <button className="btn-ghost btn-sm text-emerald-700" title="Verifikasi dokumen" onClick={() => verify(d)} data-testid={`doc-verify-${d.jenis.replace(/\s+/g, "-").toLowerCase()}`}><Check size={14} /></button>}
                {can("siswa_write") && d.status === "pending_verification" && <button className="btn-ghost btn-sm text-red-600" title="Tolak dokumen" onClick={() => reject(d)} data-testid={`doc-reject-${d.jenis.replace(/\s+/g, "-").toLowerCase()}`}><X size={14} /></button>}
                {can("siswa_write") && <button className="btn-ghost btn-sm" onClick={() => openUpload(d)} data-testid={`doc-upload-${d.jenis.replace(/\s+/g, "-").toLowerCase()}`}><Upload size={14} /></button>}
                {can("siswa_write") && d.status === "tersedia" && <button className="btn-ghost btn-sm text-red-600" onClick={() => unset(d)}><Trash2 size={14} /></button>}
              </li>))}</ul></div>
        ))}
      </div>
      <FormDialog open={open} onOpenChange={setOpen} title="Upload Dokumen Siswa" description="File disimpan di object storage dan terkait langsung dengan profil siswa." onSubmit={save} loading={saving} testId="upload-document-dialog" submitLabel={saving ? "Mengunggah..." : "Simpan"}>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Jenis Dokumen"><input className="input" data-testid="doc-jenis-input" value={f.jenis} onChange={(e) => setF({ ...f, jenis: e.target.value })} placeholder="mis. KTP, Paspor" required /></Field>
          <Field label="Kategori"><select className="input" data-testid="doc-kategori-select" value={f.kategori} onChange={(e) => setF({ ...f, kategori: e.target.value })}>{Object.entries(KAT).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        </div>
        <Field label="Tanggal Kadaluarsa (opsional)"><input type="date" className="input" data-testid="doc-expiry-input" value={f.tanggal_kadaluarsa} onChange={(e) => setF({ ...f, tanggal_kadaluarsa: e.target.value })} /></Field>
        <Field label="File (PDF/JPG/PNG, maks 10MB)" hint="Kosongkan jika hanya ingin menandai dokumen sudah tersedia (fisik)."><input type="file" className="input py-1.5" data-testid="doc-file-input" accept=".pdf,.jpg,.jpeg,.png,.webp" onChange={(e) => setF({ ...f, file: e.target.files?.[0] || null })} /></Field>
      </FormDialog>
    </div>
  );
};
