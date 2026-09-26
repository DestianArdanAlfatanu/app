import { Printer } from "lucide-react";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { useApi } from "@/hooks/useApi";
import { openFile } from "@/lib/api";
import { rupiah, fmtDate } from "@/lib/format";

export const ReceiptDialog = ({ paymentId, onClose }) => {
  const { data: r } = useApi(paymentId ? `/payments/${paymentId}/receipt` : null, [paymentId], !!paymentId);
  return (
    <Dialog open={!!paymentId} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="bg-white sm:max-w-2xl max-h-[92vh] overflow-y-auto" data-testid="receipt-dialog">
        <DialogTitle className="sr-only">Kwitansi</DialogTitle>
        {!r ? <p className="text-sm text-slate-500">Memuat kwitansi...</p> : (
          <div>
            <div className="print-area border border-slate-300 p-6 sm:p-8 relative" data-testid="receipt-content">
              <div className="absolute top-0 left-0 right-0 h-1.5 bg-red-600" />
              <div className="flex justify-between items-start gap-4 mt-2">
                <div className="flex items-center gap-3"><div className="h-11 w-11 rounded-md bg-slate-900 flex items-center justify-center"><span className="h-4 w-4 rounded-full bg-red-600 block" /></div>
                  <div><p className="font-bold tracking-tight">LPK Penyaluran Kerja Jepang</p><p className="text-xs text-slate-500">Lembaga Pelatihan Kerja · <span className="font-jp">技能実習生</span></p></div></div>
                <div className="text-right"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-400">Kwitansi</p><p className="mono font-bold text-lg" data-testid="receipt-no">{r.no_kwitansi}</p></div>
              </div>
              <div className="grid grid-cols-2 gap-6 mt-8 text-sm">
                <div><p className="label">Diterima dari</p><p className="font-semibold text-slate-900">{r.student_nama}</p><p className="text-xs text-slate-500">{[r.alamat?.kecamatan, r.alamat?.kabupaten].filter(Boolean).join(", ")} · {r.no_hp}</p></div>
                <div className="text-right"><p className="label">Tanggal</p><p className="font-semibold">{fmtDate(r.tanggal)}</p></div>
                <div><p className="label">Untuk Pembayaran</p><p className="font-semibold">{r.jenis}</p>{r.catatan && <p className="text-xs text-slate-500">{r.catatan}</p>}</div>
                <div className="text-right"><p className="label">Metode</p><p className="font-semibold capitalize">{r.metode} {r.no_transaksi ? `· ${r.no_transaksi}` : ""}</p><p className="text-xs text-slate-500">{r.account_nama}</p></div>
              </div>
              <div className="mt-8 rounded-md bg-slate-900 text-white p-5 flex items-center justify-between"><span className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">Jumlah Dibayar</span><span className="mono text-2xl font-bold" data-testid="receipt-nominal">{rupiah(r.nominal)}</span></div>
              <div className="grid grid-cols-3 gap-3 mt-4 text-sm">
                <div className="border border-slate-200 rounded-md p-3"><p className="label">Total Tagihan</p><p className="mono font-semibold">{rupiah(r.total_tagihan)}</p></div>
                <div className="border border-slate-200 rounded-md p-3"><p className="label">Total Dibayar</p><p className="mono font-semibold text-emerald-700">{rupiah(r.total_dibayar)}</p></div>
                <div className="border border-slate-200 rounded-md p-3"><p className="label">Sisa Pembayaran</p><p className="mono font-semibold text-red-600" data-testid="receipt-sisa">{rupiah(r.sisa)}</p></div>
              </div>
              <div className="flex justify-between items-end mt-10 text-sm">
                <p className="text-xs text-slate-400">Dokumen ini dihasilkan otomatis oleh Sistem LPK dan sah tanpa tanda tangan basah.</p>
                <div className="text-center"><p className="text-xs text-slate-500 mb-10">Petugas</p><p className="font-semibold border-t border-slate-300 pt-1 px-4">{r.petugas}</p></div>
              </div>
            </div>
            <div className="flex justify-between items-center mt-4 no-print">
              {r.bukti_file_id ? <a href="#" onClick={(e) => { e.preventDefault(); openFile(r.bukti_file_id); }} className="btn-outline btn-sm" data-testid="receipt-bukti-link">Lihat bukti pembayaran</a> : <span />}
              <div className="flex gap-2"><button className="btn-outline" onClick={onClose} data-testid="receipt-close-btn">Tutup</button><button className="btn-primary" onClick={() => window.print()} data-testid="receipt-print-btn"><Printer size={15} />Cetak / PDF</button></div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
