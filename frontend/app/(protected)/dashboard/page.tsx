"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/auth-provider";
import { EmptyState, ErrorBanner, LoadingState, PageHeader, StatCard } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";

type ManagerDashboard = {
  total_assets: number;
  available_assets: number;
  assigned_assets: number;
  assets_in_repair: number;
  open_work_orders: number;
  overdue_work_orders: number;
  maintenance_due: number;
  warranties_expiring_30_days: number;
};
type PersonalOverview = { assigned_assets: number; requested_work_orders: number; assigned_work_orders: number; unread_notifications: number };

export default function DashboardPage() {
  const { user } = useAuth();
  const [managerData, setManagerData] = useState<ManagerDashboard | null>(null);
  const [personalData, setPersonalData] = useState<PersonalOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const isManager = user?.role === "administrator" || user?.role === "asset_manager";

  const load = useCallback(async () => {
    try {
      if (isManager) setManagerData(await api.get<ManagerDashboard>("/reports/dashboard"));
      else setPersonalData(await api.get<PersonalOverview>("/reports/overview"));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Dashboard data could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [isManager]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  return <>
    <PageHeader eyebrow="Overview" title={`Good to see you, ${user?.full_name.split(" ")[0] ?? "there"}`} description="A current view of the assets and maintenance work you can access." />
    {loading ? <LoadingState label="Loading current operational data…" /> : error ? <ErrorBanner message={error} onRetry={() => void load()} /> : isManager && managerData ? <>
      <section className="stat-grid" aria-label="Asset and maintenance summary">
        <StatCard label="Assets in register" value={managerData.total_assets} note="All registered assets" />
        <StatCard label="Available" value={managerData.available_assets} note="Ready for allocation" tone="green" />
        <StatCard label="Assigned" value={managerData.assigned_assets} note="Currently in custody" tone="violet" />
        <StatCard label="In repair" value={managerData.assets_in_repair} note={`${managerData.open_work_orders} open work orders`} tone="amber" />
      </section>
      <section className="section-block"><div className="section-heading"><div><h2>Needs attention</h2><p className="muted">Counts are calculated from current register and schedule records.</p></div></div>
        <div className="stat-grid stat-grid-compact">
          <StatCard label="Overdue work orders" value={managerData.overdue_work_orders} tone="amber" />
          <StatCard label="Maintenance due" value={managerData.maintenance_due} />
          <StatCard label="Warranties expiring in 30 days" value={managerData.warranties_expiring_30_days} tone="violet" />
        </div>
      </section>
    </> : personalData ? <>
      <section className="stat-grid" aria-label="Personal work summary">
        <StatCard label="Assets assigned to you" value={personalData.assigned_assets} tone="green" />
        <StatCard label="Requests you submitted" value={personalData.requested_work_orders} />
        <StatCard label="Work assigned to you" value={personalData.assigned_work_orders} tone="violet" />
        <StatCard label="Unread notifications" value={personalData.unread_notifications} tone="amber" />
      </section>
      {!personalData.assigned_assets && !personalData.requested_work_orders && !personalData.assigned_work_orders && <section className="section-block"><EmptyState title="Your workspace is ready" message="Asset allocations and work assigned to you will appear here." /></section>}
    </> : null}
  </>;
}
