"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorBanner, EmptyState, LoadingState, PageHeader } from "@/components/page-header";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Asset, Page, UserOption, WorkOrder } from "@/lib/types";

type Plan = { id: string; name: string; asset_id: string; interval_days: number; next_due_date: string; description: string | null; is_active: boolean };

export default function WorkOrdersPage() {
  const { user } = useAuth();
  const canManage = user?.role === "administrator" || user?.role === "asset_manager";
  const isTechnician = user?.role === "technician";
  const [orders, setOrders] = useState<WorkOrder[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [people, setPeople] = useState<UserOption[]>([]);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [resolution, setResolution] = useState<Record<string, string>>({});
  const [assignee, setAssignee] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const [page, assetPage, planList] = await Promise.all([
        api.get<Page<WorkOrder>>("/work-orders?page_size=100"),
        api.get<Page<Asset>>("/assets?page_size=100"),
        api.get<Plan[]>("/maintenance-plans"),
      ]);
      setOrders(page.items); setTotal(page.total); setAssets(assetPage.items); setPlans(planList);
      if (canManage) setPeople(await api.get<UserOption[]>("/users/directory"));
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Maintenance records could not be loaded.");
    } finally { setLoading(false); }
  }, [canManage]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  async function perform<T>(operation: () => Promise<T>, message: string): Promise<boolean> {
    setError(""); setSuccess("");
    try { await operation(); setSuccess(message); await load(); return true; }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "The requested maintenance operation failed."); return false; }
  }

  async function createOrder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    const created = await perform(() => api.post<WorkOrder>("/work-orders", {
      asset_id: values.get("asset_id"), plan_id: values.get("plan_id") || null,
      title: values.get("title"), description: values.get("description") || null,
      priority: values.get("priority"), due_date: values.get("due_date") || null,
    }), "Maintenance request submitted.");
    if (created) form.reset();
  }

  async function createPlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    const created = await perform(() => api.post<Plan>("/maintenance-plans", {
      name: values.get("name"), asset_id: values.get("asset_id"), interval_days: Number(values.get("interval_days")),
      next_due_date: values.get("next_due_date"), description: values.get("description") || null,
    }), "Preventive maintenance plan created.");
    if (created) form.reset();
  }

  return <>
    <PageHeader eyebrow="Maintenance" title="Work orders" description="Submit requests, coordinate assignments, and record completed maintenance." />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}
    {success && <p className="alert alert-success" role="status">{success}</p>}
    <section className="section-block card card-pad">
      <div className="section-heading"><div><h2>Request maintenance</h2><p className="muted">Requests are saved to the work order register and routed to operations.</p></div></div>
      <form className="form-grid form-grid-3" onSubmit={(event) => void createOrder(event)}>
        <label className="field"><span>Asset</span><select name="asset_id" defaultValue="" required><option value="" disabled>Select an asset</option>{assets.filter((asset) => asset.status !== "retired").map((asset) => <option key={asset.id} value={asset.id}>{asset.asset_tag} · {asset.name}</option>)}</select></label>
        <label className="field"><span>Related plan <span className="field-hint">Optional</span></span><select name="plan_id" defaultValue=""><option value="">Unscheduled request</option>{plans.filter((plan) => plan.is_active).map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}</select></label>
        <label className="field"><span>Priority</span><select name="priority" defaultValue="medium"><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
        <label className="field"><span>Title</span><input name="title" required maxLength={180} placeholder="Describe the issue or task" /></label>
        <label className="field"><span>Due date <span className="field-hint">Optional</span></span><input name="due_date" type="date" /></label>
        <div className="field"><span>&nbsp;</span><button className="button button-primary" type="submit">Submit request</button></div>
        <label className="field" style={{ gridColumn: "1 / -1" }}><span>Description</span><textarea name="description" maxLength={10000} placeholder="Add symptoms, checks, or context" /></label>
      </form>
    </section>

    {canManage && <section className="section-block card card-pad">
      <div className="section-heading"><div><h2>Preventive schedules</h2><p className="muted">A completed planned order advances its due date by the configured interval.</p></div></div>
      <form className="form-grid form-grid-3" onSubmit={(event) => void createPlan(event)}>
        <label className="field"><span>Plan name</span><input name="name" required maxLength={180} /></label>
        <label className="field"><span>Asset</span><select name="asset_id" defaultValue="" required><option value="" disabled>Select an asset</option>{assets.filter((asset) => asset.status !== "retired").map((asset) => <option key={asset.id} value={asset.id}>{asset.asset_tag} · {asset.name}</option>)}</select></label>
        <label className="field"><span>Interval in days</span><input name="interval_days" type="number" min="1" max="3650" required /></label>
        <label className="field"><span>Next due date</span><input name="next_due_date" type="date" required /></label>
        <label className="field"><span>Description</span><input name="description" maxLength={5000} /></label>
        <div className="field"><span>&nbsp;</span><button className="button button-secondary" type="submit">Create plan</button></div>
      </form>
      {plans.length > 0 && <div className="table-wrap section-block"><table><thead><tr><th>Plan</th><th>Asset</th><th>Interval</th><th>Next due</th><th>Status</th></tr></thead><tbody>{plans.map((plan) => <tr key={plan.id}><td className="table-primary">{plan.name}</td><td>{assets.find((asset) => asset.id === plan.asset_id)?.asset_tag ?? "—"}</td><td>Every {plan.interval_days} days</td><td>{plan.next_due_date}</td><td><span className={`badge ${plan.is_active ? "badge-green" : ""}`}>{plan.is_active ? "Active" : "Inactive"}</span></td></tr>)}</tbody></table></div>}
    </section>}

    <section className="section-block card card-pad">
      <div className="section-heading"><div><h2>Work queue</h2><p className="muted">{total} {total === 1 ? "record" : "records"} available to your role.</p></div></div>
      {loading ? <LoadingState /> : orders.length === 0 ? <EmptyState title="No work orders yet" message="Maintenance requests and assignments will appear here." /> :
        <div className="table-wrap"><table><thead><tr><th>Work item</th><th>Asset</th><th>Priority</th><th>Status</th><th>Due</th>{(canManage || isTechnician) && <th>Assignment / action</th>}</tr></thead><tbody>{orders.map((order) => <tr key={order.id}>
          <td><span className="table-primary">{order.title}</span><span className="table-secondary">{order.description || "No extra details"}</span></td>
          <td>{order.asset_tag}</td><td><span className={`badge ${order.priority === "critical" || order.priority === "high" ? "badge-amber" : ""}`}>{order.priority}</span></td>
          <td><span className={`badge ${order.status === "completed" ? "badge-green" : order.status === "in_progress" ? "badge-blue" : ""}`}>{order.status.replaceAll("_", " ")}</span></td>
          <td>{order.due_date ?? "—"}</td>
          {(canManage || isTechnician) && <td><div className="table-actions">
            {canManage && !["completed", "cancelled"].includes(order.status) && <><select aria-label={`Assign ${order.title}`} value={assignee[order.id] ?? order.assigned_to_id ?? ""} onChange={(event) => setAssignee((current) => ({ ...current, [order.id]: event.target.value }))}><option value="">Assign technician…</option>{people.filter((person) => person.role === "technician").map((person) => <option value={person.id} key={person.id}>{person.full_name}</option>)}</select><button className="button button-small button-secondary" type="button" disabled={!assignee[order.id]} onClick={() => void perform(() => api.patch(`/work-orders/${order.id}/assign`, { assigned_to_id: assignee[order.id] }), "Work order assigned.")}>Assign</button></>}
            {order.status === "open" && (canManage || (isTechnician && order.assigned_to_id === user?.id)) && <button className="button button-small button-secondary" type="button" onClick={() => void perform(() => api.patch(`/work-orders/${order.id}/status`, { status: "in_progress" }), "Work started.")}>Start</button>}
            {order.status === "in_progress" && (canManage || (isTechnician && order.assigned_to_id === user?.id)) && <><input aria-label={`Resolution for ${order.title}`} placeholder="Completion resolution" value={resolution[order.id] ?? ""} onChange={(event) => setResolution((current) => ({ ...current, [order.id]: event.target.value }))} /><button className="button button-small button-primary" type="button" disabled={!resolution[order.id]?.trim()} onClick={() => void perform(() => api.patch(`/work-orders/${order.id}/status`, { status: "completed", resolution: resolution[order.id] }), "Work order completed.")}>Complete</button></>}
          </div></td>}
        </tr>)}</tbody></table></div>}
    </section>
  </>;
}
