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
import ExpensePage from "@/pages/ExpensePage";
import HRPage from "@/pages/HRPage";
import JobOrdersPage from "@/pages/JobOrdersPage";
import ReportsPage from "@/pages/ReportsPage";
import AuditPage from "@/pages/AuditPage";
import UsersPage from "@/pages/UsersPage";
import FollowupPage from "@/pages/FollowupPage";
import DeparturePage from "@/pages/DeparturePage";
import WhatsAppPage from "@/pages/WhatsAppPage";
import PortalLogin, { PortalGuard } from "@/pages/portal/PortalLogin";
import PortalLayout from "@/components/portal/PortalLayout";
import PortalDashboard from "@/pages/portal/PortalDashboard";
import { PortalProfile, PortalAcademic, PortalFinance, PortalDocuments, PortalNotifications, PortalSettings } from "@/pages/portal/PortalPages";

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
            <Route path="/portal/login" element={<PortalLogin />} />
            <Route element={<PortalGuard><PortalLayout /></PortalGuard>}>
              <Route path="/portal" element={<PortalDashboard />} />
              <Route path="/portal/profile" element={<PortalProfile />} />
              <Route path="/portal/academic" element={<PortalAcademic />} />
              <Route path="/portal/finance" element={<PortalFinance />} />
              <Route path="/portal/documents" element={<PortalDocuments />} />
              <Route path="/portal/notifications" element={<PortalNotifications />} />
              <Route path="/portal/settings" element={<PortalSettings />} />
            </Route>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Guard mod="dashboard"><DashboardPage /></Guard>} />
              <Route path="/siswa" element={<Guard mod="siswa"><StudentsPage /></Guard>} />
              <Route path="/siswa/:id" element={<Guard mod="siswa"><StudentDetailPage /></Guard>} />
              <Route path="/followup" element={<Guard mod="followup"><FollowupPage /></Guard>} />
              <Route path="/kelas" element={<Guard mod="kelas"><ClassesPage /></Guard>} />
              <Route path="/absensi" element={<Guard mod="absensi"><AttendancePage /></Guard>} />
              <Route path="/nilai" element={<Guard mod="nilai"><GradesPage /></Guard>} />
              <Route path="/pembayaran" element={<Guard mod="pembayaran"><PaymentsPage /></Guard>} />
              <Route path="/keuangan" element={<Guard mod="keuangan"><FinancePage /></Guard>} />
              <Route path="/pengajuan" element={<Guard mod="expense"><ExpensePage /></Guard>} />
              <Route path="/job-order" element={<Guard mod="joborder"><JobOrdersPage /></Guard>} />
              <Route path="/departure" element={<Guard mod="departure"><DeparturePage /></Guard>} />
              <Route path="/sdm" element={<Guard mod="sdm"><HRPage /></Guard>} />
              <Route path="/laporan" element={<Guard mod="laporan"><ReportsPage /></Guard>} />
              <Route path="/audit" element={<Guard mod="audit"><AuditPage /></Guard>} />
              <Route path="/whatsapp" element={<Guard mod="whatsapp"><WhatsAppPage /></Guard>} />
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
