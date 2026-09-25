import { useState } from "react";
import { Plus, Pencil, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { api, errMsg } from "@/lib/api";
import { PageHeader, Loading, FormDialog, Field } from "@/components/common";
import { ROLE_LABELS, fmtDateTime } from "@/lib/format";

const ACCESS = { owner: "Seluruh sistem", admin: "Operasional umum: siswa, kelas, job order, laporan", finance: "Pembayaran, pemasukan, pengeluaran, kas, laporan keuangan", hr: "Karyawan, guru, laporan SDM", guru: "Kelas yang diajar, absensi, nilai", marketing: "Calon siswa, pendaftaran, job order", staff: "Akses terbatas (baca siswa & kelas)", student: "Portal siswa miliknya sendiri" };
const EMPTY = { name: "", email: "", password: "", role: "staff", employee_id: "", student_id: "", aktif: true };

export default function UsersPage() {
  const { user: me } = useAuth();
  const isOwner = me?.role === "owner";
  const { data, loading, reload } = useApi("/users");
  const { data: emps } = useApi("/employees");
  const { data: students } = useApi("/students", [], isOwner);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [editId, setEditId] = useState(null);

  const save = async () => {
    const body = { ...form, employee_id: form.employee_id || null, student_id: form.student_id || null, password: form.password || null };
    try { editId ? await api.put(`/users/${editId}`, body) : await api.post("/users", body); toast.success("Akun tersimpan"); setOpen(false); reload(); } catch (e) { toast.error(errMsg(e)); }
  };
  const remove = async (u) => { if (!window.confirm(`Hapus akun ${u.email}?`)) return; try { await api.delete(`/users/${u.id}`); reload(); } catch (e) { toast.error(errMsg(e)); } };

  return (
    <div>
      <PageHeader title="Pengguna & Hak Akses" jp="ユーザー管理" subtitle="Akun dibuat oleh Super Admin. Setiap role hanya melihat modul yang relevan.">
        <button className="btn-red" onClick={() => { setForm({ ...EMPTY, role: isOwner ? "staff" : "student" }); setEditId(null); setOpen(true); }} data-testid="add-user-btn"><Plus size={16} />Tambah Akun</button>
      </PageHeader>
      <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-3 mb-6">{Object.entries(ACCESS).map(([r, d]) => <div key={r} className="card p-3"><p className="text-xs font-bold uppercase tracking-wider text-red-600">{ROLE_LABELS[r]}</p><p className="text-xs text-slate-600 mt-1">{d}</p></div>)}</div>
      {loading && !data ? <Loading /> : (
        <div className="table-wrap fade-up"><table className="tbl" data-testid="users-table"><thead><tr><th>Nama</th><th>Email</th><th>Role</th><th>Terhubung ke</th><th>Status</th><th>Login Terakhir</th><th></th></tr></thead>
          <tbody>{(data || []).map((u) => <tr key={u.id} data-testid={`user-row-${u.id}`}><td className="font-semibold">{u.name}</td><td>{u.email}</td><td><span className="chip bg-slate-900 text-white border-slate-900">{ROLE_LABELS[u.role]}</span></td><td className="text-xs">{(emps || []).find((e) => e.id === u.employee_id)?.nama || (students || []).find((s) => s.id === u.student_id)?.nama_lengkap || "-"}</td><td><span className={`chip ${u.aktif !== false ? "bg-emerald-50 text-emerald-700 border-emerald-200" : "bg-slate-100"}`}>{u.aktif !== false ? "Aktif" : "Nonaktif"}</span></td><td className="text-xs">{fmtDateTime(u.last_login)}</td>
            <td className="whitespace-nowrap">{isOwner ? (<><button className="btn-ghost btn-sm" onClick={() => { setForm({ ...EMPTY, ...u, password: "", employee_id: u.employee_id || "", student_id: u.student_id || "" }); setEditId(u.id); setOpen(true); }} data-testid={`edit-user-${u.id}`}><Pencil size={13} /></button>{u.id !== me.id && (<button className="btn-ghost btn-sm text-red-600" onClick={() => remove(u)} data-testid={`delete-user-${u.id}`}><Trash2 size={13} /></button>)}</>) : null}</td></tr>)}
          </tbody></table></div>)}
      <FormDialog open={open} onOpenChange={setOpen} title={editId ? "Edit Akun" : "Tambah Akun Pengguna"} onSubmit={save} testId="user-dialog">
        <Field label="Nama"><input className="input" data-testid="user-name-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required /></Field>
        <Field label="Email"><input type="email" className="input" data-testid="user-email-input" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required /></Field>
        <Field label={editId ? "Password baru (kosongkan jika tidak diubah)" : "Password (min 6 karakter)"}><input type="password" className="input" data-testid="user-password-input" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Role"><select className="input" data-testid="user-role-select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>{Object.entries(ROLE_LABELS).filter(([k]) => isOwner || k === "student").map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
          {form.role === "student"
            ? <Field label="Terhubung ke Siswa"><select className="input" data-testid="user-student-select" value={form.student_id} onChange={(e) => setForm({ ...form, student_id: e.target.value })} required><option value="">-</option>{(students || []).map((s) => <option key={s.id} value={s.id}>{s.nama_lengkap}</option>)}</select></Field>
            : <Field label="Terhubung ke Guru/Karyawan"><select className="input" data-testid="user-employee-select" value={form.employee_id} onChange={(e) => setForm({ ...form, employee_id: e.target.value })}><option value="">-</option>{(emps || []).map((e) => <option key={e.id} value={e.id}>{e.nama} ({e.tipe})</option>)}</select></Field>}
        </div>
        <Field label="Status"><select className="input" value={form.aktif ? "1" : "0"} onChange={(e) => setForm({ ...form, aktif: e.target.value === "1" })}><option value="1">Aktif</option><option value="0">Nonaktif</option></select></Field>
      </FormDialog>
    </div>
  );
}
