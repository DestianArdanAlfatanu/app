import { useState } from "react";
import { Field } from "@/components/common";

export const EMPTY_STUDENT = {
  nama_lengkap: "", nik: "", no_kk: "", tempat_lahir: "", tanggal_lahir: "", jenis_kelamin: "L",
  alamat: { desa: "", kecamatan: "", kabupaten: "", provinsi: "" }, no_hp: "", email: "", nama_orang_tua: "", no_hp_orang_tua: "",
  wa_student_opt_in: false, wa_guardian_opt_in: false,
  pendidikan_terakhir: "SMA", nama_sekolah: "", jurusan: "", tahun_lulus: "", tinggi_badan: "", berat_badan: "",
  status_pernikahan: "belum_menikah", riwayat_pekerjaan: "", riwayat_kesehatan: "", kemampuan_bahasa_jepang: "-", status: "calon_siswa", jatuh_tempo: "", catatan: "",
  sumber_prospek: "", pemilik_lead: "",
};

export function normalizeStudent(f) {
  return { ...f, tanggal_lahir: f.tanggal_lahir || null, jatuh_tempo: f.jatuh_tempo || null,
    tinggi_badan: f.tinggi_badan === "" ? null : Number(f.tinggi_badan), berat_badan: f.berat_badan === "" ? null : Number(f.berat_badan) };
}

export const StudentForm = ({ form, setForm }) => {
  const [sec, setSec] = useState("pribadi");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const setA = (k) => (e) => setForm({ ...form, alamat: { ...form.alamat, [k]: e.target.value } });
  const secs = [["pribadi", "Data Pribadi"], ["pendidikan", "Pendidikan"], ["tambahan", "Data Tambahan"]];
  return (
    <div>
      <div className="flex gap-1 mb-4 border-b border-slate-200">
        {secs.map(([k, l]) => <button type="button" key={k} data-testid={`student-form-sec-${k}`} onClick={() => setSec(k)} className={`px-3 py-2 text-sm font-medium border-b-2 -mb-px ${sec === k ? "border-red-600 text-slate-900" : "border-transparent text-slate-500"}`}>{l}</button>)}
      </div>
      {sec === "pribadi" && (
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Nama Lengkap *" className="sm:col-span-2"><input data-testid="student-nama-input" className="input" value={form.nama_lengkap} onChange={set("nama_lengkap")} required /></Field>
          <Field label="NIK"><input data-testid="student-nik-input" className="input" value={form.nik} onChange={set("nik")} /></Field>
          <Field label="Nomor KK"><input className="input" value={form.no_kk} onChange={set("no_kk")} /></Field>
          <Field label="Tempat Lahir"><input className="input" value={form.tempat_lahir} onChange={set("tempat_lahir")} /></Field>
          <Field label="Tanggal Lahir"><input data-testid="student-tanggal-lahir-input" type="date" className="input" value={form.tanggal_lahir || ""} onChange={set("tanggal_lahir")} /></Field>
          <Field label="Jenis Kelamin"><select data-testid="student-jk-select" className="input" value={form.jenis_kelamin} onChange={set("jenis_kelamin")}><option value="L">Laki-laki</option><option value="P">Perempuan</option></select></Field>
          <Field label="Nomor HP"><input data-testid="student-hp-input" className="input" value={form.no_hp} onChange={set("no_hp")} /></Field>
          <Field label="Email"><input type="email" className="input" value={form.email} onChange={set("email")} /></Field>
          <Field label="Sumber Prospek"><select data-testid="student-sumber-select" className="input" value={form.sumber_prospek || ""} onChange={set("sumber_prospek")}><option value="">— Pilih —</option>{["referral", "sosmed", "iklan", "sekolah", "kunjungan", "lainnya"].map((x) => <option key={x} value={x}>{x}</option>)}</select></Field>
          <Field label="Pemilik Lead"><input data-testid="student-pemilik-input" className="input" value={form.pemilik_lead || ""} onChange={set("pemilik_lead")} placeholder="mis. Marketing A" /></Field>
          <Field label="Nama Orang Tua"><input className="input" value={form.nama_orang_tua} onChange={set("nama_orang_tua")} /></Field>
          <Field label="No. HP Orang Tua"><input className="input" value={form.no_hp_orang_tua} onChange={set("no_hp_orang_tua")} /></Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-1"><input type="checkbox" data-testid="student-wa-siswa" checked={!!form.wa_student_opt_in} onChange={(e) => setForm({ ...form, wa_student_opt_in: e.target.checked })} />WA siswa boleh dihubungi</label>
          <Field label="No. WA Wali (otomatis dari HP ortu bila kosong)"><input className="input mono" value={form.wa_guardian_phone || ""} placeholder="628..." onChange={(e) => setForm({ ...form, wa_guardian_phone: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-1"><input type="checkbox" data-testid="student-wa-wali" checked={!!form.wa_guardian_opt_in} onChange={(e) => setForm({ ...form, wa_guardian_opt_in: e.target.checked })} />WA wali boleh dihubungi</label>
          <Field label="Desa"><input className="input" value={form.alamat?.desa || ""} onChange={setA("desa")} /></Field>
          <Field label="Kecamatan"><input className="input" value={form.alamat?.kecamatan || ""} onChange={setA("kecamatan")} /></Field>
          <Field label="Kabupaten"><input className="input" value={form.alamat?.kabupaten || ""} onChange={setA("kabupaten")} /></Field>
          <Field label="Provinsi"><input className="input" value={form.alamat?.provinsi || ""} onChange={setA("provinsi")} /></Field>
        </div>
      )}
      {sec === "pendidikan" && (
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Pendidikan Terakhir"><select className="input" value={form.pendidikan_terakhir} onChange={set("pendidikan_terakhir")}>{["SMP", "SMA", "SMK", "D1", "D3", "S1"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Nama Sekolah"><input className="input" value={form.nama_sekolah} onChange={set("nama_sekolah")} /></Field>
          <Field label="Jurusan"><input className="input" value={form.jurusan} onChange={set("jurusan")} /></Field>
          <Field label="Tahun Lulus"><input className="input" value={form.tahun_lulus} onChange={set("tahun_lulus")} /></Field>
        </div>
      )}
      {sec === "tambahan" && (
        <div className="grid sm:grid-cols-2 gap-3">
          <Field label="Tinggi Badan (cm)"><input type="number" className="input" value={form.tinggi_badan ?? ""} onChange={set("tinggi_badan")} /></Field>
          <Field label="Berat Badan (kg)"><input type="number" className="input" value={form.berat_badan ?? ""} onChange={set("berat_badan")} /></Field>
          <Field label="Status Pernikahan"><select className="input" value={form.status_pernikahan} onChange={set("status_pernikahan")}><option value="belum_menikah">Belum Menikah</option><option value="menikah">Menikah</option><option value="cerai">Cerai</option></select></Field>
          <Field label="Kemampuan Bahasa Jepang"><select data-testid="student-jlpt-select" className="input" value={form.kemampuan_bahasa_jepang} onChange={set("kemampuan_bahasa_jepang")}>{["-", "N5", "N4", "N3", "N2", "N1"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Riwayat Pekerjaan" className="sm:col-span-2"><textarea className="input" value={form.riwayat_pekerjaan} onChange={set("riwayat_pekerjaan")} /></Field>
          <Field label="Riwayat Kesehatan" className="sm:col-span-2"><textarea className="input" value={form.riwayat_kesehatan} onChange={set("riwayat_kesehatan")} /></Field>
          <Field label="Jatuh Tempo Pembayaran Berikutnya"><input type="date" className="input" value={form.jatuh_tempo || ""} onChange={set("jatuh_tempo")} /></Field>
          <Field label="Catatan"><input className="input" value={form.catatan} onChange={set("catatan")} /></Field>
        </div>
      )}
    </div>
  );
};
