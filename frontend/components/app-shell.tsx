"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Activity, Bell, Boxes, ChevronLeft, ChevronRight,
  LayoutDashboard, LogOut, MapPinned, Menu, Search,
  ShieldCheck, Truck, Wrench, SunMoon, Building2,
} from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Notification, Page } from "@/lib/types";
import { useTheme } from "@/components/theme-provider";
import type { ThemeMode } from "@/lib/theme";

const links = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard, group: "Workspace", roles: ["administrator", "asset_manager", "technician", "employee"] },
  { href: "/assets", label: "Asset register", icon: Boxes, group: "Workspace", roles: ["administrator", "asset_manager", "technician", "employee"] },
  { href: "/catalogs", label: "Categories & locations", icon: MapPinned, group: "Workspace", roles: ["administrator", "asset_manager"] },
  { href: "/work-orders", label: "Maintenance", icon: Wrench, group: "Workspace", roles: ["administrator", "asset_manager", "technician", "employee"] },
  { href: "/vendors", label: "Vendors", icon: Truck, group: "Workspace", roles: ["administrator", "asset_manager"] },
  { href: "/reports", label: "Reports & audit", icon: Activity, group: "Insights", roles: ["administrator", "asset_manager"] },
  { href: "/users", label: "People & access", icon: ShieldCheck, group: "Administration", roles: ["administrator"] },
  { href: "/departments", label: "Departments", icon: Building2, group: "Administration", roles: ["administrator"] },
  { href: "/notifications", label: "Notifications", icon: Bell, group: "Administration", roles: ["administrator", "asset_manager", "technician", "employee"] },
] as const;

const routeTitles: Record<string, string> = {
  "/dashboard": "Overview", "/assets": "Asset register", "/catalogs": "Categories & locations",
  "/work-orders": "Maintenance", "/vendors": "Vendors", "/reports": "Reports & audit",
  "/users": "People & access", "/departments": "Departments", "/notifications": "Notifications",
};

function initials(name: string) {
  return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase();
}

function NotificationPopover({ onNavigate }: Readonly<{ onNavigate: () => void }>) {
  const [items, setItems] = useState<Notification[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const unread = useMemo(() => items.filter((item) => !item.read_at).length, [items]);

  const load = useCallback(async () => {
    try {
      const result = await api.get<Page<Notification>>("/notifications?page_size=6");
      setItems(result.items);
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Notifications could not be loaded.");
    }
  }, []);

  useEffect(() => { queueMicrotask(() => void load()); }, [load]);

  async function markRead(item: Notification) {
    try {
      await api.post<void>(`/notifications/${item.id}/read`);
      setItems((current) => current.map((row) => row.id === item.id ? { ...row, read_at: new Date().toISOString() } : row));
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Notification could not be updated.");
    }
  }

  return <div className="notification-wrap">
    <button className={`icon-button notification-trigger ${open ? "is-open" : ""}`} type="button" aria-label={`Notifications, ${unread} unread`} aria-expanded={open} onClick={() => { setOpen((value) => !value); if (!open) void load(); }}>
      <Bell size={19} strokeWidth={1.8} />{unread > 0 && <span className="notification-count">{unread > 9 ? "9+" : unread}</span>}
    </button>
    {open && <>
      <button className="popover-dismiss" aria-label="Close notifications" type="button" onClick={() => setOpen(false)} />
      <section className="notification-panel" aria-label="Recent notifications">
        <div className="popover-heading"><div><strong>Notifications</strong><span>{unread ? `${unread} unread` : "You're all caught up"}</span></div><button className="icon-button icon-button-small" type="button" aria-label="Refresh notifications" onClick={() => void load()}><Activity size={16} /></button></div>
        {error && <p className="inline-error" role="alert">{error}</p>}
        {!error && items.length === 0 && <div className="popover-empty"><Bell size={22} /><strong>No notifications yet</strong><span>System updates will appear here.</span></div>}
        <div className="notification-list">{items.map((item) => <article className={`notification-item ${item.read_at ? "is-read" : ""}`} key={item.id}>
          <span className="notification-marker" aria-hidden="true" />
          <div><p className="notification-title">{item.title}</p><p className="notification-copy">{item.message}</p><time>{new Date(item.created_at).toLocaleString()}</time>{!item.read_at && <button className="text-button" type="button" onClick={() => void markRead(item)}>Mark as read</button>}</div>
        </article>)}</div>
        <Link className="popover-footer" href="/notifications" onClick={() => { setOpen(false); onNavigate(); }}>View all notifications <ChevronRight size={15} /></Link>
      </section>
    </>}
  </div>;
}

export function AppShell({ children }: Readonly<{ children: React.ReactNode }>) {
  const { user, logout } = useAuth();
  const { mode, setMode } = useTheme();
  const router = useRouter();
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [query, setQuery] = useState("");
  const role = user?.role ?? "employee";
  const visibleLinks = links.filter((item) => (item.roles as readonly string[]).includes(role));
  const groups = [...new Set(visibleLinks.map((item) => item.group))];
  const currentTitle = routeTitles[pathname] ?? "EAMMS";

  function searchAssets(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/assets?search=${encodeURIComponent(value)}` : "/assets");
    window.dispatchEvent(new CustomEvent("eamms:asset-search", { detail: value }));
  }

  async function signOut() {
    await logout();
    router.replace("/login");
  }

  return <div className={`app-frame ${collapsed ? "sidebar-collapsed" : ""} ${mobileOpen ? "mobile-nav-open" : ""}`}>
    <button className="mobile-scrim" type="button" aria-label="Close navigation" onClick={() => setMobileOpen(false)} />
    <aside className="sidebar" aria-label="Primary navigation">
      <Link className="brand-lockup" href="/dashboard" aria-label="EAMMS home">
        <span className="brand-mark"><Boxes size={21} strokeWidth={2.1} /></span>
        <span className="brand-copy"><strong>EAMMS</strong><small>Asset operations</small></span>
        <span className="brand-caret"><ChevronRight size={15} /></span>
      </Link>
      <div className="workspace-switcher"><span className="workspace-avatar">E</span><span className="workspace-copy"><strong>EAMMS Workspace</strong><small>Company workspace</small></span><ChevronRight className="workspace-chevron" size={15} /></div>
      <nav className="sidebar-nav">
        {groups.map((group) => <div className="nav-group" key={group}>
          <p className="nav-caption">{group}</p>
          {visibleLinks.filter((item) => item.group === group).map(({ href, label, icon: Icon }) => <Link className={`nav-link ${pathname === href ? "active" : ""}`} href={href} key={href} title={collapsed ? label : undefined} aria-current={pathname === href ? "page" : undefined} onClick={() => setMobileOpen(false)}>
          <Icon size={18} strokeWidth={1.8} /><span className="nav-label">{label}</span>
          </Link>)}
        </div>)}
      </nav>
      <div className="sidebar-bottom">
        <label className="theme-control" title="Choose appearance"><SunMoon size={17} /><span className="nav-label">Appearance</span><select aria-label="Color theme" value={mode} onChange={(event) => setMode(event.target.value as ThemeMode)}><option value="light">Light</option><option value="dark">Dark</option><option value="system">System</option></select></label>
        <div className="nav-link sidebar-help" title={collapsed ? "Contact your administrator" : undefined}><span className="nav-label">Contact your administrator</span></div>
      </div>
      <button className="collapse-button" type="button" aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"} onClick={() => setCollapsed((value) => !value)}>{collapsed ? <ChevronRight size={17} /> : <ChevronLeft size={17} />}<span className="nav-label">Collapse sidebar</span></button>
    </aside>

    <div className="workspace">
      <header className="topbar">
        <button className="mobile-menu icon-button" type="button" aria-label="Open navigation" onClick={() => setMobileOpen(true)}><Menu size={20} /></button>
        <div className="topbar-location"><span className="topbar-kicker">Workspace</span><ChevronRight size={14} /><strong>{currentTitle}</strong></div>
        <form className="global-search" onSubmit={searchAssets} role="search"><Search size={17} /><input aria-label="Search assets" placeholder="Search assets, tags, serial numbers..." value={query} onChange={(event) => setQuery(event.target.value)} /></form>
        <div className="topbar-actions"><NotificationPopover onNavigate={() => setMobileOpen(false)} /><span className="topbar-divider" />
          <div className="topbar-user"><span className="avatar">{initials(user?.full_name ?? "U")}</span><span className="user-chip-copy"><strong>{user?.full_name ?? "Account"}</strong><small>{user?.role.replaceAll("_", " ")}</small></span></div>
          <button className="icon-button signout-icon" type="button" aria-label="Sign out" title="Sign out" onClick={() => void signOut()}><LogOut size={17} /></button>
        </div>
      </header>
      <main className="page-content">{children}</main>
      <footer className="workspace-footer"><span>EAMMS asset operations</span><span>Enterprise workspace</span></footer>
    </div>
  </div>;
}
