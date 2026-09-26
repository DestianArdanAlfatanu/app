import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Users, UserCheck, GraduationCap, Plane, TrendingUp, TrendingDown, Landmark, AlertCircle, BookOpen, Briefcase, CalendarClock } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { useApi } from "@/hooks/useApi";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, Loading, EmptyState } from "@/components/common";
import { rupiah, STATUS_LABELS, STATUS_ORDER, fmtDateTime } from "@/lib/format";

const PERIODS = [["hari", "Hari ini"], ["minggu", "Minggu ini"], ["bulan", "Bulan ini"], ["tahun", "Tahun ini"]];

export default function DashboardPage() {
  const [period, setPeriod] = useState("bulan");
  const { user, can } = useAuth();
  const nav = useNavigate();
  const { data, loading } = useApi(`/dashboard?period=${period}`);
  const { data: cash } = useApi("/finance/cashflow?bulan=6", [], can("keuangan"));

  if (loading && !data) return <Loading />;
  if (!data) return <EmptyState text="Dashboard gagal dimuat. Muat ulang halaman untuk mencoba lagi." />;
  const s = data.siswa, k = data.keuangan, o = data.operasional, p = data.pending || {};
  const statusData = STATUS_ORDER.filter((x) => x !== "gagal").map((x) => ({ name: STATUS_LABELS[x].split(" ")[0], jumlah: s.per_status[x] || 0 }));

  return (
    <div>
      <PageHeader title={`Selamat datang, ${user.name.split(" ")[0]}`} jp="ダッシュボード" subtitle="Kondisi lembaga secara ringkas, semua data saling terhubung.">
        <div className="flex rounded-md border border-slate-200 bg-white p-1" data-testid="period-filter">
          {PERIODS.map(([k2, l]) => (
            <button key={k2} data-testid={`period-${k2}`} onClick={() => setPeriod(k2)} className={`px-3 h-8 rounded text-xs font-semibold transition-colors ${period === k2 ? "bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-100"}`}>{l}</button>
          ))}
        </div>
      </PageHeader>

      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Siswa</p>
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard testId="stat-total-siswa" label="Total Siswa" value={s.total} hint={`${s.baru_periode} pendaftar baru periode ini`} icon={Users} onClick={() => nav("/siswa")} />
        <StatCard testId="stat-siswa-aktif" label="Siswa Aktif" value={s.aktif} hint={`${s.pelatihan} sedang pelatihan`} icon={UserCheck} tone="amber" onClick={() => nav("/siswa?status=pelatihan")} />
        <StatCard testId="stat-siswa-lulus" label="Lulus / Matching" value={(s.per_status.lulus || 0) + (s.per_status.matching || 0)} hint={`${s.per_status.pemberkasan || 0} pemberkasan · ${s.per_status.visa || 0} visa`} icon={GraduationCap} tone="green" />
        <StatCard testId="stat-siswa-berangkat" label="Berangkat & Alumni" value={s.berangkat + s.alumni} hint={`${s.calon} calon siswa · ${s.gagal} gagal`} icon={Plane} tone="red" />
      </div>

      {k && (
        <>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Keuangan</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            <StatCard testId="stat-pemasukan" label="Pemasukan" value={rupiah(k.pemasukan)} hint={`Pembayaran hari ini ${rupiah(k.pembayaran_hari_ini)}`} icon={TrendingUp} tone="green" />
            <StatCard testId="stat-pengeluaran" label="Pengeluaran" value={rupiah(k.pengeluaran)} hint={`Laba ${rupiah(k.pemasukan - k.pengeluaran)}`} icon={TrendingDown} tone="red" />
            <StatCard testId="stat-saldo-kas" label="Saldo Kas & Bank" value={rupiah(k.saldo_kas)} hint={k.accounts.map((a) => `${a.nama}: ${rupiah(a.saldo)}`).join(" · ")} icon={Landmark} tone="blue" onClick={() => nav("/keuangan")} />
            <StatCard testId="stat-piutang" label="Piutang Siswa" value={rupiah(k.piutang)} hint={`${k.siswa_tunggakan} siswa memiliki tunggakan`} icon={AlertCircle} tone="amber" onClick={() => nav("/pembayaran?tab=tunggakan")} />
          </div>
        </>
      )}

      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Operasional</p>      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <StatCard testId="stat-guru" label="Guru / Karyawan" value={`${o.guru} / ${o.karyawan}`} icon={Users} />
        <StatCard testId="stat-kelas" label="Kelas Aktif" value={o.kelas_aktif} hint={`${o.jadwal_hari_ini.length} sesi hari ini`} icon={BookOpen} tone="indigo" onClick={() => nav("/kelas")} />
        <StatCard testId="stat-ujian" label="Siswa Akan Ujian" value={o.siswa_akan_ujian} hint={o.ujian_mendatang[0] ? `${o.ujian_mendatang[0].nama} · ${o.ujian_mendatang[0].tanggal}` : "Tidak ada ujian 14 hari ke depan"} icon={CalendarClock} tone="amber" />
        <StatCard testId="stat-joborder" label="Job Order Terbuka" value={o.job_order_terbuka} hint={`${o.interview_mendatang.length} interview mendatang · ${data.absensi_hari_ini.tidak_hadir} siswa absen hari ini`} icon={Briefcase} tone="red" onClick={() => nav("/job-order")} />
      </div>

      {(p.expense || p.leave || p.payroll) && (
        <>
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Menunggu Persetujuan</p>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
            {p.expense && <StatCard testId="stat-pending-expense" label="Pengajuan Biaya" value={p.expense.count} hint={p.expense.count ? `Total ${rupiah(p.expense.total)}` : "Tidak ada pengajuan menunggu"} icon={AlertCircle} tone="amber" onClick={() => nav("/pengajuan")} />}
            {p.leave && <StatCard testId="stat-pending-leave" label="Pengajuan Cuti" value={p.leave.count} hint={p.leave.count ? "Perlu keputusan" : "Tidak ada cuti menunggu"} icon={CalendarClock} tone="amber" onClick={() => nav("/sdm")} />}
            {p.payroll && <StatCard testId="stat-pending-payroll" label="Payroll Draft" value={p.payroll.count} hint={p.payroll.count ? `Total bersih ${rupiah(p.payroll.total)}` : "Tidak ada draft"} icon={Landmark} tone="blue" onClick={() => nav("/sdm")} />}
          </div>
        </>
      )}

      <p className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">Aksi Cepat</p>
      <div className="flex flex-wrap gap-2 mb-8">
        {can("expense_write") && <button className="btn-outline btn-sm" onClick={() => nav("/pengajuan")} data-testid="quick-expense">+ Pengajuan Biaya</button>}
        {can("payroll_write") && <button className="btn-outline btn-sm" onClick={() => nav("/sdm")} data-testid="quick-payroll">+ Payroll / Cuti</button>}
        {can("pembayaran_write") && <button className="btn-outline btn-sm" onClick={() => nav("/pembayaran")} data-testid="quick-payment">+ Pembayaran</button>}
        {can("siswa_write") && <button className="btn-outline btn-sm" onClick={() => nav("/siswa")} data-testid="quick-student">+ Calon Siswa</button>}
        {can("laporan") && <button className="btn-outline btn-sm" onClick={() => nav("/laporan")} data-testid="quick-report">Lihat Laporan</button>}
      </div>

      <div className="grid lg:grid-cols-3 gap-4">
        <div className="card card-pad lg:col-span-2">
          <h3 className="font-semibold text-slate-900">Siswa per Status Pipeline</h3>
          <div className="h-64 mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={statusData} margin={{ left: -20 }}>
                <CartesianGrid vertical={false} stroke="#E2E8F0" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} angle={-45} textAnchor="end" height={80} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip cursor={{ fill: "#F1F5F9" }} />
                <Bar dataKey="jumlah" fill="#0F172A" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
        <div className="card card-pad">
          <h3 className="font-semibold text-slate-900">Jadwal Hari Ini</h3>
          <div className="mt-3 space-y-2">
            {o.jadwal_hari_ini.length === 0 && <p className="text-sm text-slate-400">Tidak ada sesi kelas hari ini.</p>}
            {o.jadwal_hari_ini.map((j, i) => (
              <div key={i} className="flex items-center justify-between text-sm border border-slate-100 rounded-md px-3 py-2">
                <div><p className="font-medium">{j.kelas}</p><p className="text-xs text-slate-500">{j.guru || "-"}</p></div>
                <span className="mono text-xs text-slate-600">{j.jam_mulai}–{j.jam_selesai}</span>
              </div>
            ))}
          </div>
          <h3 className="font-semibold text-slate-900 mt-6">Interview Mendatang</h3>
          <div className="mt-3 space-y-2">
            {o.interview_mendatang.length === 0 && <p className="text-sm text-slate-400">Belum ada jadwal interview.</p>}
            {o.interview_mendatang.map((iv) => (
              <div key={iv.id} className="text-sm border border-slate-100 rounded-md px-3 py-2">
                <p className="font-medium">{iv.student_nama}</p>
                <p className="text-xs text-slate-500">{iv.perusahaan} · {iv.tanggal}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className="grid lg:grid-cols-3 gap-4 mt-4">
        {cash && (
          <div className="card card-pad lg:col-span-2">
            <h3 className="font-semibold text-slate-900">Arus Kas 6 Bulan</h3>
            <div className="h-60 mt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={cash} margin={{ left: 10 }}>
                  <CartesianGrid vertical={false} stroke="#E2E8F0" />
                  <XAxis dataKey="bulan" tick={{ fontSize: 11 }} />
                  <YAxis tick={{ fontSize: 11 }} tickFormatter={(v) => `${(v / 1e6).toFixed(0)}jt`} />
                  <Tooltip formatter={(v) => rupiah(v)} cursor={{ fill: "#F1F5F9" }} />
                  <Bar dataKey="pemasukan" name="Pemasukan" fill="#16A34A" radius={[3, 3, 0, 0]} />
                  <Bar dataKey="pengeluaran" name="Pengeluaran" fill="#DC2626" radius={[3, 3, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}
        <div className={`card card-pad ${cash ? "" : "lg:col-span-3"}`}>
          <h3 className="font-semibold text-slate-900">Aktivitas Terbaru</h3>
          <div className="mt-3 space-y-3">
            {data.aktivitas_terbaru.map((a) => (
              <div key={a.id} className="flex gap-3 text-sm">
                <span className="mt-1.5 h-2 w-2 rounded-full bg-red-600 shrink-0" />
                <div className="min-w-0"><p className="text-slate-800 truncate"><b>{a.user_name}</b> · {a.action} {a.entity}</p><p className="text-[11px] text-slate-400">{fmtDateTime(a.timestamp)}</p></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
