import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/sonner";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import AppLayout from "@/components/layout/AppLayout";
import LoginPage from "@/pages/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import StudentsPage from "@/pages/StudentsPage";
import StudentDetailPage from "@/pages/StudentDetailPage";
import ClassesPage from "@/pages/ClassesPage";
import AttendancePage from "@/pages/AttendancePage";
import GradesPage from "@/pages/GradesPage";
import PaymentsPage from "@/pages/PaymentsPage";
import FinancePage from "@/pages/FinancePage";
import HRPage from "@/pages/HRPage";
import JobOrdersPage from "@/pages/JobOrdersPage";
import ReportsPage from "@/pages/ReportsPage";
import AuditPage from "@/pages/AuditPage";
import UsersPage from "@/pages/UsersPage";

const Guard = ({ mod, children }) => {
  const { can } = useAuth();
  return can(mod) ? children : <div className="card card-pad text-sm text-slate-600" data-testid="forbidden">Anda tidak memiliki akses ke halaman ini.</div>;
};

function App() {
  return (
    <div className="App">
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route element={<AppLayout />}>
              <Route path="/" element={<DashboardPage />} />
              <Route path="/siswa" element={<StudentsPage />} />
              <Route path="/siswa/:id" element={<StudentDetailPage />} />
              <Route path="/kelas" element={<Guard mod="kelas"><ClassesPage /></Guard>} />
              <Route path="/absensi" element={<Guard mod="absensi"><AttendancePage /></Guard>} />
              <Route path="/nilai" element={<Guard mod="nilai"><GradesPage /></Guard>} />
              <Route path="/pembayaran" element={<Guard mod="pembayaran"><PaymentsPage /></Guard>} />
              <Route path="/keuangan" element={<Guard mod="keuangan"><FinancePage /></Guard>} />
              <Route path="/job-order" element={<Guard mod="joborder"><JobOrdersPage /></Guard>} />
              <Route path="/sdm" element={<Guard mod="sdm"><HRPage /></Guard>} />
              <Route path="/laporan" element={<Guard mod="laporan"><ReportsPage /></Guard>} />
              <Route path="/audit" element={<Guard mod="audit"><AuditPage /></Guard>} />
              <Route path="/pengguna" element={<Guard mod="pengguna"><UsersPage /></Guard>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster position="top-right" richColors />
      </AuthProvider>
    </div>
  );
}

export default App;
