import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { useApi } from "@/hooks/useApi";
import { FormDialog, Field } from "@/components/common";
import { METODE, rupiah, today } from "@/lib/format";

export const PaymentDialog = ({ open, onOpenChange, student, students, onSaved }) => {
  const { data: accounts } = useApi("/finance/accounts", [], open);
  const [f, setF] = useState({ student_id: "", nominal: "", tanggal: today(), metode: "cash", jenis: "Cicilan", no_transaksi: "", account_id: "", catatan: "", bukti: null });
  const [saving, setSaving] = useState(false);

  useEffect(() => { if (open) setF((x) => ({ ...x, student_id: student?.id || "", nominal: "", no_transaksi: "", catatan: "", bukti: null, tanggal: today() })); }, [open, student]);
  useEffect(() => { if (accounts?.length && !f.account_id) setF((x) => ({ ...x, account_id: accounts[0].id })); }, [accounts, f.account_id]);

  const sel = student || (students || []).find((s) => s.id === f.student_id);
  const save = async () => {
    if (!f.student_id) return toast.error("Pilih siswa terlebih dahulu");
    setSaving(true);
    try {
      let bukti_file_id = null;
      if (f.bukti) { const fd = new FormData(); fd.append("file", f.bukti); bukti_file_id = (await api.post("/upload", fd)).data.id; }
      const { data } = await api.post("/payments", { ...f, nominal: Number(f.nominal), bukti_file_id, bukti: undefined });
      toast.success(`Pembayaran ${rupiah(data.nominal)} tercatat · ${data.no_kwitansi}`);
      onOpenChange(false); onSaved && onSaved(data);
    } catch (e) { toast.error(errMsg(e)); } finally { setSaving(false); }
  };
  return (
    <FormDialog open={open} onOpenChange={onOpenChange} title="Catat Pembayaran Siswa" description="Otomatis masuk ke pemasukan kas dan membuat kwitansi." onSubmit={save} loading={saving} testId="payment-dialog">
      {!student && <Field label="Siswa"><select className="input" data-testid="payment-student-select" value={f.student_id} onChange={(e) => setF({ ...f, student_id: e.target.value })} required><option value="">Pilih siswa...</option>{(students || []).map((s) => <option key={s.id} value={s.id}>{s.nama_lengkap} — sisa {rupiah(s.pembayaran?.sisa ?? s.sisa)}</option>)}</select></Field>}
      {sel && <div className="rounded-md bg-slate-50 border border-slate-100 p-3 text-sm flex justify-between"><span>{sel.nama_lengkap}</span><span className="mono text-red-600 font-semibold">Sisa {rupiah(sel.pembayaran?.sisa ?? sel.sisa)}</span></div>}
      <div className="grid grid-cols-2 gap-3">
        <Field label="Nominal (Rp)"><input type="number" min="1" className="input mono" data-testid="payment-nominal-input" value={f.nominal} onChange={(e) => setF({ ...f, nominal: e.target.value })} required /></Field>
        <Field label="Tanggal"><input type="date" className="input" data-testid="payment-tanggal-input" value={f.tanggal} onChange={(e) => setF({ ...f, tanggal: e.target.value })} required /></Field>
        <Field label="Metode"><select className="input" data-testid="payment-metode-select" value={f.metode} onChange={(e) => setF({ ...f, metode: e.target.value })}>{METODE.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
        <Field label="Jenis Pembayaran"><select className="input" data-testid="payment-jenis-select" value={f.jenis} onChange={(e) => setF({ ...f, jenis: e.target.value })}>{["Cicilan", "Pendaftaran", "Pelatihan", "Asrama", "Dokumen", "Keberangkatan", "Pelunasan"].map((x) => <option key={x}>{x}</option>)}</select></Field>
        <Field label="Masuk ke Rekening"><select className="input" data-testid="payment-account-select" value={f.account_id} onChange={(e) => setF({ ...f, account_id: e.target.value })} required>{(accounts || []).map((a) => <option key={a.id} value={a.id}>{a.nama}</option>)}</select></Field>
        <Field label="No. Transaksi / Ref"><input className="input" data-testid="payment-ref-input" value={f.no_transaksi} onChange={(e) => setF({ ...f, no_transaksi: e.target.value })} /></Field>
      </div>
      <Field label="Bukti Pembayaran (opsional)"><input type="file" className="input py-1.5" data-testid="payment-bukti-input" accept=".pdf,.jpg,.jpeg,.png" onChange={(e) => setF({ ...f, bukti: e.target.files?.[0] || null })} /></Field>
      <Field label="Catatan"><input className="input" data-testid="payment-catatan-input" value={f.catatan} onChange={(e) => setF({ ...f, catatan: e.target.value })} /></Field>
    </FormDialog>
  );
};
