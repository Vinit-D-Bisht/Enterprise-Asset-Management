"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Building2, Pencil, Plus, Search, Trash2, UsersRound } from "lucide-react";
import { EmptyState, ErrorBanner, LoadingState, PageHeader, SuccessBanner } from "@/components/page-header";
import { Modal } from "@/components/modal";
import { api, ApiError } from "@/lib/api";
import type { Department } from "@/lib/types";

export default function DepartmentsPage() {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Department | null>(null);
  const [creating, setCreating] = useState(false);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (query.trim()) params.set("search", query.trim());
      setDepartments(await api.get<Department[]>(`/departments${params.size ? `?${params}` : ""}`));
      setError("");
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Departments could not be loaded."); }
    finally { setLoading(false); }
  }, [query]);
  useEffect(() => { const timer = window.setTimeout(() => void load(), 180); return () => window.clearTimeout(timer); }, [load]);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const values = new FormData(form);
    setSaving(true); setError(""); setSuccess("");
    const body = { name: String(values.get("name") ?? "").trim(), description: String(values.get("description") ?? "").trim() || null };
    try {
      if (editing) await api.patch(`/departments/${editing.id}`, body);
      else await api.post("/departments", body);
      setEditing(null); setCreating(false); setSuccess(editing ? "Department updated." : "Department created."); await load();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Department could not be saved."); }
    finally { setSaving(false); }
  }

  async function remove(department: Department) {
    if (!window.confirm(`Delete ${department.name}? Departments with assigned employees cannot be deleted.`)) return;
    setError(""); setSuccess("");
    try { await api.delete<void>(`/departments/${department.id}`); setSuccess(`${department.name} deleted.`); await load(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Department could not be deleted."); }
  }

  const modalOpen = creating || Boolean(editing);
  return <div className="page-stack">
    <PageHeader eyebrow="Organization" title="Departments" description="Organize employees into departments and keep the company directory current." action={<button className="button button-primary" type="button" onClick={() => { setEditing(null); setCreating(true); }}><Plus size={15} /> Add department</button>} />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}{success && <SuccessBanner message={success} />}
    <section className="card card-pad department-panel">
      <div className="toolbar"><label className="toolbar-search"><Search size={15} /><span className="visually-hidden">Search departments</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search departments" /></label><span className="toolbar-meta">{departments.length} {departments.length === 1 ? "department" : "departments"}</span></div>
      {loading ? <LoadingState label="Loading departments..." /> : departments.length === 0 ? <EmptyState title={query ? "No matching departments" : "No departments yet"} message={query ? "Try a different department name." : "Create departments to group employees in the organization directory."} action={!query && <button className="button button-primary button-small" type="button" onClick={() => setCreating(true)}><Plus size={14} /> Add first department</button>} /> : <div className="table-wrap"><table><thead><tr><th>Department</th><th>Description</th><th>Employees</th><th>Actions</th></tr></thead><tbody>{departments.map((department) => <tr key={department.id}><td><div className="department-name"><span><Building2 size={16} /></span><strong>{department.name}</strong></div></td><td>{department.description || <span className="cell-muted">No description</span>}</td><td><span className="department-count"><UsersRound size={14} />{department.employee_count}</span></td><td><div className="table-actions"><button className="button button-small button-secondary" type="button" onClick={() => { setCreating(false); setEditing(department); }}><Pencil size={13} /> Edit</button><button className="button button-small button-danger" type="button" aria-label={`Delete ${department.name}`} onClick={() => void remove(department)}><Trash2 size={13} /> Delete</button></div></td></tr>)}</tbody></table></div>}
    </section>
    <Modal open={modalOpen} title={editing ? "Edit department" : "Add department"} description="Department names must be unique across the organization." onClose={() => { setCreating(false); setEditing(null); }}>
      <form className="form-stack" onSubmit={(event) => void save(event)}><label className="field"><span>Department name</span><input name="name" autoFocus required minLength={1} maxLength={120} defaultValue={editing?.name ?? ""} /></label><label className="field"><span>Description <span className="field-hint">Optional</span></span><textarea name="description" maxLength={2000} defaultValue={editing?.description ?? ""} /></label><div className="form-actions"><button className="button button-secondary" type="button" onClick={() => { setCreating(false); setEditing(null); }}>Cancel</button><button className="button button-primary" type="submit" disabled={saving}>{saving ? "Saving..." : editing ? "Save changes" : "Create department"}</button></div></form>
    </Modal>
  </div>;
}
