# PRD — Sistem Digital LPK Penyaluran Kerja ke Jepang

## Problem Statement (asli)
"Buatkan saya website untuk menjawab kebutuhan yang ada pada file tersebut" — dokumen kebutuhan sistem terintegrasi LPK: data siswa (pendaftaran → alumni), seleksi, kelas/absensi/nilai/ujian, pembayaran & kwitansi, keuangan (kas, rekening, rekonsiliasi), SDM, job order & matching, dokumen, laporan, audit trail, role & hak akses, notifikasi, search global, mobile responsive.

## Pilihan User
- MVP = modul inti (opsi a). Auth JWT email/password, akun dibuat Super Admin. Upload file asli (penyimpanan lokal server). Tanpa WhatsApp. Tema terang profesional nuansa Jepang.

## Arsitektur
- Backend FastAPI `/api` (routers: auth, students, academics, finance, hr, jobs, dashboard), MongoDB (uuid `id`, tanpa ObjectId di respons), JWT (PyJWT + bcrypt), Object Storage via INTEGRATION_PROXY_URL.
- Frontend React + Tailwind + shadcn, AuthContext dengan `can(module)` role map, pages di `src/pages`, Bearer token di localStorage.
- Seed otomatis saat startup (owner + 6 akun role, 15 siswa, 2 kelas, 3 rekening, pembayaran, pengeluaran, job order, interview). Kredensial: /app/memory/test_credentials.md

## Persona
Owner, Admin, Finance, HR, Guru, Marketing, Staff.

## Implemented (Sep 2026)
- Dashboard (filter hari/minggu/bulan/tahun), siswa/keuangan/operasional, chart status & arus kas, aktivitas terbaru
- Siswa: pendaftaran lengkap, pipeline status + histori, seleksi, checklist 13 dokumen + upload & expired warning, rincian biaya, profil terintegrasi
- Kelas & jadwal & enroll; Absensi (mobile), rekap otomatis; Nilai (rata-rata otomatis), Ujian + hasil
- Pembayaran cicilan → transaksi pemasukan otomatis, kwitansi cetak/PDF, koreksi wajib alasan (audit), tunggakan (terlambat/hari ini/akan jatuh tempo)
- Keuangan: rekening & saldo otomatis, pemasukan/pengeluaran + bukti, per kategori, rekonsiliasi dengan selisih & alasan
- SDM: guru & karyawan (gaji/honor/kontrak); Job Order + matching (usia/JK/JLPT) + interview → status siswa otomatis
- Laporan (siswa/keuangan/SDM/pelatihan) ekspor CSV & cetak; Audit trail; Notifikasi in-app; Search global; Pengguna & role

## Backlog
- P1: Gaji/honor otomatis (payroll), absensi karyawan, cuti, approval pengeluaran berjenjang, checklist keberangkatan, modul alumni detail
- P2: Notifikasi WhatsApp, portal siswa & orang tua, ekspor Excel asli (xlsx)/PDF server-side, partial-update model untuk PUT payments/transactions
