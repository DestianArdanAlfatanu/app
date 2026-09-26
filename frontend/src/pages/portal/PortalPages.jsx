import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Loading, Money, EmptyState, Field } from "@/components/common";
import { rupiah, STATUS_LABELS, fmtDate } from "@/lib/format";

function Row({ l, v }) {
  if (v === undefined || v === null || v === "") return null;
  return <div className="flex justify-between text-sm py-1.5 border-b border-slate-50 last:border-0"><span className="text-slate-500">{l}</span><span className="font-medium text-right">{v}</span></div>;
}

export function PortalProfile() {
  const { data: s, loading } = useApi("/student/profile");
  if (loading && !s) return <Loading />;
  if (!s) return <EmptyState />;
  return (
    <div>
      <PageHeader title={s.nama_lengkap} subtitle={`${STATUS_LABELS[s.status] || s.status || ""}${s.kelas_nama ? ` · ${s.kelas_nama}` : ""}`} />
      <div className="card card-pad">
        <Row l="NIK" v={s.nik} />
        <Row l="Tempat, Tanggal Lahir" v={[s.tempat_lahir, s.tanggal_lahir ? fmtDate(s.tanggal_lahir) : ""].filter(Boolean).join(", ")} />
        <Row l="Jenis Kelamin" v={s.jenis_kelamin === "L" ? "Laki-laki" : s.jenis_kelamin === "P" ? "Perempuan" : s.jenis_kelamin} />
        <Row l="Alamat" v={[s.alamat?.desa, s.alamat?.kecamatan, s.alamat?.kabupaten, s.alamat?.provinsi].filter(Boolean).join(", ")} />
        <Row l="No. HP" v={s.no_hp} />
        <Row l="Email" v={s.email} />
        <Row l="Nama Orang Tua" v={s.nama_orang_tua} />
        <Row l="No. HP Orang Tua" v={s.no_hp_orang_tua} />
        <Row l="Pendidikan" v={[s.pendidikan_terakhir, s.nama_sekolah, s.jurusan].filter(Boolean).join(" · ")} />
        <h3 className="font-semibold text-sm mt-4 mb-1">Riwayat Status</h3>
        {(s.status_history || []).length === 0 && <p className="text-xs text-slate-400">-</p>}
        {(s.status_history || []).map((h, i) => <p key={i} className="text-xs py-1 border-b border-slate-50 last:border-0">{STATUS_LABELS[h.status] || h.status} · {h.tanggal ? fmtDate(h.tanggal) : "-"} {h.catatan ? `· ${h.catatan}` : ""}</p>)}
      </div>
    </div>
  );
}

export function PortalAcademic() {
  const { data: cls, loading: l1 } = useApi("/student/class");
  const { data: att, loading: l2 } = useApi("/student/attendance");
  const { data: gr, loading: l3 } = useApi("/student/grades");
  const { data: ex, loading: l4 } = useApi("/student/exams");
  if ((l1 || l2 || l3 || l4) && !cls) return <Loading />;
  const r = att?.recap || {};
  return (
    <div className="space-y-3">
      <PageHeader title="Akademik" subtitle="Kelas, kehadiran, dan nilai Anda" />
      <div className="card card-pad">
        <h3 className="font-semibold text-sm mb-1">Kelas & Jadwal</h3>
        {!cls?.kelas ? <p className="text-xs text-slate-400">Belum masuk kelas.</p> : (<>
          <p className="text-sm font-semibold">{cls.kelas.nama}</p>
          <p className="text-xs text-slate-500">{cls.kelas.guru ? `Guru: ${cls.kelas.guru}` : ""} {cls.kelas.ruangan ? `· ${cls.kelas.ruangan}` : ""} {cls.kelas.level ? `· ${cls.kelas.level}` : ""}</p>
          {(cls.jadwal || []).map((j, i) => <p key={i} className="text-xs py-1 border-b border-slate-50 last:border-0">{j.hari} · {j.jam_mulai}–{j.jam_selesai} {j.materi ? `· ${j.materi}` : ""}</p>)}
        </>)}
      </div>
      <div className="card card-pad">
        <h3 className="font-semibold text-sm mb-1">Kehadiran ({r.persentase ?? "-"}%)</h3>
        <p className="text-xs text-slate-500 mb-2">Hadir {r.hadir || 0} · Terlambat {r.terlambat || 0} · Izin {r.izin || 0} · Sakit {r.sakit || 0} · Cuti {r.cuti || 0} · Alfa {r.alfa || 0}</p>
        <div className="table-wrap"><table className="tbl"><thead><tr><th>Tanggal</th><th>Status</th><th>Masuk</th><th>Pulang</th><th>Ket</th></tr></thead>
          <tbody>{(att?.rows || []).length === 0 && <tr><td colSpan={5}><EmptyState text="Belum ada data kehadiran" /></td></tr>}
            {(att?.rows || []).map((a, i) => <tr key={i}><td>{fmtDate(a.tanggal)}</td><td>{a.status}</td><td>{a.jam_masuk || "-"}</td><td>{a.jam_pulang || "-"}</td><td className="text-xs">{a.keterangan || "-"}</td></tr>)}
          </tbody></table></div>
      </div>
      <div className="card card-pad">
        <h3 className="font-semibold text-sm mb-1">Nilai</h3>
        {(gr?.rows || []).length === 0 && <p className="text-xs text-slate-400">Belum ada nilai.</p>}
        {(gr?.rows || []).map((g, i) => <div key={i} className="text-xs py-1.5 border-b border-slate-50 last:border-0"><p className="font-semibold">{g.periode} · <span className="mono">{g.nilai_akhir}</span></p>{g.catatan && <p className="text-slate-500">{g.catatan}</p>}</div>)}
        <h3 className="font-semibold text-sm mt-3 mb-1">Ujian</h3>
        {(ex?.rows || []).length === 0 && <p className="text-xs text-slate-400">Belum ada ujian.</p>}
        {(ex?.rows || []).map((e, i) => <p key={i} className="text-xs py-1 border-b border-slate-50 last:border-0">{e.nama} · {fmtDate(e.tanggal)} · <b className="mono">{e.nilai ?? "-"}</b> {e.nilai != null && <span className={e.lulus ? "text-emerald-600" : "text-red-600"}>({e.lulus ? "Lulus" : "Belum lulus"})</span>}</p>)}
      </div>
    </div>
  );
}

export function PortalFinance() {
  const { data, loading } = useApi("/student/payments");
  if (loading && !data) return <Loading />;
  if (!data) return <EmptyState />;
  return (
    <div>
      <PageHeader title="Keuangan" subtitle="Tagihan & riwayat pembayaran Anda" />
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-3">
        <div className="card p-4"><p className="label">Total Tagihan</p><p className="mono font-semibold">{rupiah(data.total)}</p></div>
        <div className="card p-4"><p className="label">Sudah Dibayar</p><p className="mono font-semibold text-emerald-700">{rupiah(data.bayar)}</p></div>
        <div className="card p-4"><p className="label">Sisa</p><p className={`mono font-semibold ${data.sisa > 0 ? "text-red-600" : "text-emerald-600"}`}>{rupiah(data.sisa)}</p>{data.jatuh_tempo && <p className="text-[11px] text-slate-400">Jatuh tempo {fmtDate(data.jatuh_tempo)}</p>}</div>
      </div>
      <div className="card card-pad">
        <h3 className="font-semibold text-sm mb-2">Riwayat Pembayaran</h3>
        <div className="table-wrap"><table className="tbl"><thead><tr><th>Tanggal</th><th>Jenis</th><th>Nominal</th><th>Metode</th><th>Kwitansi</th></tr></thead>
          <tbody>{data.rows.length === 0 && <tr><td colSpan={5}><EmptyState text="Belum ada pembayaran" /></td></tr>}
            {data.rows.map((p) => <tr key={p.id}><td>{fmtDate(p.tanggal)}</td><td>{p.jenis}</td><td><Money value={p.nominal} /></td><td>{p.metode}</td><td className="mono text-xs">{p.no_kwitansi || "-"}</td></tr>)}
          </tbody></table></div>
        <h3 className="font-semibold text-sm mt-3 mb-1">Rincian Tagihan</h3>
        {(data.fee_plan || []).map((f, i) => <div key={i} className="flex justify-between text-xs py-1 border-b border-slate-50 last:border-0"><span>{f.nama}</span><Money value={f.nominal} /></div>)}
      </div>
    </div>
  );
}

const DOC_STATUS_LABEL = {
  belum: ["Belum Ada", "Menunggu dokumen", "bg-slate-100 text-slate-600"],
  pending_verification: ["Menunggu Verifikasi", "Sedang diperiksa staf", "bg-amber-50 text-amber-700 border-amber-200"],
  verified: ["Terverifikasi", "Dokumen sudah diverifikasi", "bg-emerald-50 text-emerald-700 border-emerald-200"],
  rejected: ["Ditolak", "Dokumen perlu diperbaiki", "bg-red-50 text-red-700 border-red-200"],
  tersedia: ["Tersedia", "Dokumen tersedia", "bg-emerald-50 text-emerald-700 border-emerald-200"],
};

export function PortalDocuments() {
  const { data, loading, reload } = useApi("/student/documents");
  const [busy, setBusy] = useState(null);
  const openPreview = async (d) => {
    try {
      const r = await api.get(`/student/documents/${d.id}/download`, { responseType: "blob" });
      // r.data sudah Blob dengan type dari response Content-Type; JANGAN bungkus
      // new Blob() tanpa type karena browser kehilangan MIME dan menampilkan raw text.
      const blob = r.data instanceof Blob
        ? r.data
        : new Blob([r.data], { type: r.headers?.["content-type"] || "application/octet-stream" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener");
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e) { toast.error("Gagal membuka dokumen"); }
  };
  const upload = async (d, f) => {
    if (!f) return;
    setBusy(d.jenis);
    try {
      const fd = new FormData();
      fd.append("jenis", d.jenis);
      fd.append("file", f);
      await api.post("/student/documents", fd);
      toast.success("Dokumen berhasil diupload dan menunggu verifikasi.");
      reload();
    } catch (e) { toast.error(errMsg(e)); }
    finally { setBusy(null); }
  };
  if (loading && !data) return <Loading />;
  return (
    <div>
      <PageHeader title="Dokumen" subtitle="Upload, pantau status verifikasi, dan lihat alasan penolakan" />
      <div className="space-y-2">
        {(data?.rows || []).map((d, i) => {
          const [label, hint, chip] = DOC_STATUS_LABEL[d.status] || [d.status, "", "bg-slate-100"];
          const canUpload = d.status === "belum" || d.status === "rejected";
          return (
            <div key={i} className="card card-pad" data-testid={`portal-doc-${d.jenis.replace(/\s+/g, "-").toLowerCase()}`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-semibold">{d.jenis}</p>
                  <p className="text-[11px] text-slate-400">{d.kategori}{d.tanggal_upload ? ` · Upload ${fmtDate(d.tanggal_upload)}` : ""}</p>
                </div>
                <span className={`chip ${chip}`} title={hint}>{label}</span>
              </div>
              {d.status === "rejected" && d.rejected_reason && (
                <p className="text-xs mt-2 p-2 rounded bg-red-50 text-red-700">Alasan penolakan: {d.rejected_reason}</p>
              )}
              {d.has_file && d.id && (
                <p className="text-[11px] text-slate-400 mt-1">{d.original_filename || "File tersedia"}</p>
              )}
              {d.status !== "belum" && !d.has_file && (
                <p className="text-[11px] text-slate-400 mt-1">File belum tersedia</p>
              )}
              <div className="flex gap-2 mt-2">
                {d.has_file && d.id && <button className="btn-ghost btn-sm" onClick={() => openPreview(d)}>Lihat Dokumen</button>}
                {canUpload && (
                  <label className={`btn-outline btn-sm cursor-pointer ${busy === d.jenis ? "opacity-50" : ""}`}>
                    {busy === d.jenis ? "Mengupload..." : (d.status === "rejected" ? "Upload Ulang" : "Upload Dokumen")}
                    <input type="file" className="hidden" accept=".pdf,.jpg,.jpeg,.png,.webp" disabled={busy === d.jenis}
                      onChange={(e) => { upload(d, e.target.files[0]); e.target.value = ""; }} />
                  </label>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function PortalNotifications() {
  const { data, loading, reload } = useApi("/student/notifications");
  const mark = async (id) => { try { await api.post(`/student/notifications/${id}/read`); reload(); } catch (_) { /* ignore */ } };
  const all = async () => { try { await api.post("/student/notifications/read-all"); reload(); } catch (_) { /* ignore */ } };
  if (loading && !data) return <Loading />;
  return (
    <div>
      <PageHeader title="Notifikasi" subtitle={`${data?.unread || 0} belum dibaca`}>
        {(data?.unread || 0) > 0 && <button className="btn-outline btn-sm" onClick={all}>Tandai semua dibaca</button>}
      </PageHeader>
      {(data?.rows || []).length === 0 && <div className="card"><EmptyState text="Belum ada notifikasi" /></div>}
      {(data?.rows || []).map((n) => (
        <button key={n.id} onClick={() => mark(n.id)} className={`card w-full text-left p-3 mb-2 ${n.read ? "opacity-60" : ""}`}>
          <p className="text-sm font-semibold">{n.judul}</p>
          <p className="text-xs text-slate-500">{n.pesan}</p>
          <p className="text-[11px] text-slate-400 mt-1">{fmtDate(n.tanggal)}</p>
        </button>
      ))}
    </div>
  );
}

export function PortalSettings() {
  const nav = useNavigate();
  const { data: me } = useApi("/student/auth/me");
  const { data: consent, loading, reload } = useApi("/student/whatsapp-consent");
  const [pw, setPw] = useState({ old_password: "", new_password: "" });
  const [saving, setSaving] = useState(false);
  const savePw = async () => {
    setSaving(true);
    try {
      await api.post("/student/auth/change-password", pw);
      toast.success("Password berhasil diganti");
      setPw({ old_password: "", new_password: "" });
      if (me?.must_change_password) nav("/portal");
    }
    catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const saveConsent = async (v) => {
    try { await api.put("/student/whatsapp-consent", { wa_student_opt_in: v }); toast.success("Preferensi WhatsApp tersimpan"); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  if (loading && !consent) return <Loading />;
  return (
    <div className="space-y-3">
      <PageHeader title="Pengaturan" subtitle={me?.email} />
      {me?.must_change_password && <div className="card card-pad border-amber-300 bg-amber-50 text-sm">Akun baru wajib mengganti password awal terlebih dahulu.</div>}
      <div className="card card-pad">
        <h3 className="font-semibold text-sm mb-2">Ganti Password</h3>
        <Field label="Password lama"><input type="password" className="input" data-testid="portal-old-pw" value={pw.old_password} onChange={(e) => setPw({ ...pw, old_password: e.target.value })} /></Field>
        <Field label="Password baru (min 6 karakter)"><input type="password" className="input" data-testid="portal-new-pw" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} /></Field>
        <button className="btn-primary mt-2" onClick={savePw} disabled={saving} data-testid="portal-save-pw">Simpan Password</button>
      </div>
      <div className="card card-pad">
        <h3 className="font-semibold text-sm mb-1">Notifikasi WhatsApp</h3>
        <p className="text-xs text-slate-500 mb-2">Nomor: {consent?.wa_student_phone || "-"} · Wali: {consent?.wa_guardian_opt_in ? "aktif" : "nonaktif"} (read-only)</p>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" data-testid="portal-wa-toggle" checked={!!consent?.wa_student_opt_in} onChange={(e) => saveConsent(e.target.checked)} /> Kirim notifikasi ke WhatsApp saya</label>
      </div>
    </div>
  );
}
