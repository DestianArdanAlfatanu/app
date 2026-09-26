import { useState } from "react";
import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

export default function AppLayout() {
  const { user, checking } = useAuth();
  const [open, setOpen] = useState(false);
  if (checking) return <div className="min-h-screen flex items-center justify-center text-slate-500 text-sm">Memuat...</div>;
  if (!user) return <Navigate to="/login" replace />;
  if (user.role === "student") return <Navigate to="/portal" replace />;
  return (
    <div className="min-h-screen bg-[#F8FAFC]">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="lg:pl-[260px] flex flex-col min-h-screen">
        <Header onMenu={() => setOpen(true)} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-[1500px] w-full mx-auto"><Outlet /></main>
      </div>
    </div>
  );
}
