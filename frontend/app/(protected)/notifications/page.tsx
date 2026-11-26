"use client";

import { useCallback, useEffect, useState } from "react";
import { Bell, CheckCheck } from "lucide-react";
import { EmptyState, ErrorBanner, LoadingState, PageHeader } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";
import type { Notification, Page } from "@/lib/types";

export default function NotificationsPage() {
  const [items, setItems] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const load = useCallback(async () => {
    try {
      const result = await api.get<Page<Notification>>(`/notifications?page=${page}&page_size=25`);
      setItems(result.items); setTotal(result.total); setError("");
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Notifications could not be loaded."); }
    finally { setLoading(false); }
  }, [page]);
  useEffect(() => { queueMicrotask(() => void load()); }, [load]);
  async function markRead(item: Notification) {
    try { await api.post<void>(`/notifications/${item.id}/read`); setItems((current) => current.map((row) => row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row)); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Notification could not be updated."); }
  }
  return <>
    <PageHeader eyebrow="Workspace" title="Notifications" description="Account updates and operational events relevant to your work." />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}
    <section className="card card-pad section-block">
      <div className="section-heading"><div><h2>All updates</h2><p className="muted">{total} notifications</p></div><Bell size={19} className="muted-icon" /></div>
      {loading ? <LoadingState /> : items.length === 0 ? <EmptyState title="You're all caught up" message="New notifications will appear here when there are updates." /> : <div className="notification-list notification-list-page">{items.map((item) => <article className={`notification-item ${item.read_at ? "is-read" : ""}`} key={item.id}><span className="notification-marker" aria-hidden="true" /><div className="notification-body"><p className="notification-title">{item.title}</p><p className="notification-copy">{item.message}</p><time>{new Date(item.created_at).toLocaleString()}</time></div>{!item.read_at && <button className="button button-small button-secondary" type="button" onClick={() => void markRead(item)}><CheckCheck size={14} /> Mark read</button>}</article>)}</div>}
      {total > 25 && <div className="form-actions"><button className="button button-secondary button-small" type="button" disabled={page <= 1} onClick={() => setPage((value) => value - 1)}>Previous</button><span className="muted">Page {page} of {Math.ceil(total / 25)}</span><button className="button button-secondary button-small" type="button" disabled={page * 25 >= total} onClick={() => setPage((value) => value + 1)}>Next</button></div>}
    </section>
  </>;
}
