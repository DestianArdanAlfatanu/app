import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { STATUS_CLASSES, STATUS_LABELS, rupiah } from "@/lib/format";
import { Inbox } from "lucide-react";

export const StatusBadge = ({ status, testId }) => (
  <span data-testid={testId} className={`chip ${STATUS_CLASSES[status] || "bg-slate-100 text-slate-700 border-slate-200"}`}>
    {STATUS_LABELS[status] || status}
  </span>
);

export const PageHeader = ({ title, subtitle, jp, children }) => (
  <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4 mb-6 fade-up">
    <div className="red-bar pl-4">
      <div className="flex items-center gap-2">
        <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-900">{title}</h1>
        {jp && <span className="font-jp text-xs text-slate-400 mt-1">{jp}</span>}
      </div>
      {subtitle && <p className="text-sm text-slate-500 mt-1">{subtitle}</p>}
    </div>
    {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
  </div>
);

export const StatCard = ({ label, value, hint, icon: Icon, tone = "slate", testId, onClick }) => {
  const tones = {
    slate: "text-slate-600 bg-slate-100", red: "text-red-600 bg-red-50", green: "text-emerald-600 bg-emerald-50",
    blue: "text-blue-600 bg-blue-50", amber: "text-amber-600 bg-amber-50", indigo: "text-indigo-600 bg-indigo-50",
  };
  return (
    <div data-testid={testId} onClick={onClick} className={`card p-5 fade-up ${onClick ? "cursor-pointer hover:border-slate-300 transition-colors" : ""}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</p>
          <p className="stat-num mt-2 truncate">{value}</p>
          {hint && <p className="text-xs text-slate-500 mt-1.5">{hint}</p>}
        </div>
        {Icon && <div className={`h-10 w-10 rounded-md flex items-center justify-center shrink-0 ${tones[tone]}`}><Icon size={18} /></div>}
      </div>
    </div>
  );
};

export const Field = ({ label, children, className = "", hint }) => (
  <div className={className}>
    {label && <label className="label">{label}</label>}
    {children}
    {hint && <p className="text-xs text-slate-400 mt-1">{hint}</p>}
  </div>
);

export const Money = ({ value, className = "" }) => <span className={`mono ${className}`}>{rupiah(value)}</span>;

export const EmptyState = ({ text = "Belum ada data", testId }) => (
  <div data-testid={testId} className="flex flex-col items-center justify-center py-14 text-slate-400">
    <Inbox size={32} strokeWidth={1.5} />
    <p className="text-sm mt-3">{text}</p>
  </div>
);

export const Loading = () => (
  <div className="space-y-3" data-testid="loading">
    <div className="skeleton h-10 w-full" /><div className="skeleton h-10 w-full" /><div className="skeleton h-10 w-2/3" />
  </div>
);

export const FormDialog = ({ open, onOpenChange, title, description, children, onSubmit, submitLabel = "Simpan", loading, testId, wide, footer }) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    <DialogContent data-testid={testId} className={`bg-white max-h-[92vh] overflow-y-auto ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"}`}>
      <DialogHeader>
        <DialogTitle className="text-lg font-bold tracking-tight">{title}</DialogTitle>
        {description && <DialogDescription>{description}</DialogDescription>}
      </DialogHeader>
      <form onSubmit={(e) => { e.preventDefault(); onSubmit && onSubmit(); }} className="space-y-4">
        {children}
        {footer !== null && (
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" className="btn-outline" onClick={() => onOpenChange(false)} data-testid="dialog-cancel-btn">Batal</button>
            {onSubmit && <button type="submit" className="btn-primary" disabled={loading} data-testid="dialog-submit-btn">{loading ? "Menyimpan..." : submitLabel}</button>}
          </div>
        )}
      </form>
    </DialogContent>
  </Dialog>
);

export const Progress = ({ value, tone = "bg-emerald-500" }) => (
  <div className="h-2 w-full rounded-full bg-slate-100 overflow-hidden">
    <div className={`h-full ${tone} transition-[width]`} style={{ width: `${Math.min(100, Math.max(0, value || 0))}%` }} />
  </div>
);

export const Tabs = ({ tabs, active, onChange, testPrefix = "tab" }) => (
  <div className="flex gap-1 overflow-x-auto border-b border-slate-200 mb-5 -mx-1 px-1">
    {tabs.map((t) => (
      <button key={t.key} data-testid={`${testPrefix}-${t.key}`} onClick={() => onChange(t.key)}
        className={`px-4 py-2.5 text-sm font-medium whitespace-nowrap border-b-2 -mb-px transition-colors ${active === t.key ? "border-red-600 text-slate-900" : "border-transparent text-slate-500 hover:text-slate-800"}`}>
        {t.label}{t.count != null && <span className="ml-1.5 text-xs text-slate-400">{t.count}</span>}
      </button>
    ))}
  </div>
);
