"use client";

import { useCallback, useEffect, useState } from "react";
import { Download } from "lucide-react";
import { ErrorBanner, EmptyState, LoadingState, PageHeader, StatCard } from "@/components/page-header";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";

type Dashboard = { total_assets: number; available_assets: number; assigned_assets: number; assets_in_repair: number; open_work_orders: number; overdue_work_orders: number; maintenance_due: number; warranties_expiring_30_days: number };
type DepreciationRow = { asset_id: string; asset_tag: string; name: string; purchase_cost: string; residual_value: string; accumulated_depreciation: string; book_value: string; as_of_date: string };
type DepreciationReport = { as_of_date: string; company_currency: string; items: DepreciationRow[]; total: number; page: number; page_size: number; total_cost: string; total_accumulated_depreciation: string; total_book_value: string };
type AuditRow = { id: string; actor_id: string | null; action: string; entity_type: string; entity_id: string; details: Record<string, unknown>; created_at: string };

function todayLocal() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

export default function ReportsPage() {
  const { user } = useAuth();
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [depreciation, setDepreciation] = useState<DepreciationReport | null>(null);
  const [audit, setAudit] = useState<AuditRow[]>([]);
  const [asOfDate, setAsOfDate] = useState(todayLocal);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [exporting, setExporting] = useState(false);
  const isAdmin = user?.role === "administrator";

  const load = useCallback(async () => {
    try {
      const calls: Array<Promise<unknown>> = [
        api.get<Dashboard>("/reports/dashboard"),
        api.get<DepreciationReport>(`/reports/depreciation?as_of_date=${encodeURIComponent(asOfDate)}&page=${page}&page_size=25`),
      ];
      if (isAdmin) calls.push(api.get<AuditRow[]>("/reports/audit?page_size=100"));
      const [dashboardData, depreciationData, auditData] = await Promise.all(calls);
      setDashboard(dashboardData as Dashboard); setDepreciation(depreciationData as DepreciationReport); setAudit((auditData as AuditRow[] | undefined) ?? []);
      setError("");
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Reports could not be loaded."); }
    finally { setLoading(false); }
  }, [asOfDate, page, isAdmin]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  const currency = (amount: string) => depreciation
    ? new Intl.NumberFormat(undefined, { style: "currency", currency: depreciation.company_currency, maximumFractionDigits: 2 }).format(Number(amount))
    : amount;

  async function exportReport(path: string, filename: string) {
    setExporting(true);
    try {
      await api.download(path, filename);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "The report export could not be downloaded.");
    } finally {
      setExporting(false);
    }
  }

  return <>
    <PageHeader eyebrow="Insights" title="Reports" description="Live operational counts and straight-line asset valuation as of a selected date." />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}
    {loading && !dashboard ? <LoadingState label="Calculating current reports…" /> : dashboard && <>
      <section className="stat-grid" aria-label="Operational summary">
        <StatCard label="Assets" value={dashboard.total_assets} />
        <StatCard label="Available" value={dashboard.available_assets} tone="green" />
        <StatCard label="Assigned" value={dashboard.assigned_assets} tone="violet" />
        <StatCard label="In repair" value={dashboard.assets_in_repair} tone="amber" />
      </section>
      <section className="stat-grid stat-grid-compact section-block" aria-label="Items requiring attention">
        <StatCard label="Open work orders" value={dashboard.open_work_orders} />
        <StatCard label="Overdue work orders" value={dashboard.overdue_work_orders} tone="amber" />
        <StatCard label="Maintenance due" value={dashboard.maintenance_due} />
        <StatCard label="Warranties expiring in 30 days" value={dashboard.warranties_expiring_30_days} tone="violet" />
      </section>
      <section className="card card-pad section-block">
        <div className="section-heading"><div><h2>Straight-line depreciation</h2><p className="muted">Daily proration from purchase date, capped at residual value. Currency: {depreciation?.company_currency ?? "configured company currency"}.</p></div><div className="section-actions"><label className="field"><span>As of date</span><input type="date" value={asOfDate} onChange={(event) => { setPage(1); setAsOfDate(event.target.value); }} /></label><button className="button button-secondary" type="button" disabled={exporting} onClick={() => void exportReport(`/reports/depreciation.csv?as_of_date=${encodeURIComponent(asOfDate)}`, `eamms-depreciation-${asOfDate}.csv`)}><Download size={14} />{exporting ? "Preparing..." : "Export CSV"}</button></div>
        </div>
        {depreciation && <><div className="detail-grid"><div className="detail-cell"><small>Original cost</small><strong>{currency(depreciation.total_cost)}</strong></div><div className="detail-cell"><small>Accumulated depreciation</small><strong>{currency(depreciation.total_accumulated_depreciation)}</strong></div><div className="detail-cell"><small>Current book value</small><strong>{currency(depreciation.total_book_value)}</strong></div></div>
          {depreciation.items.length === 0 ? <EmptyState title="No assets to value" message="Register assets with purchase data to calculate depreciation." /> : <div className="table-wrap section-block"><table><thead><tr><th>Asset</th><th>Cost</th><th>Residual</th><th>Accumulated</th><th>Book value</th></tr></thead><tbody>{depreciation.items.map((row) => <tr key={row.asset_id}><td><span className="table-primary">{row.asset_tag}</span><span className="table-secondary">{row.name}</span></td><td>{currency(row.purchase_cost)}</td><td>{currency(row.residual_value)}</td><td>{currency(row.accumulated_depreciation)}</td><td className="table-primary">{currency(row.book_value)}</td></tr>)}</tbody></table></div>}
          {depreciation.total > depreciation.page_size && <div className="form-actions"><button className="button button-secondary button-small" type="button" disabled={page <= 1} onClick={() => setPage((current) => current - 1)}>Previous</button><span className="muted">Page {depreciation.page} of {Math.ceil(depreciation.total / depreciation.page_size)}</span><button className="button button-secondary button-small" type="button" disabled={page * depreciation.page_size >= depreciation.total} onClick={() => setPage((current) => current + 1)}>Next</button></div>}</>}
      </section>
      {isAdmin && <section className="card card-pad section-block"><div className="section-heading"><div><h2>Audit trail</h2><p className="muted">Recent administrative events. Sensitive credentials are never recorded.</p></div><button className="button button-secondary" type="button" disabled={exporting} onClick={() => void exportReport("/reports/audit.csv", "eamms-audit.csv")}><Download size={14} />{exporting ? "Preparing..." : "Export CSV"}</button></div>
        {audit.length === 0 ? <EmptyState title="No audit events" message="Audited changes will appear here." /> : <div className="table-wrap"><table><thead><tr><th>Time</th><th>Action</th><th>Record</th><th>Actor</th></tr></thead><tbody>{audit.map((row) => <tr key={row.id}><td>{new Date(row.created_at).toLocaleString()}</td><td><span className="table-primary">{row.action}</span></td><td>{row.entity_type} · {row.entity_id.slice(0, 8)}</td><td>{row.actor_id?.slice(0, 8) ?? "System"}</td></tr>)}</tbody></table></div>}
      </section>}
    </>}
  </>;
}
