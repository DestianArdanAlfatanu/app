import { useState } from "react";
import { Download, Printer, FileSpreadsheet, FileText } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Tabs, Loading, Money, EmptyState } from "@/components/common";
import { downloadCSV, rupiah, STATUS_LABELS, fmtDate } from "@/lib/format";

export default function ReportsPage() {
  const { user } = useAuth();
  const all = [{ key: "siswa", label: "Laporan Siswa", roles: ["owner", "admin", "marketing", "hr", "finance"] }, { key: "keuangan", label: "Laporan Keuangan", roles: ["owner", "admin", "finance"] },
    { key: "sdm", label: "Laporan SDM", roles: ["owner", "admin", "hr"] }, { key: "pelatihan", label: "Laporan Pelatihan", roles: ["owner", "admin", "guru", "hr"] }];
  const tabs = all.filter((t) => t.roles.includes(user.role));
  const [tab, setTab] = useState(tabs[0]?.key);
  const [range, setRange] = useState({ dari: new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10), sampai: new Date().toISOString().slice(0, 10) });
  const [page, setPage] = useState(1);
  const limit = 200;
  const path = { siswa: `/reports/students?page=${page}&limit=${limit}`, keuangan: `/reports/finance?dari=${range.dari}&sampai=${range.sampai}`, sdm: "/reports/hr", pelatihan: `/reports/training?page=${page}&limit=${limit}` }[tab];
  const { data, loading, setData } = useApi(path, [tab, range.dari, range.sampai, page]);
  const changeTab = (t) => { if (t !== tab) { setData(null); setTab(t); setPage(1); } };
  const totalPages = data?.total ? Math.max(1, Math.ceil(data.total / (data.limit || limit))) : 1;

  const exportRows = () => {
    if (!data) return;
    const rows = tab === "pelatihan" ? data.rows.map(({ ujian, ...r }) => ({ ...r, ujian: ujian.map((u) => `${u.nama}:${u.nilai ?? "-"}`).join("; ") })) : tab === "sdm" ? data.rows.map(({ kelas, sertifikat, ...r }) => ({ ...r, sertifikat: (sertifikat || []).join("; ") })) : data.rows;
    downloadCSV(rows, `laporan-${tab}-${new Date().toISOString().slice(0, 10)}.csv`);
  };

  const exportFile = async (format) => {
    try {
      const params = new URLSearchParams({ format });
      if (tab === "keuangan") { params.set("dari", range.dari); params.set("sampai", range.sampai); }
      const r = await api.get(`/reports/${tab}/export?${params.toString()}`, { responseType: "blob" });
      const url = URL.createObjectURL(new Blob([r.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = `laporan-${tab}-${new Date().toISOString().slice(0, 10)}.${format === "xlsx" ? "xlsx" : "pdf"}`;
      a.click();
      URL.revokeObjectURL(url);
      toast.success(`File ${format.toUpperCase()} berhasil diunduh.`);
    } catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div>
      <PageHeader title="Laporan" jp="レポート" subtitle="Laporan otomatis dari data yang sama — Excel, PDF, CSV, atau cetak.">
        <button className="btn-outline" onClick={() => window.print()} data-testid="print-report-btn"><Printer size={16} />Cetak</button>
        <button className="btn-outline" onClick={exportRows} data-testid="csv-report-btn"><Download size={16} />CSV</button>
        <button className="btn-outline" onClick={() => exportFile("pdf")} data-testid="pdf-report-btn"><FileText size={16} />Ekspor PDF</button>
        <button className="btn-primary" onClick={() => exportFile("xlsx")} data-testid="export-report-btn"><FileSpreadsheet size={16} />Ekspor Excel (.xlsx)</button>
      </PageHeader>
      <div className="no-print"><Tabs active={tab} onChange={changeTab} testPrefix="report-tab" tabs={tabs} /></div>
      {tab === "keuangan" && <div className="flex gap-2 mb-4 no-print"><input type="date" className="input w-44" data-testid="report-dari-input" value={range.dari} onChange={(e) => setRange({ ...range, dari: e.target.value })} /><input type="date" className="input w-44" data-testid="report-sampai-input" value={range.sampai} onChange={(e) => setRange({ ...range, sampai: e.target.value })} /></div>}
      {(tab === "siswa" || tab === "pelatihan") && (data?.total || 0) > limit && (
        <div className="flex items-center gap-2 mb-4 no-print text-sm">
          <button className="btn-outline btn-sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)} data-testid="report-prev-btn">‹ Sebelumnya</button>
          <span className="text-slate-500">Halaman {data.page || page} dari {totalPages} · {data.total} baris</span>
          <button className="btn-outline btn-sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)} data-testid="report-next-btn">Berikutnya ›</button>
        </div>
      )}
      {loading && !data ? <Loading /> : !data ? null : (
        <div className="print-area fade-up" data-testid={`report-${tab}`}>
          {tab === "siswa" && (<>
            <div className="flex gap-2 flex-wrap mb-4">{Object.entries(data.per_status).map(([k, v]) => <span key={k} className="chip bg-white">{STATUS_LABELS[k]}: <b className="ml-1">{v}</b></span>)}<span className="chip bg-slate-900 text-white border-slate-900">Total: {data.rows.length}</span></div>
            <div className="table-wrap"><table className="tbl"><thead><tr><th>Nama</th><th>JK/Usia</th><th>Status</th><th>Kelas</th><th>Bahasa</th><th>Tagihan</th><th>Dibayar</th><th>Sisa</th><th>Hadir</th><th>Nilai</th><th>Dok</th></tr></thead>
              <tbody>{data.rows.map((r, i) => <tr key={i}><td className="font-medium">{r.nama}</td><td>{r.jenis_kelamin}/{r.usia ?? "-"}</td><td>{STATUS_LABELS[r.status]}</td><td>{r.kelas || "-"}</td><td>{r.bahasa}</td><td><Money value={r.total_tagihan} /></td><td><Money value={r.dibayar} /></td><td><Money value={r.sisa} className={r.sisa > 0 ? "text-red-600" : "text-emerald-600"} /></td><td>{r.kehadiran}%</td><td>{r.nilai ?? "-"}</td><td>{r.dokumen}/13</td></tr>)}</tbody></table></div>
          </>)}
          {tab === "keuangan" && (<>
            <div className="grid grid-cols-3 gap-3 mb-4">
              <div className="card p-4"><p className="label">Pemasukan</p><p className="mono text-xl font-semibold text-emerald-700">{rupiah(data.pemasukan)}</p></div>
              <div className="card p-4"><p className="label">Pengeluaran</p><p className="mono text-xl font-semibold text-red-600">{rupiah(data.pengeluaran)}</p></div>
              <div className="card p-4"><p className="label">Laba / Rugi</p><p className={`mono text-xl font-semibold ${data.laba >= 0 ? "text-emerald-700" : "text-red-600"}`}>{rupiah(data.laba)}</p></div>
            </div>
            <div className="grid md:grid-cols-2 gap-4 mb-4">
              <div className="card p-4"><h3 className="font-semibold mb-2">Per Kategori</h3>{data.per_kategori.map((k, i) => <div key={i} className="flex justify-between text-sm py-1 border-b border-slate-50"><span>{k.jenis === "pemasukan" ? "+" : "−"} {k.kategori}</span><Money value={k.nominal} className={k.jenis === "pemasukan" ? "text-emerald-700" : "text-red-600"} /></div>)}</div>
              <div className="card p-4"><h3 className="font-semibold mb-2">Saldo Rekening Saat Ini</h3>{data.accounts.map((a) => <div key={a.id} className="flex justify-between text-sm py-1 border-b border-slate-50"><span>{a.nama}</span><Money value={a.saldo} /></div>)}<div className="flex justify-between text-sm py-1 font-bold"><span>Total</span><Money value={data.accounts.reduce((x, a) => x + a.saldo, 0)} /></div></div>
            </div>
            <div className="table-wrap"><table className="tbl"><thead><tr><th>Tanggal</th><th>Jenis</th><th>Kategori</th><th>Deskripsi</th><th>Rekening</th><th>Nominal</th><th>Petugas</th></tr></thead>
              <tbody>{data.rows.length === 0 && <tr><td colSpan={7}><EmptyState /></td></tr>}{data.rows.map((r) => <tr key={r.id}><td>{fmtDate(r.tanggal)}</td><td>{r.jenis}</td><td>{r.kategori}</td><td>{r.deskripsi}</td><td>{r.account_nama}</td><td><Money value={r.nominal} className={r.jenis === "pemasukan" ? "text-emerald-700" : "text-red-600"} /></td><td>{r.petugas}</td></tr>)}</tbody></table></div>
          </>)}
          {tab === "sdm" && (<>
            <p className="text-sm mb-3">Total gaji pokok + tunjangan bulanan (aktif): <b className="mono">{rupiah(data.total_gaji)}</b></p>
            <div className="table-wrap"><table className="tbl"><thead><tr><th>Nama</th><th>Tipe</th><th>Jabatan</th><th>Status</th><th>Masuk</th><th>Gaji Pokok</th><th>Tunjangan</th><th>Honor/Pertemuan</th><th>Kelas</th><th>Kontrak</th></tr></thead>
              <tbody>{data.rows.map((e) => <tr key={e.id}><td className="font-medium">{e.nama}</td><td>{e.tipe}</td><td>{e.jabatan}</td><td>{e.status_kerja}{!e.aktif && " (nonaktif)"}</td><td>{fmtDate(e.tanggal_masuk)}</td><td><Money value={e.gaji_pokok} /></td><td><Money value={e.tunjangan} /></td><td><Money value={e.honor_per_pertemuan} /></td><td>{e.jumlah_kelas}</td><td>{e.kontrak_berakhir ? fmtDate(e.kontrak_berakhir) : "-"}</td></tr>)}</tbody></table></div>
          </>)}
          {tab === "pelatihan" && (
            <div className="table-wrap"><table className="tbl"><thead><tr><th>Nama</th><th>Kelas</th><th>Status</th><th>Hadir</th><th>Izin</th><th>Sakit</th><th>Alfa</th><th>%</th><th>Nilai</th><th>Ujian</th></tr></thead>
              <tbody>{data.rows.length === 0 && <tr><td colSpan={10}><EmptyState /></td></tr>}{data.rows.map((r, i) => <tr key={i}><td className="font-medium">{r.nama}</td><td>{r.kelas}</td><td>{STATUS_LABELS[r.status]}</td><td>{r.hadir}</td><td>{r.izin}</td><td>{r.sakit}</td><td>{r.alfa}</td><td className={r.persentase >= 80 ? "text-emerald-700 font-semibold" : "text-red-600 font-semibold"}>{r.persentase}%</td><td className="mono">{r.nilai ?? "-"}</td><td className="text-xs">{r.ujian.map((u) => `${u.nama}: ${u.nilai ?? "-"}`).join(" · ") || "-"}</td></tr>)}</tbody></table></div>
          )}
        </div>
      )}
    </div>
  );
}
