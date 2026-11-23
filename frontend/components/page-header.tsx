export function PageHeader({ eyebrow, title, description, action }: Readonly<{ eyebrow: string; title: string; description: string; action?: React.ReactNode }>) {
  return <div className="page-header"><div><p className="eyebrow">{eyebrow}</p><h1>{title}</h1><p className="muted">{description}</p></div>{action && <div className="page-header-action">{action}</div>}</div>;
}

export function StatCard({ label, value, note, tone = "blue" }: Readonly<{ label: string; value: number | string; note?: string; tone?: "blue" | "green" | "amber" | "violet" }>) {
  return <article className={`stat-card stat-${tone}`}><p>{label}</p><strong>{value}</strong>{note && <span>{note}</span>}</article>;
}

export function ErrorBanner({ message, onRetry }: Readonly<{ message: string; onRetry?: () => void }>) {
  return <div className="alert alert-error" role="alert"><span>{message}</span>{onRetry && <button className="text-button" type="button" onClick={onRetry}>Try again</button>}</div>;
}

export function LoadingState({ label = "Loading records…" }: Readonly<{ label?: string }>) {
  return <div className="loading-inline"><span className="spinner" aria-hidden="true" />{label}</div>;
}

export function EmptyState({ title, message }: Readonly<{ title: string; message: string }>) {
  return <div className="empty-state"><span className="empty-icon" aria-hidden="true">⌕</span><strong>{title}</strong><p>{message}</p></div>;
}
