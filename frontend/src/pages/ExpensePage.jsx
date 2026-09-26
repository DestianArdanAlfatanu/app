import { useState } from "react";
import { Plus, Check, X, Wallet, Pencil } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg, openFile } from "@/lib/api";
import { PageHeader, FormDialog, Field, EmptyState, Money, Loading } from "@/components/common";
import { rupiah, fmtDate, fmtDateTime, today } from "@/lib/format";

const STATUS_CHIP = {
  draft: "bg-slate-100 text-slate-700 border-slate-200",
  diajukan: "bg-amber-50 text-amber-700 border-amber-200",
  disetujui: "bg-emerald-50 text-emerald-700 border-emerald-200",
  ditolak: "bg-red-50 text-red-700 border-red-200",
  dibayar: "bg-blue-50 text-blue-700 border-blue-200",
  dibatalkan: "bg-slate-100 text-slate-400 border-slate-200",
};
const STATUS_LABEL = { draft: "Draft", diajukan: "Diajukan", disetujui: "Disetujui", ditolak: "Ditolak", dibayar: "Dibayar", dibatalkan: "Dibatalkan" };

const EMPTY = { judul: "", kategori: "", nominal: "", tanggal: today(), deskripsi: "", account_id: "", bukti: null };

export default function ExpensePage() {
  const { can } = useAuth();
  const writable = can("expense_write");
  const approver = can("expense_approve");
  const payer = can("expense_pay");
  const canSeeAccounts = can("keuangan");
  const [fStatus, setFStatus] = useState("");

  const qs = `/expenses${fStatus ? `?status=${fStatus}` : ""}`;
  const { data, loading, reload } = useApi(qs, [qs]);
  const rows = data || [];
  const { data: cats } = useApi("/finance/categories", [], writable);
  const { data: accounts } = useApi("/finance/accounts", [], canSeeAccounts);

  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [detail, setDetail] = useState(null);
  const [rejectId, setRejectId] = useState(null);
  const [rejectReason, setRejectReason] = useState("");
  const [payId, setPayId] = useState(null);
  const [payAcc, setPayAcc] = useState("");

  const openCreate = () => {
    setEditId(null);
    setForm({ ...EMPTY, tanggal: today(), kategori: cats?.pengeluaran?.[0] || "", account_id: (accounts || [])[0]?.id || "" });
    setOpen(true);
  };
  const openEdit = (e) => {
    setEditId(e.id);
    setForm({ judul: e.judul, kategori: e.kategori, nominal: e.nominal, tanggal: e.tanggal, deskripsi: e.deskripsi || "", account_id: e.account_id || "", bukti: null, alasan: "" });
    setOpen(true);
  };
  const save = async () => {
    setSaving(true);
    try {
      let bukti_file_id = editId ? undefined : null;
      if (form.bukti) { const fd = new FormData(); fd.append("file", form.bukti); bukti_file_id = (await api.post("/upload", fd)).data.id; }
      const body = { judul: form.judul, kategori: form.kategori, nominal: Number(form.nominal), tanggal: form.tanggal, deskripsi: form.deskripsi, account_id: form.account_id || "", bukti_file_id: bukti_file_id ?? undefined };
      if (editId) {
        if (!form.alasan?.trim()) { toast.error("Alasan perubahan wajib diisi."); setSaving(false); return; }
        await api.put(`/expenses/${editId}`, { ...body, alasan: form.alasan });
        toast.success("Pengajuan dikoreksi.");
      } else {
        await api.post("/expenses", body);
        toast.success("Pengajuan tersimpan sebagai draft.");
      }
      setOpen(false); reload(); if (detail) setDetail((await api.get(`/expenses/${detail.id}`)).data);
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  const act = async (id, action, body) => {
    try {
      const { data: r } = await api.post(`/expenses/${id}/${action}`, body || {});
      toast.success({ submit: "Pengajuan diteruskan ke approval.", cancel: "Draft dibatalkan.", approve: "Pengajuan disetujui.", pay: "Pengajuan dibayar, transaksi tercatat." }[action] || "Berhasil.");
      reload(); if (detail) setDetail(r);
      return r;
    } catch (e) { toast.error(errMsg(e)); }
  };
  const reject = async () => {
    if (!rejectReason.trim()) { toast.error("Alasan penolakan wajib diisi."); return; }
    const r = await act(rejectId, "decide", { setuju: false, alasan: rejectReason });
    if (r) { setRejectId(null); setRejectReason(""); }
  };
  const pay = async () => {
    if (!payAcc) { toast.error("Pilih rekening pembayaran."); return; }
    const r = await act(payId, "pay", { account_id: payAcc });
    if (r) { setPayId(null); if (!r.already_paid) toast.success("Tercatat tepat 1 transaksi."); }
  };
  const openDetail = async (id) => { try { setDetail((await api.get(`/expenses/${id}`)).data); } catch (e) { toast.error(errMsg(e)); } };
  const canActOn = (e) => e.status === "diajukan";

  return (
    <div>
      <PageHeader title="Pengajuan Biaya" jp="経費申請" subtitle="Draft tidak masuk ledger. Transaksi dibuat tepat sekali saat Paid.">
        {writable && <button className="btn-red" onClick={openCreate} data-testid="add-expense-btn"><Plus size={16} />Buat Pengajuan</button>}
      </PageHeader>
      <div className="card p-4 mb-4 grid sm:grid-cols-[200px_auto] gap-3 items-end">
        <Field label="Status">
          <select className="input" data-testid="expense-filter-status" value={fStatus} onChange={(e) => setFStatus(e.target.value)}>
            <option value="">Semua</option>{Object.keys(STATUS_LABEL).map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </select>
        </Field>
      </div>
      {loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="expenses-table">
          <thead><tr><th>No. Ref</th><th>Judul</th><th>Kategori</th><th>Nominal</th><th>Tanggal</th><th>Pemohon</th><th>Status</th><th></th></tr></thead>
          <tbody>
            {rows.length === 0 && <tr><td colSpan={8}><EmptyState text="Belum ada pengajuan" /></td></tr>}
            {rows.map((e) => (
              <tr key={e.id} data-testid={`expense-row-${e.id}`}>
                <td className="text-xs mono">{e.no_ref}</td>
                <td><button className="font-semibold text-left hover:underline" onClick={() => openDetail(e.id)}>{e.judul}</button>
                  <p className="text-xs text-slate-400 max-w-[240px] truncate">{e.deskripsi}</p></td>
                <td>{e.kategori}</td>
                <td><Money value={e.nominal} /></td>
                <td className="whitespace-nowrap">{fmtDate(e.tanggal)}</td>
                <td className="text-xs">{e.created_by}</td>
                <td><span className={`chip ${STATUS_CHIP[e.status]}`}>{STATUS_LABEL[e.status]}</span></td>
                <td className="whitespace-nowrap">
                  {writable && e.status === "draft" && <button className="btn-ghost btn-sm" title="Ubah" onClick={() => openEdit(e)} data-testid={`edit-expense-${e.id}`}><Pencil size={13} /></button>}
                  {approver && canActOn(e) && (<>
                    <button className="btn-ghost btn-sm text-emerald-700" title="Setujui" onClick={() => { if (window.confirm(`Setujui ${e.judul} (${rupiah(e.nominal)})?`)) act(e.id, "decide", { setuju: true }); }} data-testid={`approve-expense-${e.id}`}><Check size={15} /></button>
                    <button className="btn-ghost btn-sm text-red-600" title="Tolak" onClick={() => { setRejectId(e.id); setRejectReason(""); }} data-testid={`reject-expense-${e.id}`}><X size={15} /></button>
                  </>)}
                  {payer && e.status === "disetujui" && <button className="btn-ghost btn-sm text-blue-700" title="Bayar" onClick={async () => { await openDetail(e.id); setPayAcc(e.account_id || ""); setPayId(e.id); }} data-testid={`pay-expense-${e.id}`}><Wallet size={15} /></button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table></div>
      )}

      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Koreksi Pengajuan" : "Pengajuan Biaya Baru"} description="Tersimpan sebagai draft, belum masuk ledger." onSubmit={save} loading={saving} testId="expense-dialog" wide>
        <Field label="Judul"><input className="input" data-testid="expense-judul-input" value={form.judul} onChange={(e) => setForm({ ...form, judul: e.target.value })} required /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Kategori"><select className="input" data-testid="expense-kategori-select" value={form.kategori} onChange={(e) => setForm({ ...form, kategori: e.target.value })}>{(cats?.pengeluaran || []).map((c) => <option key={c}>{c}</option>)}</select></Field>
          <Field label="Nominal (Rp)"><input type="number" min="1" className="input mono" data-testid="expense-nominal-input" value={form.nominal} onChange={(e) => setForm({ ...form, nominal: e.target.value })} required /></Field>
          <Field label="Tanggal"><input type="date" className="input" data-testid="expense-tanggal-input" value={form.tanggal} onChange={(e) => setForm({ ...form, tanggal: e.target.value })} required /></Field>
          <Field label="Rekening (opsional, ditetapkan saat bayar)"><select className="input" data-testid="expense-account-select" value={form.account_id} onChange={(e) => setForm({ ...form, account_id: e.target.value })}><option value="">— Belum ditentukan —</option>{(accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama}</option>)}</select></Field>
        </div>
        <Field label="Deskripsi"><input className="input" data-testid="expense-deskripsi-input" value={form.deskripsi} onChange={(e) => setForm({ ...form, deskripsi: e.target.value })} /></Field>
        <Field label="Bukti (opsional)"><input type="file" className="input py-1.5" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setForm({ ...form, bukti: e.target.files?.[0] || null })} /></Field>
        {editId && <Field label="Alasan perubahan (wajib)"><input className="input" data-testid="expense-alasan-input" value={form.alasan || ""} onChange={(e) => setForm({ ...form, alasan: e.target.value })} required /></Field>}
      </FormDialog>

      <FormDialog open={!!detail} onOpenChange={(v) => { if (!v) setDetail(null); }} title={detail ? `${detail.judul} · ${detail.no_ref}` : ""} testId="expense-detail-dialog" wide footer={null}>
        {detail && (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-2 gap-2">
              <p>Status: <span className={`chip ${STATUS_CHIP[detail.status]}`}>{STATUS_LABEL[detail.status]}</span></p>
              <p>Nominal: <Money value={detail.nominal} className="font-semibold" /></p>
              <p>Kategori: {detail.kategori}</p>
              <p>Tanggal: {fmtDate(detail.tanggal)}</p>
              <p>Pemohon: {detail.created_by}</p>
              <p>Rekening: {detail.account_id || "-"} {detail.transaction_id && <span className="text-xs text-slate-400">(tx tertaut)</span>}</p>
              {detail.approved_by && <p>Disetujui: {detail.approved_by}</p>}
              {detail.paid_by && <p>Dibayar: {detail.paid_by}</p>}
              {detail.deskripsi && <p className="col-span-2">Deskripsi: {detail.deskripsi}</p>}
              {detail.bukti_file_id && <p className="col-span-2"><a className="text-red-600 font-semibold text-xs" href="#" onClick={(e) => { e.preventDefault(); openFile(detail.bukti_file_id); }}>Lihat bukti</a></p>}
            </div>
            <div><p className="font-semibold mb-1">Riwayat</p>
              <ul className="space-y-1">{(detail.history || []).map((h, i) => <li key={i} className="text-xs text-slate-600">{fmtDateTime(h.tanggal)} — <b>{h.aksi}</b> oleh {h.oleh} ({h.role}){h.alasan ? `: ${h.alasan}` : ""}</li>)}</ul>
            </div>
            <div className="flex justify-end gap-2 flex-wrap">
              {writable && detail.status === "draft" && <button type="button" className="btn-outline" onClick={() => act(detail.id, "submit")} data-testid="expense-submit-btn">Ajukan</button>}
              {writable && detail.status === "draft" && <button type="button" className="btn-outline" onClick={() => act(detail.id, "cancel")} data-testid="expense-cancel-btn">Batalkan</button>}
              {approver && canActOn(detail) && <button type="button" className="btn-primary" onClick={() => { if (window.confirm("Setujui pengajuan ini?")) act(detail.id, "decide", { setuju: true }); }} data-testid="expense-approve-btn"><Check size={15} />Setujui</button>}
              {approver && canActOn(detail) && <button type="button" className="btn-outline" onClick={() => { setRejectId(detail.id); setRejectReason(""); }} data-testid="expense-reject-btn"><X size={15} />Tolak</button>}
              {payer && detail.status === "disetujui" && <button type="button" className="btn-primary" onClick={() => { setPayAcc(detail.account_id || ""); setPayId(detail.id); }} data-testid="expense-pay-btn"><Wallet size={15} />Bayar</button>}
            </div>
          </div>
        )}
      </FormDialog>

      <FormDialog open={!!rejectId} onOpenChange={(v) => { if (!v) setRejectId(null); }} title="Tolak Pengajuan" description="Alasan wajib diisi dan tercatat di audit." onSubmit={reject} submitLabel="Tolak" testId="expense-reject-dialog">
        <Field label="Alasan penolakan"><textarea className="input" rows={3} data-testid="expense-reject-reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} required /></Field>
      </FormDialog>

      <FormDialog open={!!payId} onOpenChange={(v) => { if (!v) setPayId(null); }} title="Bayar Pengajuan" description="Membuat tepat 1 transaksi pengeluaran." onSubmit={pay} submitLabel="Bayar" loading={saving} testId="expense-pay-dialog">
        <Field label="Rekening pembayaran">
          <select className="input" data-testid="expense-pay-account" value={payAcc} onChange={(e) => setPayAcc(e.target.value)}>
            <option value="">— Pilih —</option>{(accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama} · {rupiah(a.saldo)}</option>)}
          </select>
        </Field>
      </FormDialog>
    </div>
  );
}
