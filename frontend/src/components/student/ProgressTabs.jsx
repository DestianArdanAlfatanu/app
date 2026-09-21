import { useState } from "react";
import { Link } from "react-router-dom";
import { Receipt, Plus, Settings2 } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { FormDialog, Field, EmptyState, Money } from "@/components/common";
import { PaymentDialog } from "@/components/PaymentDialog";
import { ReceiptDialog } from "@/components/ReceiptDialog";
import { fmtDate, rupiah, ATT_LABELS, METODE } from "@/lib/format";

export const PembayaranTab = ({ s, reload }) => {
  const { can } = useAuth();
  const [payOpen, setPayOpen] = useState(false);
  const [receipt, setReceipt] = useState(null);
  const [planOpen, setPlanOpen] = useState(false);
  const [plan, setPlan] = useState({ items: s.fee_plan, jatuh_tempo: s.jatuh_tempo || "" });
  const savePlan = async () => {
    try { await api.put(`/students/${s.id}/fee-plan`, { items: plan.items.filter((i) => i.nama), jatuh_tempo: plan.jatuh_tempo || null }); toast.success("Rincian biaya diperbarui"); setPlanOpen(false); reload(); }
    catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div className="grid lg:grid-cols-3 gap-4 fade-up">
      <div className="card card-pad">
        <div className="flex items-center justify-between mb-3"><h3 className="font-semibold">Rincian Biaya Program</h3>
          {can("pembayaran_write") && <button className="btn-ghost btn-sm" onClick={() => { setPlan({ items: s.fee_plan, jatuh_tempo: s.jatuh_tempo || "" }); setPlanOpen(true); }} data-testid="edit-fee-plan-btn"><Settings2 size={14} /></button>}</div>
        {s.fee_plan.map((i, k) => <div key={k} className="flex justify-between text-sm py-2 border-b border-slate-100"><span className="text-slate-600">{i.nama}</span><Money value={i.nominal} /></div>)}
        <div className="flex justify-between text-sm py-2 font-bold"><span>Total Tagihan</span><Money value={s.pembayaran.total} /></div>
        <div className="flex justify-between text-sm py-1 text-emerald-700"><span>Sudah Dibayar</span><Money value={s.pembayaran.bayar} /></div>
        <div className="flex justify-between text-sm py-1 text-red-600 font-semibold"><span>Sisa</span><Money value={s.pembayaran.sisa} /></div>
        {can("pembayaran_write") && <button className="btn-red w-full mt-4" onClick={() => setPayOpen(true)} data-testid="add-payment-btn"><Plus size={15} />Catat Pembayaran</button>}
      </div>
      <div className="lg:col-span-2 table-wrap"><table className="tbl" data-testid="student-payments-table"><thead><tr><th>Kwitansi</th><th>Tanggal</th><th>Jenis</th><th>Metode</th><th>Nominal</th><th>Petugas</th><th></th></tr></thead>
        <tbody>{s.payments.length === 0 && <tr><td colSpan={7}><EmptyState text="Belum ada pembayaran" /></td></tr>}
          {s.payments.map((p) => <tr key={p.id}><td className="mono text-xs">{p.no_kwitansi}</td><td>{fmtDate(p.tanggal)}</td><td>{p.jenis}</td><td className="capitalize">{p.metode}</td><td><Money value={p.nominal} className="font-semibold" /></td><td>{p.petugas}</td>
            <td><button className="btn-ghost btn-sm" onClick={() => setReceipt(p.id)} data-testid={`receipt-btn-${p.id}`}><Receipt size={14} />Kwitansi</button></td></tr>)}
        </tbody></table></div>
      <PaymentDialog open={payOpen} onOpenChange={setPayOpen} student={s} onSaved={(p) => { reload(); setReceipt(p.id); }} />
      <ReceiptDialog paymentId={receipt} onClose={() => setReceipt(null)} />
      <FormDialog open={planOpen} onOpenChange={setPlanOpen} title="Atur Rincian Biaya" onSubmit={savePlan} testId="fee-plan-dialog">
        {plan.items.map((i, k) => (
          <div key={k} className="grid grid-cols-[1fr_140px_32px] gap-2 items-end">
            <Field label={k === 0 ? "Komponen" : ""}><input className="input" value={i.nama} onChange={(e) => setPlan({ ...plan, items: plan.items.map((x, j) => j === k ? { ...x, nama: e.target.value } : x) })} /></Field>
            <Field label={k === 0 ? "Nominal" : ""}><input type="number" className="input" value={i.nominal} onChange={(e) => setPlan({ ...plan, items: plan.items.map((x, j) => j === k ? { ...x, nominal: Number(e.target.value) } : x) })} /></Field>
            <button type="button" className="btn-ghost h-10 px-0 text-red-600" onClick={() => setPlan({ ...plan, items: plan.items.filter((_, j) => j !== k) })}>×</button>
          </div>))}
        <button type="button" className="btn-outline btn-sm" onClick={() => setPlan({ ...plan, items: [...plan.items, { nama: "", nominal: 0 }] })}>+ Tambah komponen</button>
        <Field label="Jatuh Tempo Berikutnya"><input type="date" className="input" value={plan.jatuh_tempo} onChange={(e) => setPlan({ ...plan, jatuh_tempo: e.target.value })} /></Field>
        <p className="text-sm font-semibold">Total: {rupiah(plan.items.reduce((a, i) => a + Number(i.nominal || 0), 0))}</p>
      </FormDialog>
    </div>
  );
};

export const AkademikTab = ({ s }) => (
  <div className="grid lg:grid-cols-2 gap-4 fade-up">
    <div className="card card-pad">
      <h3 className="font-semibold mb-3">Rekap Absensi {s.kelas ? `· ${s.kelas.nama}` : ""}</h3>
      <div className="grid grid-cols-4 gap-2 mb-4">{["hadir", "izin", "sakit", "alfa"].map((k) => <div key={k} className="rounded-md bg-slate-50 p-3 text-center"><p className="mono text-xl font-semibold">{s.absensi[k]}</p><p className="text-[11px] uppercase tracking-wider text-slate-500">{ATT_LABELS[k]}</p></div>)}</div>
      <div className="max-h-64 overflow-y-auto">{s.attendance_rows.map((r) => <div key={r.id} className="flex justify-between text-sm py-1.5 border-b border-slate-50"><span>{fmtDate(r.tanggal)}</span><span className={`chip ${r.status === "hadir" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : r.status === "alfa" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>{ATT_LABELS[r.status]}</span></div>)}</div>
    </div>
    <div className="space-y-4">
      <div className="card card-pad"><h3 className="font-semibold mb-3">Nilai per Periode</h3>
        {s.grades.length === 0 && <p className="text-sm text-slate-400">Belum ada nilai.</p>}
        {s.grades.map((g) => (
          <div key={g.id} className="border border-slate-100 rounded-md p-3 mb-2"><div className="flex justify-between items-center mb-2"><span className="font-medium text-sm">{g.periode}</span><span className="mono font-bold text-lg">{g.nilai_akhir}</span></div>
            <div className="grid grid-cols-5 gap-1 text-[11px]">{Object.entries(g.komponen).map(([k, v]) => <div key={k} className="bg-slate-50 rounded px-1.5 py-1 text-center"><p className="capitalize text-slate-500 truncate">{k}</p><p className="mono font-semibold">{v}</p></div>)}</div></div>))}
      </div>
      <div className="card card-pad"><h3 className="font-semibold mb-3">Hasil Ujian</h3>
        {s.exam_results.length === 0 && <p className="text-sm text-slate-400">Belum ada ujian.</p>}
        {s.exam_results.map((e) => <div key={e.exam_id} className="flex justify-between items-center text-sm py-2 border-b border-slate-50"><div><p className="font-medium">{e.nama}</p><p className="text-xs text-slate-500">{e.jenis} · {fmtDate(e.tanggal)}</p></div>
          <span className={`mono font-bold ${e.nilai == null ? "text-slate-400" : e.nilai >= e.passing_grade ? "text-emerald-600" : "text-red-600"}`}>{e.nilai ?? "-"}</span></div>)}
      </div>
    </div>
  </div>
);

export const JepangTab = ({ s }) => (
  <div className="fade-up table-wrap"><table className="tbl" data-testid="student-interviews-table"><thead><tr><th>Tanggal</th><th>Perusahaan</th><th>Posisi</th><th>Hasil</th><th>Catatan</th></tr></thead>
    <tbody>{s.interviews.length === 0 && <tr><td colSpan={5}><EmptyState text="Belum ada job order / interview. Cocokkan siswa dari menu Job Order." /></td></tr>}
      {s.interviews.map((iv) => <tr key={iv.id}><td>{fmtDate(iv.tanggal)}</td><td className="font-medium">{iv.perusahaan}</td><td>{iv.posisi}</td>
        <td><span className={`chip ${iv.hasil === "lulus" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : iv.hasil === "gagal" ? "bg-red-50 text-red-700 border-red-200" : "bg-amber-50 text-amber-700 border-amber-200"}`}>{iv.hasil}</span></td><td>{iv.catatan || "-"}</td></tr>)}
    </tbody></table>
    <div className="p-3 text-xs text-slate-500">Lihat semua lowongan di <Link to="/job-order" className="text-red-600 font-semibold">Job Order Jepang</Link></div>
  </div>
);
