"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Boxes, CalendarClock, CheckCircle2, CircleDollarSign, Clock3, PackageCheck, PackageOpen, Wrench } from "lucide-react";
import { useAuth } from "@/components/auth-provider";
import { EmptyState, ErrorBanner, LoadingState, PageHeader, StatCard } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";
import type { Asset, Notification, Page, WorkOrder } from "@/lib/types";

type ManagerDashboard = { total_assets: number; available_assets: number; assigned_assets: number; assets_in_repair: number; open_work_orders: number; overdue_work_orders: number; maintenance_due: number; warranties_expiring_30_days: number };
type PersonalOverview = { assigned_assets: number; requested_work_orders: number; assigned_work_orders: number; unread_notifications: number };
type Depreciation = { company_currency: string; total_book_value: string; total_cost: string };

function currency(value: string, code: string) {
  return new Intl.NumberFormat(undefined, { style: "currency", currency: code, maximumFractionDigits: 0 }).format(Number(value));
}

async function loadAllAssets() {
  const first = await api.get<Page<Asset>>("/assets?page=1&page_size=100");
  const pages = await Promise.all(Array.from({ length: Math.ceil(first.total / first.page_size) - 1 }, (_, index) => api.get<Page<Asset>>(`/assets?page=${index + 2}&page_size=100`)));
  return [...first.items, ...pages.flatMap((page) => page.items)];
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [managerData, setManagerData] = useState<ManagerDashboard | null>(null);
  const [personalData, setPersonalData] = useState<PersonalOverview | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [updates, setUpdates] = useState<Notification[]>([]);
  const [bookValue, setBookValue] = useState("0");
  const [currencyCode, setCurrencyCode] = useState("INR");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const isManager = user?.role === "administrator" || user?.role === "asset_manager";

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [overview, notificationPage] = await Promise.all([
        api.get<Page<Notification>>("/notifications?page_size=5"),
        isManager ? api.get<ManagerDashboard>("/reports/dashboard") : api.get<PersonalOverview>("/reports/overview"),
      ]);
      setUpdates(overview.items);
      if (isManager) {
        const [assetRows, ordersPage, depreciation] = await Promise.all([
          loadAllAssets(), api.get<Page<WorkOrder>>("/work-orders?page_size=100"), api.get<Depreciation>("/reports/depreciation?page_size=1"),
        ]);
        setManagerData(notificationPage as ManagerDashboard);
        setPersonalData(null);
        setAssets(assetRows);
        setOrders(ordersPage.items);
        setBookValue(depreciation.total_book_value);
        setCurrencyCode(depreciation.company_currency);
      } else {
        setPersonalData(notificationPage as PersonalOverview);
        setManagerData(null);
        setAssets([]); setOrders([]);
      }
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Dashboard data could not be loaded.");
    } finally { setLoading(false); }
  }, [isManager]);

  useEffect(() => { let alive = true; queueMicrotask(() => { if (alive) void load(); }); return () => { alive = false; }; }, [load]);

  const distribution = useMemo(() => {
    const counts = new Map<string, number>();
    for (const asset of assets) counts.set(asset.category_name, (counts.get(asset.category_name) ?? 0) + 1);
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [assets]);
  const maxDistribution = Math.max(1, ...distribution.map(([, count]) => count));
  const pending = orders.filter((order) => order.status === "open").slice(0, 4);
  const total = managerData?.total_assets ?? 0;
  const availableAngle = total ? managerData!.available_assets / total * 360 : 0;
  const assignedAngle = total ? availableAngle + managerData!.assigned_assets / total * 360 : 0;
  const repairAngle = total ? assignedAngle + managerData!.assets_in_repair / total * 360 : 0;

  return <div className="page-stack">
    <PageHeader eyebrow="Workspace overview" title={`Good ${getDayPart()}, ${user?.full_name.split(" ")[0] ?? "there"}`} description="A real-time snapshot of your asset portfolio and maintenance operations." action={isManager && <Link className="button button-secondary" href="/reports"><Activity size={15} /> View reports</Link>} />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}
    {loading ? <LoadingState label="Loading live operational data..." /> : managerData ? <>
      <section className="stat-grid" aria-label="Asset portfolio summary">
        <StatCard label="Total assets" value={managerData.total_assets.toLocaleString()} note="In the asset register" icon={Boxes} />
        <StatCard label="Available" value={managerData.available_assets.toLocaleString()} note="Ready to allocate" tone="green" icon={PackageOpen} />
        <StatCard label="Assigned" value={managerData.assigned_assets.toLocaleString()} note="Currently in custody" tone="violet" icon={PackageCheck} />
        <StatCard label="Under maintenance" value={managerData.assets_in_repair.toLocaleString()} note={`${managerData.open_work_orders} open work orders`} tone="amber" icon={Wrench} />
      </section>

      <section className="stat-grid stat-grid-secondary" aria-label="Value and attention summary">
        <StatCard label="Current book value" value={currency(bookValue, currencyCode)} note={`Straight-line value · ${currencyCode}`} icon={CircleDollarSign} />
        <StatCard label="Overdue work orders" value={managerData.overdue_work_orders} note="Require follow-up" tone="amber" icon={Clock3} />
        <StatCard label="Preventive maintenance due" value={managerData.maintenance_due} note="Scheduled for today or earlier" icon={CalendarClock} />
        <StatCard label="Warranties expiring" value={managerData.warranties_expiring_30_days} note="Within the next 30 days" tone="violet" icon={CheckCircle2} />
      </section>

      <section className="dashboard-grid">
        <div className="dashboard-main">
          <article className="card card-pad chart-card">
            <div className="section-heading"><div><h2>Asset status</h2><p>Current lifecycle state across the asset register.</p></div><Link className="text-link" href="/assets">View register <ArrowRight size={14} /></Link></div>
            <div className="asset-mix">
              <div className="donut-chart" style={{ "--available-angle": `${availableAngle}deg`, "--assigned-angle": `${assignedAngle}deg`, "--repair-angle": `${repairAngle}deg` } as React.CSSProperties} role="img" aria-label={`${managerData.total_assets} total assets, ${managerData.available_assets} available, ${managerData.assigned_assets} assigned, ${managerData.assets_in_repair} under maintenance`}>
                <div className="donut-center"><strong>{managerData.total_assets.toLocaleString()}</strong><span>Total assets</span></div>
              </div>
              <div className="legend-list">
                <Legend color="#326be5" label="Available" value={managerData.available_assets} />
                <Legend color="#755ed4" label="Assigned" value={managerData.assigned_assets} />
                <Legend color="#df9a37" label="Under maintenance" value={managerData.assets_in_repair} />
                <Legend color="#e6ebf2" label="Other status" value={Math.max(0, total - managerData.available_assets - managerData.assigned_assets - managerData.assets_in_repair)} />
              </div>
            </div>
          </article>
          <article className="card card-pad chart-card">
            <div className="section-heading"><div><h2>Distribution by category</h2><p>Asset counts grouped by registered category.</p></div><span className="subtle-count">{assets.length.toLocaleString()} records loaded</span></div>
            {assets.length === 0 ? <div className="distribution-empty">Category distribution appears when assets are registered.</div> : distribution.length === 0 ? <div className="distribution-empty">No categorized assets to display.</div> : <div className="distribution-list">{distribution.map(([name, count]) => <div className="distribution-row" key={name}><span className="distribution-label" title={name}>{name}</span><div className="distribution-track"><div className="distribution-fill" style={{ width: `${Math.max(4, count / maxDistribution * 100)}%` }} /></div><strong className="distribution-count">{count}</strong></div>)}</div>}
          </article>
        </div>
        <aside className="dashboard-aside">
          <article className="card card-pad">
            <div className="section-heading"><div><h2>Pending maintenance</h2><p>Open requests needing coordination.</p></div><span className="count-pill">{orders.filter((order) => order.status === "open").length}</span></div>
            {pending.length === 0 ? <EmptyState title="No pending requests" message="Open work requests will appear here." /> : <div className="pending-list">{pending.map((order) => <div className="pending-item" key={order.id}><div><strong>{order.title}</strong><small>{order.asset_tag} · {order.priority} priority</small></div><span className={`badge ${order.priority === "critical" || order.priority === "high" ? "badge-amber" : "badge-blue"}`}>{order.status.replaceAll("_", " ")}</span></div>)}</div>}
            <Link className="card-link-footer" href="/work-orders">Open maintenance queue <ArrowRight size={14} /></Link>
          </article>
          <article className="card card-pad">
            <div className="section-heading"><div><h2>Recent activity</h2><p>Latest updates sent to your account.</p></div><Link className="icon-action" href="/notifications" aria-label="View all notifications"><ArrowRight size={16} /></Link></div>
            {updates.length === 0 ? <EmptyState title="No recent updates" message="When activity needs your attention, it will appear here." /> : <div className="activity-list">{updates.slice(0, 4).map((item) => <div className="activity-row" key={item.id}><span className="activity-icon"><Activity size={14} /></span><div><strong>{item.title}</strong><p>{item.message}</p><time>{new Date(item.created_at).toLocaleString()}</time></div></div>)}</div>}
          </article>
        </aside>
      </section>
    </> : personalData ? <>
      <section className="stat-grid" aria-label="Personal work summary">
        <StatCard label="Assets assigned to you" value={personalData.assigned_assets} note="Active allocations" icon={PackageCheck} tone="green" />
        <StatCard label="Requests submitted" value={personalData.requested_work_orders} note="Maintenance requests" icon={Wrench} />
        <StatCard label="Work assigned to you" value={personalData.assigned_work_orders} note="Technician assignments" icon={CalendarClock} tone="violet" />
        <StatCard label="Unread notifications" value={personalData.unread_notifications} note="Updates to review" icon={Activity} tone="amber" />
      </section>
      <section className="dashboard-grid">
        <article className="card card-pad"><div className="section-heading"><div><h2>Your latest updates</h2><p>Recent notifications for your account.</p></div><Link className="text-link" href="/notifications">View all <ArrowRight size={14} /></Link></div>{updates.length === 0 ? <EmptyState title="Nothing needs your attention" message="New assignments and maintenance updates will appear here." /> : <div className="activity-list">{updates.map((item) => <div className="activity-row" key={item.id}><span className="activity-icon"><Activity size={14} /></span><div><strong>{item.title}</strong><p>{item.message}</p><time>{new Date(item.created_at).toLocaleString()}</time></div></div>)}</div>}</article>
        <article className="card card-pad"><div className="section-heading"><div><h2>Your workspace</h2><p>Quick access to the work available to your role.</p></div></div><div className="quick-link-list"><Link href="/assets"><span className="quick-link-icon"><Boxes size={17} /></span><span><strong>Browse assets</strong><small>Find an asset or review your allocations</small></span><ArrowRight size={15} /></Link><Link href="/work-orders"><span className="quick-link-icon"><Wrench size={17} /></span><span><strong>Maintenance</strong><small>Submit or review maintenance work</small></span><ArrowRight size={15} /></Link></div></article>
      </section>
    </> : null}
  </div>;
}

function Legend({ color, label, value }: Readonly<{ color: string; label: string; value: number }>) {
  return <div className="legend-item"><span className="legend-label"><span className="legend-dot" style={{ "--legend-color": color } as React.CSSProperties} />{label}</span><strong>{value.toLocaleString()}</strong></div>;
}

function getDayPart() {
  const hour = new Date().getHours();
  return hour < 12 ? "morning" : hour < 18 ? "afternoon" : "evening";
}
