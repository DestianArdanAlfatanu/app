import { useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Tabs, FormDialog, Field, EmptyState, Money, Loading } from "@/components/common";
import HrAttendanceTab from "@/components/HrAttendanceTab";
import LeaveTab from "@/components/LeaveTab";
import PayrollTab from "@/components/PayrollTab";
import { fmtDate } from "@/lib/format";

const EMPTY = { nama: "", tipe: "karyawan", nik: "", jabatan: "", no_hp: "", email: "", alamat: "", tanggal_masuk: "", status_kerja: "tetap", gaji_pokok: 0, tunjangan: 0, honor_per_pertemuan: 0, spesialisasi: "", sertifikat: "", kontrak_berakhir: "", aktif: true };

export default function HRPage() {
  const { can } = useAuth();
  const [tab, setTab] = useState("guru");
  const { data, loading, reload } = useApi("/employees");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);
  const showAtt = can("hr_attendance");
  const showLeave = can("leave");
  const showPayroll = can("payroll");
  const tabs = [
    { key: "guru", label: "Guru", count: (data || []).filter((e) => e.tipe === "guru").length },
    { key: "karyawan", label: "Karyawan", count: (data || []).filter((e) => e.tipe === "karyawan").length },
    ...(showAtt ? [{ key: "absensi", label: "Absensi" }] : []),
    ...(showLeave ? [{ key: "cuti", label: "Cuti" }] : []),
    ...(showPayroll ? [{ key: "payroll", label: "Payroll" }] : []),
  ];
  const rows = (data || []).filter((e) => e.tipe === tab);

  const save = async () => {
    const body = { ...form, gaji_pokok: Number(form.gaji_pokok), tunjangan: Number(form.tunjangan), honor_per_pertemuan: Number(form.honor_per_pertemuan),
      sertifikat: typeof form.sertifikat === "string" ? form.sertifikat.split(",").map((x) => x.trim()).filter(Boolean) : form.sertifikat,
      tanggal_masuk: form.tanggal_masuk || null, kontrak_berakhir: form.kontrak_berakhir || null };
    try { editId ? await api.put(`/employees/${editId}`, body) : await api.post("/employees", body); toast.success("Data tersimpan"); setOpen(false); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const remove = async (e) => { if (!window.confirm(`Hapus ${e.nama}?`)) return; try { await api.delete(`/employees/${e.id}`); reload(); } catch (x) { toast.error(errMsg(x)); } };

  return (
    <div>
      <PageHeader title="Guru & Karyawan" jp="教師・職員" subtitle="Biodata, jabatan, gaji/honor, kontrak, dan kelas yang diajar.">
        {can("sdm_write") && (tab === "guru" || tab === "karyawan") && <button className="btn-red" onClick={() => { setForm({ ...EMPTY, tipe: tab }); setEditId(null); setOpen(true); }} data-testid="add-employee-btn"><Plus size={16} />Tambah {tab === "guru" ? "Guru" : "Karyawan"}</button>}
      </PageHeader>
      <Tabs active={tab} onChange={setTab} testPrefix="hr-tab" tabs={tabs} />
      {tab === "absensi" ? <HrAttendanceTab employees={data} loadingEmployees={loading && !data} /> : tab === "cuti" ? <LeaveTab employees={data} /> : tab === "payroll" ? <PayrollTab employees={data} /> : (
      <>{loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="employees-table"><thead><tr><th>Nama</th><th>Jabatan</th>{tab === "guru" ? <><th>Spesialisasi</th><th>Kelas Diajar</th><th>Honor/Pertemuan</th></> : <><th>Status</th><th>Masuk</th></>}<th>Gaji Pokok</th><th>Kontrak</th><th>Kontak</th><th></th></tr></thead>
          <tbody>{rows.length === 0 && <tr><td colSpan={9}><EmptyState /></td></tr>}
            {rows.map((e) => <tr key={e.id} data-testid={`employee-row-${e.id}`}><td><p className="font-semibold">{e.nama}</p><p className="text-xs text-slate-400">{e.email}</p></td><td>{e.jabatan}</td>
              {tab === "guru" ? <><td className="text-xs">{e.spesialisasi}<br /><span className="text-slate-400">{(e.sertifikat || []).join(", ")}</span></td><td>{e.kelas.map((c) => <span key={c.id} className="chip bg-slate-50 mr-1 mb-1">{c.nama}</span>)}{e.kelas.length === 0 && "-"}</td><td>{e.honor_per_pertemuan != null ? <Money value={e.honor_per_pertemuan} /> : "-"}</td></> : <><td><span className={`chip ${e.aktif ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100"}`}>{e.status_kerja}{!e.aktif && " · nonaktif"}</span></td><td>{fmtDate(e.tanggal_masuk)}</td></>}
              <td>{e.gaji_pokok != null ? <Money value={e.gaji_pokok} /> : <span className="text-slate-400 text-xs">tersembunyi</span>}</td><td className={e.kontrak_berakhir && e.kontrak_berakhir <= new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10) ? "text-amber-600 font-semibold" : ""}>{e.kontrak_berakhir ? fmtDate(e.kontrak_berakhir) : "-"}</td><td className="text-xs">{e.no_hp}</td>
              <td className="whitespace-nowrap">{can("sdm_write") && <><button className="btn-ghost btn-sm" onClick={() => { setForm({ ...EMPTY, ...e, sertifikat: (e.sertifikat || []).join(", "), tanggal_masuk: e.tanggal_masuk || "", kontrak_berakhir: e.kontrak_berakhir || "" }); setEditId(e.id); setOpen(true); }} data-testid={`edit-employee-${e.id}`}><Pencil size={13} /></button><button className="btn-ghost btn-sm text-red-600" onClick={() => remove(e)}><Trash2 size={13} /></button></>}</td></tr>)}
          </tbody></table></div>)}

      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Edit Data" : `Tambah ${form.tipe === "guru" ? "Guru" : "Karyawan"}`} onSubmit={save} testId="employee-dialog" wide>
        <div className="grid sm:grid-cols-3 gap-3">
          <Field label="Nama" className="sm:col-span-2"><input className="input" data-testid="emp-nama-input" value={form.nama} onChange={(e) => setForm({ ...form, nama: e.target.value })} required /></Field>
          <Field label="Tipe"><select className="input" data-testid="emp-tipe-select" value={form.tipe} onChange={(e) => setForm({ ...form, tipe: e.target.value })}><option value="guru">Guru</option><option value="karyawan">Karyawan</option></select></Field>
          <Field label="NIK"><input className="input" value={form.nik} onChange={(e) => setForm({ ...form, nik: e.target.value })} /></Field>
          <Field label="Jabatan"><input className="input" data-testid="emp-jabatan-input" value={form.jabatan} onChange={(e) => setForm({ ...form, jabatan: e.target.value })} /></Field>
          <Field label="Status Kerja"><select className="input" value={form.status_kerja} onChange={(e) => setForm({ ...form, status_kerja: e.target.value })}>{["tetap", "kontrak", "freelance", "magang"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="No. HP"><input className="input" value={form.no_hp} onChange={(e) => setForm({ ...form, no_hp: e.target.value })} /></Field>
          <Field label="Email"><input className="input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Tanggal Masuk"><input type="date" className="input" value={form.tanggal_masuk} onChange={(e) => setForm({ ...form, tanggal_masuk: e.target.value })} /></Field>
          <Field label="Alamat" className="sm:col-span-3"><input className="input" value={form.alamat} onChange={(e) => setForm({ ...form, alamat: e.target.value })} /></Field>
          <Field label="Gaji Pokok"><input type="number" className="input mono" data-testid="emp-gaji-input" value={form.gaji_pokok} onChange={(e) => setForm({ ...form, gaji_pokok: e.target.value })} /></Field>
          <Field label="Tunjangan"><input type="number" className="input mono" value={form.tunjangan} onChange={(e) => setForm({ ...form, tunjangan: e.target.value })} /></Field>
          <Field label="Kontrak Berakhir"><input type="date" className="input" value={form.kontrak_berakhir} onChange={(e) => setForm({ ...form, kontrak_berakhir: e.target.value })} /></Field>
          {form.tipe === "guru" && <>
            <Field label="Honor / Pertemuan"><input type="number" className="input mono" value={form.honor_per_pertemuan} onChange={(e) => setForm({ ...form, honor_per_pertemuan: e.target.value })} /></Field>
            <Field label="Spesialisasi"><input className="input" value={form.spesialisasi} onChange={(e) => setForm({ ...form, spesialisasi: e.target.value })} /></Field>
            <Field label="Sertifikat (pisahkan koma)"><input className="input" value={form.sertifikat} onChange={(e) => setForm({ ...form, sertifikat: e.target.value })} /></Field></>}
          <Field label="Aktif"><select className="input" value={form.aktif ? "1" : "0"} onChange={(e) => setForm({ ...form, aktif: e.target.value === "1" })}><option value="1">Aktif</option><option value="0">Nonaktif</option></select></Field>
        </div>
      </FormDialog>
      </>)}
    </div>
  );
}
