import type { LucideIcon } from "lucide-react";
import { AlertCircle, CheckCircle2, Inbox, LoaderCircle } from "lucide-react";

export function PageHeader({ eyebrow, title, description, action }: Readonly<{ eyebrow?: string; title: string; description?: string; action?: React.ReactNode }>) {
  return <div className="page-heading"><div className="page-heading-copy">{eyebrow && <p className="page-eyebrow">{eyebrow}</p>}<h1>{title}</h1>{description && <p className="page-description">{description}</p>}</div>{action && <div className="page-heading-action">{action}</div>}</div>;
}

export function StatCard({ label, value, note, tone = "blue", icon: Icon, footnote }: Readonly<{ label: string; value: number | string; note?: string; tone?: "blue" | "green" | "amber" | "violet"; icon?: LucideIcon; footnote?: string }>) {
  return <article className={`stat-card stat-${tone}`}>
    <div className="stat-card-top"><span className="stat-label">{label}</span>{Icon && <span className="stat-icon"><Icon size={18} strokeWidth={1.8} /></span>}</div>
    <strong className="stat-value">{value}</strong>
    {(note || footnote) && <div className="stat-note">{note && <span>{note}</span>}{footnote && <small>{footnote}</small>}</div>}
  </article>;
}

export function ErrorBanner({ message, onRetry }: Readonly<{ message: string; onRetry?: () => void }>) {
  return <div className="alert alert-error" role="alert"><AlertCircle size={18} /><span>{message}</span>{onRetry && <button className="text-button" type="button" onClick={onRetry}>Try again</button>}</div>;
}

export function SuccessBanner({ message }: Readonly<{ message: string }>) {
  return <div className="alert alert-success" role="status"><CheckCircle2 size={18} /><span>{message}</span></div>;
}

export function LoadingState({ label = "Loading records..." }: Readonly<{ label?: string }>) {
  return <div className="loading-state" role="status"><LoaderCircle className="loading-spinner" size={22} /><span>{label}</span></div>;
}

export function EmptyState({ title, message, action }: Readonly<{ title: string; message: string; action?: React.ReactNode }>) {
  return <div className="empty-state"><span className="empty-state-icon"><Inbox size={23} /></span><strong>{title}</strong><p>{message}</p>{action}</div>;
}
