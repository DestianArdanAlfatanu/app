import { useEffect, useState } from "react";
import { Plus, Pencil, Scale, Landmark } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, fileUrl } from "@/lib/api";
import { PageHeader, StatCard, Tabs, FormDialog, Field, EmptyState, Money, Loading } from "@/components/common";
import { rupiah, fmtDate, fmtDateTime, today, METODE } from "@/lib/format";

const EMPTY_TX = { jenis: "pengeluaran", kategori: "", nominal: "", tanggal: today(), deskripsi: "", account_id: "", metode: "transfer", bukti: null, alasan: "" };

export default function FinancePage() {
  const { can } = useAuth();
  const [tab, setTab] = useState("transaksi");
  const [period, setPeriod] = useState("bulan");
  const [filter, setFilter] = useState({ jenis: "", account_id: "" });
  const { data: sum, reload: reloadSum } = useApi(`/finance/summary?period=${period}`);
  const { data: cats } = useApi("/finance/categories");
  const qs = Object.entries(filter).filter(([, v]) => v).map(([k, v]) => `${k}=${v}`).join("&");
  const { data: txs, loading, reload } = useApi(`/finance/transactions${qs ? `?${qs}` : ""}`);
  const { data: recons, reload: reloadRecon } = useApi("/finance/reconciliations");
  const [txOpen, setTxOpen] = useState(false);
  const [tx, setTx] = useState(EMPTY_TX);
  const [editTx, setEditTx] = useState(null);
  const [accOpen, setAccOpen] = useState(false);
  const [acc, setAcc] = useState({ nama: "", jenis: "bank", bank: "", no_rekening: "", saldo_awal: 0 });
  const [recOpen, setRecOpen] = useState(false);
  const [rec, setRec] = useState({ account_id: "", tanggal: today(), saldo_aktual: "", alasan: "" });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (sum?.accounts?.length && !tx.account_id) setTx((x) => ({ ...x, account_id: sum.accounts[0].id })); }, [sum, tx.account_id]);
  const refresh = () => { reload(); reloadSum(); reloadRecon(); };

  const saveTx = async () => {
    setSaving(true);
    try {
      let bukti_file_id = editTx?.bukti_file_id || null;
      if (tx.bukti) { const fd = new FormData(); fd.append("file", tx.bukti); bukti_file_id = (await api.post("/upload", fd)).data.id; }
      const body = { ...tx, nominal: Number(tx.nominal), bukti_file_id, bukti: undefined, kategori: tx.kategori || (cats?.[tx.jenis]?.[0] ?? "Lainnya") };
      editTx ? await api.put(`/finance/transactions/${editTx.id}`, body) : await api.post("/finance/transactions", body);
      toast.success(editTx ? "Transaksi dikoreksi & tercatat di audit" : "Transaksi tersimpan, saldo otomatis diperbarui"); setTxOpen(false); setEditTx(null); refresh();
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const saveAcc = async () => { try { await api.post("/finance/accounts", { ...acc, saldo_awal: Number(acc.saldo_awal) }); toast.success("Rekening ditambahkan"); setAccOpen(false); refresh(); } catch (e) { toast.error(errMsg(e)); } };
  const saveRec = async () => { try { const { data } = await api.post("/finance/reconciliations", { ...rec, saldo_aktual: Number(rec.saldo_aktual) }); toast.success(`Rekonsiliasi tersimpan, selisih ${rupiah(data.selisih)}`); setRecOpen(false); refresh(); } catch (e) { toast.error(errMsg(e)); } };
  const selAcc = sum?.accounts?.find((a) => a.id === rec.account_id);

  return (
    <div>
      <PageHeader title="Kas & Keuangan" jp="財務" subtitle="Pemasukan, pengeluaran, saldo per rekening, dan rekonsiliasi — dihitung otomatis.">
        <div className="flex rounded-md border border-slate-200 bg-white p-1">{[["hari", "Hari"], ["minggu", "Minggu"], ["bulan", "Bulan"], ["tahun", "Tahun"]].map(([k, l]) => <button key={k} data-testid={`finance-period-${k}`} onClick={() => setPeriod(k)} className={`px-3 h-8 rounded text-xs font-semibold ${period === k ? "bg-slate-900 text-white" : "text-slate-600"}`}>{l}</button>)}</div>
        {can("keuangan_write") && <button className="btn-red" onClick={() => { setEditTx(null); setTx({ ...EMPTY_TX, account_id: sum?.accounts?.[0]?.id || "" }); setTxOpen(true); }} data-testid="add-transaction-btn"><Plus size={16} />Catat Transaksi</button>}
      </PageHeader>
      {!sum ? <Loading /> : (<>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <StatCard testId="fin-pemasukan" label="Pemasukan" value={rupiah(sum.pemasukan)} tone="green" hint={`${fmtDate(sum.dari)} – ${fmtDate(sum.sampai)}`} />
          <StatCard testId="fin-pengeluaran" label="Pengeluaran" value={rupiah(sum.pengeluaran)} tone="red" hint={sum.pengeluaran_per_kategori[0] ? `Terbesar: ${sum.pengeluaran_per_kategori[0].kategori}` : ""} />
          <StatCard testId="fin-laba" label="Laba / Rugi Operasional" value={rupiah(sum.laba)} tone={sum.laba >= 0 ? "green" : "red"} />
          <StatCard testId="fin-piutang" label="Piutang Siswa" value={rupiah(sum.piutang)} tone="amber" hint={`Pembayaran hari ini ${rupiah(sum.pembayaran_hari_ini)}`} />
        </div>
        <div className="card p-4 mb-6 fade-up">
          <div className="flex items-center justify-between mb-3"><h3 className="font-semibold flex items-center gap-2"><Landmark size={16} />Saldo Kas & Rekening <span className="mono text-red-600">{rupiah(sum.saldo_kas)}</span></h3>
            {can("keuangan_write") && <button className="btn-outline btn-sm" onClick={() => setAccOpen(true)} data-testid="add-account-btn"><Plus size={13} />Rekening</button>}</div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3">{sum.accounts.map((a) => <div key={a.id} className="border border-slate-200 rounded-md p-3" data-testid={`account-card-${a.id}`}><p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{a.nama}</p><p className="mono text-xl font-semibold mt-1">{rupiah(a.saldo)}</p><p className="text-[11px] text-slate-400">{a.bank ? `${a.bank} · ${a.no_rekening}` : "Kas tunai"} · awal {rupiah(a.saldo_awal)}</p></div>)}</div>
        </div>
      </>)}

      <Tabs active={tab} onChange={setTab} testPrefix="finance-tab" tabs={[{ key: "transaksi", label: "Transaksi", count: txs?.length }, { key: "kategori", label: "Per Kategori" }, { key: "rekonsiliasi", label: "Rekonsiliasi", count: recons?.length }]} />

      {tab === "transaksi" && (<>
        <div className="flex flex-wrap gap-2 mb-4">
          <select className="input w-44" data-testid="filter-jenis-select" value={filter.jenis} onChange={(e) => setFilter({ ...filter, jenis: e.target.value })}><option value="">Semua jenis</option><option value="pemasukan">Pemasukan</option><option value="pengeluaran">Pengeluaran</option></select>
          <select className="input w-52" data-testid="filter-account-select" value={filter.account_id} onChange={(e) => setFilter({ ...filter, account_id: e.target.value })}><option value="">Semua rekening</option>{(sum?.accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama}</option>)}</select>
        </div>
        {loading && !txs ? <Loading /> : (
          <div className="table-wrap fade-up"><table className="tbl" data-testid="transactions-table"><thead><tr><th>Tanggal</th><th>Jenis</th><th>Kategori</th><th>Deskripsi</th><th>Rekening</th><th>Metode</th><th>Nominal</th><th>Petugas</th><th></th></tr></thead>
            <tbody>{(txs || []).length === 0 && <tr><td colSpan={9}><EmptyState /></td></tr>}
              {(txs || []).map((t) => <tr key={t.id} data-testid={`tx-row-${t.id}`}><td>{fmtDate(t.tanggal)}</td><td><span className={`chip ${t.jenis === "pemasukan" ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-red-50 text-red-700 border-red-200"}`}>{t.jenis}</span></td><td>{t.kategori}</td><td className="max-w-xs truncate">{t.deskripsi}{t.bukti_file_id && <a href={fileUrl(t.bukti_file_id)} target="_blank" rel="noreferrer" className="ml-2 text-xs text-red-600 font-semibold">bukti</a>}</td><td>{t.account_nama}</td><td className="capitalize">{t.metode}</td>
                <td><Money value={t.nominal} className={`font-semibold ${t.jenis === "pemasukan" ? "text-emerald-700" : "text-red-600"}`} /></td><td className="text-xs">{t.petugas}</td>
                <td>{can("keuangan_write") && (t.ref_type === "manual" || !t.ref_type) && <button className="btn-ghost btn-sm" onClick={() => { setEditTx(t); setTx({ ...EMPTY_TX, ...t, bukti: null, alasan: "" }); setTxOpen(true); }} data-testid={`edit-tx-${t.id}`}><Pencil size={13} /></button>}</td></tr>)}
            </tbody></table></div>)}
      </>)}

      {tab === "kategori" && sum && (
        <div className="grid md:grid-cols-2 gap-4">
          <div className="card card-pad"><h3 className="font-semibold mb-3">Pengeluaran per Kategori ({period})</h3>
            {sum.pengeluaran_per_kategori.length === 0 && <p className="text-sm text-slate-400">Belum ada pengeluaran.</p>}
            {sum.pengeluaran_per_kategori.map((k) => <div key={k.kategori} className="mb-2"><div className="flex justify-between text-sm"><span>{k.kategori}</span><Money value={k.nominal} /></div><div className="h-1.5 bg-slate-100 rounded-full"><div className="h-full bg-red-600 rounded-full" style={{ width: `${(k.nominal / sum.pengeluaran) * 100}%` }} /></div></div>)}
          </div>
          <div className="card card-pad"><h3 className="font-semibold mb-3">Ringkasan Kas</h3>
            <div className="text-sm space-y-2"><div className="flex justify-between"><span className="text-slate-500">Saldo awal (semua rekening)</span><Money value={sum.accounts.reduce((a, x) => a + x.saldo_awal, 0)} /></div><div className="flex justify-between text-emerald-700"><span>+ Total pemasukan</span><Money value={sum.accounts.reduce((a, x) => a + x.pemasukan, 0)} /></div><div className="flex justify-between text-red-600"><span>− Total pengeluaran</span><Money value={sum.accounts.reduce((a, x) => a + x.pengeluaran, 0)} /></div><div className="flex justify-between font-bold border-t pt-2"><span>Saldo akhir</span><Money value={sum.saldo_kas} /></div></div>
          </div>
        </div>
      )}

      {tab === "rekonsiliasi" && (<>
        {can("keuangan_write") && <button className="btn-primary mb-4" onClick={() => { setRec({ account_id: sum?.accounts?.[0]?.id || "", tanggal: today(), saldo_aktual: "", alasan: "" }); setRecOpen(true); }} data-testid="add-recon-btn"><Scale size={15} />Rekonsiliasi Baru</button>}
        <div className="table-wrap fade-up"><table className="tbl" data-testid="recon-table"><thead><tr><th>Tanggal</th><th>Rekening</th><th>Saldo Sistem</th><th>Saldo Aktual</th><th>Selisih</th><th>Alasan</th><th>Petugas</th></tr></thead>
          <tbody>{(recons || []).length === 0 && <tr><td colSpan={7}><EmptyState text="Belum ada rekonsiliasi" /></td></tr>}
            {(recons || []).map((r) => <tr key={r.id}><td>{fmtDate(r.tanggal)}</td><td>{r.account_nama}</td><td><Money value={r.saldo_sistem} /></td><td><Money value={r.saldo_aktual} /></td><td><Money value={r.selisih} className={`font-semibold ${r.selisih === 0 ? "text-emerald-600" : "text-red-600"}`} /></td><td>{r.alasan || "-"}</td><td className="text-xs">{r.petugas} · {fmtDateTime(r.created_at)}</td></tr>)}
          </tbody></table></div>
      </>)}

      <FormDialog open={txOpen} onOpenChange={(o) => { setTxOpen(o); if (!o) setEditTx(null); }} title={editTx ? "Koreksi Transaksi" : "Catat Transaksi"} onSubmit={saveTx} loading={saving} testId="transaction-dialog">
        <div className="grid grid-cols-2 gap-3">
          <Field label="Jenis"><select className="input" data-testid="tx-jenis-select" value={tx.jenis} onChange={(e) => setTx({ ...tx, jenis: e.target.value, kategori: "" })}><option value="pengeluaran">Pengeluaran</option><option value="pemasukan">Pemasukan</option></select></Field>
          <Field label="Kategori"><select className="input" data-testid="tx-kategori-select" value={tx.kategori} onChange={(e) => setTx({ ...tx, kategori: e.target.value })}>{(cats?.[tx.jenis] || []).map((c) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Nominal (Rp)"><input type="number" min="1" className="input mono" data-testid="tx-nominal-input" value={tx.nominal} onChange={(e) => setTx({ ...tx, nominal: e.target.value })} required /></Field>
          <Field label="Tanggal"><input type="date" className="input" data-testid="tx-tanggal-input" value={tx.tanggal} onChange={(e) => setTx({ ...tx, tanggal: e.target.value })} /></Field>
          <Field label="Sumber Dana / Rekening"><select className="input" data-testid="tx-account-select" value={tx.account_id} onChange={(e) => setTx({ ...tx, account_id: e.target.value })}>{(sum?.accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama}</option>)}</select></Field>
          <Field label="Metode"><select className="input" value={tx.metode} onChange={(e) => setTx({ ...tx, metode: e.target.value })}>{METODE.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        </div>
        <Field label="Deskripsi"><input className="input" data-testid="tx-deskripsi-input" value={tx.deskripsi} onChange={(e) => setTx({ ...tx, deskripsi: e.target.value })} placeholder="mis. Pembelian ATK" /></Field>
        <Field label="Bukti Transaksi (opsional)"><input type="file" className="input py-1.5" data-testid="tx-bukti-input" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setTx({ ...tx, bukti: e.target.files?.[0] || null })} /></Field>
        {editTx && <Field label="Alasan Koreksi *"><textarea className="input" data-testid="tx-alasan-input" value={tx.alasan} onChange={(e) => setTx({ ...tx, alasan: e.target.value })} required /></Field>}
      </FormDialog>

      <FormDialog open={accOpen} onOpenChange={setAccOpen} title="Tambah Rekening / Kas" onSubmit={saveAcc} testId="account-dialog">
        <Field label="Nama"><input className="input" data-testid="acc-nama-input" value={acc.nama} onChange={(e) => setAcc({ ...acc, nama: e.target.value })} required /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Jenis"><select className="input" value={acc.jenis} onChange={(e) => setAcc({ ...acc, jenis: e.target.value })}><option value="bank">Bank</option><option value="kas">Kas Tunai</option></select></Field>
          <Field label="Saldo Awal"><input type="number" className="input mono" data-testid="acc-saldo-input" value={acc.saldo_awal} onChange={(e) => setAcc({ ...acc, saldo_awal: e.target.value })} /></Field>
          <Field label="Bank"><input className="input" value={acc.bank} onChange={(e) => setAcc({ ...acc, bank: e.target.value })} /></Field>
          <Field label="No. Rekening"><input className="input" value={acc.no_rekening} onChange={(e) => setAcc({ ...acc, no_rekening: e.target.value })} /></Field>
        </div>
      </FormDialog>

      <FormDialog open={recOpen} onOpenChange={setRecOpen} title="Rekonsiliasi Saldo" description="Bandingkan saldo sistem dengan saldo fisik/rekening bank. Selisih wajib diberi alasan." onSubmit={saveRec} testId="recon-dialog">
        <Field label="Rekening"><select className="input" data-testid="recon-account-select" value={rec.account_id} onChange={(e) => setRec({ ...rec, account_id: e.target.value })}>{(sum?.accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama}</option>)}</select></Field>
        {selAcc && <div className="rounded-md bg-slate-50 border p-3 text-sm flex justify-between"><span>Saldo menurut sistem</span><Money value={selAcc.saldo} className="font-semibold" /></div>}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Tanggal"><input type="date" className="input" value={rec.tanggal} onChange={(e) => setRec({ ...rec, tanggal: e.target.value })} /></Field>
          <Field label="Saldo Aktual"><input type="number" className="input mono" data-testid="recon-saldo-input" value={rec.saldo_aktual} onChange={(e) => setRec({ ...rec, saldo_aktual: e.target.value })} required /></Field>
        </div>
        {selAcc && rec.saldo_aktual !== "" && <p className={`text-sm font-semibold ${Number(rec.saldo_aktual) - selAcc.saldo === 0 ? "text-emerald-600" : "text-red-600"}`} data-testid="recon-selisih">Selisih: {rupiah(Number(rec.saldo_aktual) - selAcc.saldo)}</p>}
        <Field label="Alasan Selisih"><textarea className="input" data-testid="recon-alasan-input" value={rec.alasan} onChange={(e) => setRec({ ...rec, alasan: e.target.value })} placeholder="Pengeluaran belum dicatat / kesalahan pencatatan" /></Field>
      </FormDialog>
    </div>
  );
}
