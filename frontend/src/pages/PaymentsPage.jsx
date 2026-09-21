import { useMemo, useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { Plus, Receipt, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, StatCard, Loading, Tabs, EmptyState, Money, FormDialog, Field } from "@/components/common";
import { PaymentDialog } from "@/components/PaymentDialog";
import { ReceiptDialog } from "@/components/ReceiptDialog";
import { rupiah, fmtDate, METODE, STATUS_LABELS } from "@/lib/format";

const KONDISI = { terlambat: ["Terlambat", "bg-red-50 text-red-700 border-red-200"], hari_ini: ["Jatuh tempo hari ini", "bg-amber-50 text-amber-700 border-amber-200"], akan_jatuh_tempo: ["Akan jatuh tempo", "bg-blue-50 text-blue-700 border-blue-200"], belum_jatuh_tempo: ["Belum ada tanggal", "bg-slate-50 text-slate-600 border-slate-200"] };

export default function PaymentsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || "riwayat";
  const { can } = useAuth();
  const [filter, setFilter] = useState("");
  const { data: payments, loading, reload } = useApi("/payments");
  const { data: arrears, reload: reloadArrears } = useApi(`/payments-arrears${filter ? `?filter=${filter}` : ""}`);
  const { data: students } = useApi("/students");
  const [open, setOpen] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [edit, setEdit] = useState(null);
  const [q, setQ] = useState("");

  const rows = useMemo(() => (payments || []).filter((p) => !q || p.student_nama.toLowerCase().includes(q.toLowerCase()) || p.no_kwitansi.includes(q)), [payments, q]);
  const totalHariIni = (payments || []).filter((p) => p.tanggal === new Date().toISOString().slice(0, 10)).reduce((a, p) => a + p.nominal, 0);
  const totalTunggakan = (arrears || []).reduce((a, s) => a + s.sisa, 0);

  const saveEdit = async () => {
    if (!edit.alasan) return toast.error("Alasan perubahan wajib diisi (audit)");
    try { await api.put(`/payments/${edit.id}`, { ...edit, nominal: Number(edit.nominal) }); toast.success("Pembayaran diperbarui & tercatat di audit"); setEdit(null); reload(); reloadArrears(); }
    catch (e) { toast.error(errMsg(e)); }
  };

  return (
    <div>
      <PageHeader title="Pembayaran Siswa" jp="学費管理" subtitle="Cicilan, kwitansi otomatis, dan pengingat tunggakan.">
        {can("pembayaran_write") && <button className="btn-red" onClick={() => setOpen(true)} data-testid="record-payment-btn"><Plus size={16} />Catat Pembayaran</button>}
      </PageHeader>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard testId="stat-pembayaran-hari-ini" label="Pembayaran Hari Ini" value={rupiah(totalHariIni)} tone="green" />
        <StatCard testId="stat-total-transaksi" label="Total Transaksi" value={payments?.length ?? "-"} />
        <StatCard testId="stat-siswa-tunggakan" label="Siswa Menunggak" value={arrears?.length ?? "-"} tone="red" onClick={() => setParams({ tab: "tunggakan" })} />
        <StatCard testId="stat-total-tunggakan" label="Total Piutang" value={rupiah(totalTunggakan)} tone="amber" />
      </div>
      <Tabs active={tab} onChange={(t) => setParams({ tab: t })} testPrefix="payments-tab" tabs={[{ key: "riwayat", label: "Riwayat Pembayaran" }, { key: "tunggakan", label: "Tunggakan & Pengingat", count: arrears?.length }]} />

      {tab === "riwayat" && (<>
        <input className="input max-w-sm mb-4" placeholder="Cari nama / no kwitansi..." value={q} onChange={(e) => setQ(e.target.value)} data-testid="payments-search-input" />
        {loading && !payments ? <Loading /> : (
          <div className="table-wrap fade-up"><table className="tbl" data-testid="payments-table"><thead><tr><th>Kwitansi</th><th>Tanggal</th><th>Siswa</th><th>Jenis</th><th>Metode</th><th>Rekening</th><th>Nominal</th><th>Petugas</th><th></th></tr></thead>
            <tbody>{rows.length === 0 && <tr><td colSpan={9}><EmptyState /></td></tr>}
              {rows.map((p) => <tr key={p.id} data-testid={`payment-row-${p.id}`}><td className="mono text-xs">{p.no_kwitansi}</td><td>{fmtDate(p.tanggal)}</td><td><Link to={`/siswa/${p.student_id}`} className="font-medium hover:text-red-600">{p.student_nama}</Link></td><td>{p.jenis}</td><td className="capitalize">{p.metode}</td><td>{p.account_nama}</td><td><Money value={p.nominal} className="font-semibold" /></td><td className="text-xs">{p.petugas}</td>
                <td className="whitespace-nowrap"><button className="btn-ghost btn-sm" onClick={() => setReceipt(p.id)} data-testid={`receipt-btn-${p.id}`}><Receipt size={14} /></button>{can("pembayaran_write") && <button className="btn-ghost btn-sm" onClick={() => setEdit({ ...p, alasan: "" })} data-testid={`edit-payment-${p.id}`}><Pencil size={14} /></button>}</td></tr>)}
            </tbody></table></div>)}
      </>)}

      {tab === "tunggakan" && (<>
        <div className="flex gap-1.5 mb-4 flex-wrap" data-testid="arrears-filter">
          {[["", "Semua"], ["terlambat", "Terlambat"], ["hari_ini", "Jatuh tempo hari ini"], ["akan_jatuh_tempo", "Akan jatuh tempo"]].map(([k, l]) => <button key={k} onClick={() => setFilter(k)} data-testid={`arrears-filter-${k || "all"}`} className={`chip cursor-pointer ${filter === k ? "bg-slate-900 text-white border-slate-900" : "bg-white text-slate-600"}`}>{l}</button>)}
        </div>
        <div className="table-wrap fade-up"><table className="tbl" data-testid="arrears-table"><thead><tr><th>Siswa</th><th>Status</th><th>Total</th><th>Dibayar</th><th>Sisa</th><th>Jatuh Tempo</th><th>Kondisi</th><th>Pembayaran Terakhir</th><th>Kontak</th></tr></thead>
          <tbody>{(arrears || []).length === 0 && <tr><td colSpan={9}><EmptyState text="Tidak ada tunggakan" /></td></tr>}
            {(arrears || []).map((s) => <tr key={s.id}><td><Link to={`/siswa/${s.id}`} className="font-medium hover:text-red-600">{s.nama_lengkap}</Link></td><td className="text-xs">{STATUS_LABELS[s.status]}</td><td><Money value={s.total} /></td><td><Money value={s.bayar} className="text-emerald-700" /></td><td><Money value={s.sisa} className="text-red-600 font-semibold" /></td><td>{fmtDate(s.jatuh_tempo)}</td>
              <td><span className={`chip ${KONDISI[s.kondisi][1]}`}>{KONDISI[s.kondisi][0]}</span></td><td>{fmtDate(s.terakhir)}</td><td className="text-xs">{s.no_hp}</td></tr>)}
          </tbody></table></div>
      </>)}

      <PaymentDialog open={open} onOpenChange={setOpen} students={students || []} onSaved={(p) => { reload(); reloadArrears(); setReceipt(p.id); }} />
      <ReceiptDialog paymentId={receipt} onClose={() => setReceipt(null)} />
      {edit && <FormDialog open={!!edit} onOpenChange={() => setEdit(null)} title={`Koreksi Pembayaran ${edit.no_kwitansi}`} description="Setiap koreksi menyimpan data sebelum & sesudah di audit trail." onSubmit={saveEdit} testId="edit-payment-dialog">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Nominal"><input type="number" className="input mono" data-testid="edit-payment-nominal" value={edit.nominal} onChange={(e) => setEdit({ ...edit, nominal: e.target.value })} /></Field>
          <Field label="Tanggal"><input type="date" className="input" value={edit.tanggal} onChange={(e) => setEdit({ ...edit, tanggal: e.target.value })} /></Field>
          <Field label="Metode"><select className="input" value={edit.metode} onChange={(e) => setEdit({ ...edit, metode: e.target.value })}>{METODE.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          <Field label="No. Transaksi"><input className="input" value={edit.no_transaksi || ""} onChange={(e) => setEdit({ ...edit, no_transaksi: e.target.value })} /></Field>
        </div>
        <Field label="Alasan Koreksi *"><textarea className="input" data-testid="edit-payment-alasan" value={edit.alasan} onChange={(e) => setEdit({ ...edit, alasan: e.target.value })} placeholder="mis. Koreksi nominal transfer" required /></Field>
      </FormDialog>}
    </div>
  );
}
