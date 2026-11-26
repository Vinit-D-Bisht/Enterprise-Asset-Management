"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorBanner, EmptyState, LoadingState, PageHeader } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";
import type { Department, Page, User } from "@/lib/types";

const roles: Array<User["role"]> = ["administrator", "asset_manager", "technician", "employee"];

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [departments, setDepartments] = useState<Department[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    try { const [result, departmentRows] = await Promise.all([api.get<Page<User>>("/users?page_size=100"), api.get<Department[]>("/departments")]); setUsers(result.items); setTotal(result.total); setDepartments(departmentRows); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "User records could not be loaded."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  async function createUser(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    setError(""); setSuccess("");
    try {
      await api.post<User>("/users", { full_name: data.get("full_name"), email: data.get("email"), password: data.get("password"), role: data.get("role"), department_id: data.get("department_id") || null });
      form.reset(); setSuccess("User created. Share initial credentials through your approved secure channel."); await load();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "User could not be created."); }
  }

  async function update(user: User, changes: Partial<Pick<User, "role" | "is_active" | "department_id">>) {
    setError(""); setSuccess("");
    try { await api.patch(`/users/${user.id}`, changes); setSuccess(`${user.full_name} updated.`); await load(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "User could not be updated."); }
  }

  return <>
    <PageHeader eyebrow="Administration" title="Users & access" description="Create accounts and manage backend-enforced role assignments. Passwords are never displayed after creation." />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}{success && <p className="alert alert-success" role="status">{success}</p>}
    <section className="card section-block card-pad"><div className="section-heading"><div><h2>Create account</h2><p className="muted">Use a temporary password of at least 12 characters and share it securely.</p></div></div>
      <form className="form-grid form-grid-3" onSubmit={(event) => void createUser(event)}>
        <label className="field"><span>Full name</span><input name="full_name" minLength={2} maxLength={160} required /></label>
        <label className="field"><span>Email</span><input name="email" type="email" required /></label>
        <label className="field"><span>Initial password</span><input name="password" type="password" autoComplete="new-password" minLength={12} maxLength={200} required /></label>
        <label className="field"><span>Role</span><select name="role" defaultValue="employee">{roles.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}</select></label>
        <label className="field"><span>Department <span className="field-hint">Optional</span></span><select name="department_id" defaultValue=""><option value="">No department</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label>
        <div className="field"><span>&nbsp;</span><button className="button button-primary" type="submit">Create account</button></div>
      </form>
    </section>
    <section className="card section-block card-pad"><div className="section-heading"><div><h2>Access directory</h2><p className="muted">{total} accounts. The final active administrator cannot be removed.</p></div></div>
      {loading ? <LoadingState /> : users.length === 0 ? <EmptyState title="No users" message="Accounts will appear here after creation." /> : <div className="table-wrap"><table><thead><tr><th>User</th><th>Role</th><th>Department</th><th>Status</th><th>Access</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}>
        <td><span className="table-primary">{item.full_name}</span><span className="table-secondary">{item.email}</span></td>
        <td><select aria-label={`Role for ${item.full_name}`} value={item.role} onChange={(event) => void update(item, { role: event.target.value as User["role"] })}>{roles.map((role) => <option key={role} value={role}>{role.replaceAll("_", " ")}</option>)}</select></td>
        <td><select aria-label={`Department for ${item.full_name}`} value={item.department_id ?? ""} onChange={(event) => void update(item, { department_id: event.target.value || null })}><option value="">No department</option>{departments.map((department) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></td>
        <td><span className={`badge ${item.is_active ? "badge-green" : ""}`}>{item.is_active ? "Active" : "Inactive"}</span></td>
        <td><button className={`button button-small ${item.is_active ? "button-danger" : "button-secondary"}`} type="button" onClick={() => void update(item, { is_active: !item.is_active })}>{item.is_active ? "Deactivate" : "Reactivate"}</button></td>
      </tr>)}</tbody></table></div>}
    </section>
  </>;
}
