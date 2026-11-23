"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Notification } from "@/lib/types";

const navigation = [
  { href: "/dashboard", label: "Overview", roles: ["administrator", "asset_manager", "technician", "employee"] },
  { href: "/assets", label: "Assets", roles: ["administrator", "asset_manager", "technician", "employee"] },
  { href: "/work-orders", label: "Work orders", roles: ["administrator", "asset_manager", "technician", "employee"] },
  { href: "/vendors", label: "Vendors", roles: ["administrator", "asset_manager"] },
  { href: "/reports", label: "Reports", roles: ["administrator", "asset_manager"] },
  { href: "/users", label: "Users", roles: ["administrator"] },
];

function NotificationMenu() {
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    try {
      const result = await api.get<{ items: Notification[]; total: number }>("/notifications?page_size=8");
      setItems(result.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Notifications could not be loaded.");
    }
  }

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, []);

  async function markRead(id: string) {
    try {
      await api.post<void>(`/notifications/${id}/read`);
      setItems((current) => current.map((item) => item.id === id ? { ...item, read_at: new Date().toISOString() } : item));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Notification could not be updated.");
    }
  }

  const unread = items.filter((item) => !item.read_at).length;
  return (
    <div className="notification-wrap">
      <button className="icon-button" type="button" aria-expanded={open} aria-label={`Notifications, ${unread} unread`} onClick={() => { setOpen((value) => !value); if (!open) void load(); }}>
        <span aria-hidden="true">♧</span>{unread > 0 && <span className="notification-count">{unread}</span>}
      </button>
      {open && <section className="notification-panel" aria-label="Notifications">
        <div className="panel-heading"><strong>Notifications</strong><button className="text-button" onClick={() => void load()} type="button">Refresh</button></div>
        {error && <p className="alert alert-error">{error}</p>}
        {items.length === 0 && !error ? <p className="empty-state">You’re all caught up.</p> : items.map((item) => (
          <article className={`notification-item ${item.read_at ? "is-read" : ""}`} key={item.id}>
            <p className="notification-title">{item.title}</p><p className="notification-copy">{item.message}</p>
            {!item.read_at && <button type="button" className="text-button" onClick={() => void markRead(item.id)}>Mark read</button>}
          </article>
        ))}
      </section>}
    </div>
  );
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const { user, loading, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading || !user) return <main className="loading-screen"><span className="spinner" aria-hidden="true" /> <span>Loading your workspace…</span></main>;

  const links = navigation.filter((item) => item.roles.includes(user.role));
  return (
    <div className="app-frame">
      <aside className="sidebar">
        <Link className="brand-lockup" href="/dashboard"><span className="brand-mark">E</span><span><strong>EAMMS</strong><small>Operations workspace</small></span></Link>
        <nav aria-label="Main navigation" className="main-nav">
          <p className="nav-caption">Workspace</p>
          {links.map((item) => <Link className={`nav-link ${pathname === item.href ? "active" : ""}`} href={item.href} key={item.href}>{item.label}</Link>)}
        </nav>
        <div className="sidebar-footer"><span className="status-dot" /> All systems operational</div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="mobile-brand"><span className="brand-mark">E</span><strong>EAMMS</strong></div>
          <div className="topbar-spacer" />
          <NotificationMenu />
          <div className="user-chip"><span className="avatar">{user.full_name.slice(0, 1).toUpperCase()}</span><span className="user-chip-copy"><strong>{user.full_name}</strong><small>{user.role.replaceAll("_", " ")}</small></span></div>
          <button className="button button-quiet button-small" type="button" onClick={async () => { await logout(); router.replace("/login"); }}>Sign out</button>
        </header>
        <main className="page-content">{children}</main>
      </div>
    </div>
  );
}
