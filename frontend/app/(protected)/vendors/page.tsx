"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { ErrorBanner, EmptyState, LoadingState, PageHeader } from "@/components/page-header";
import { Modal } from "@/components/modal";
import { api, ApiError } from "@/lib/api";
import type { Page, Vendor } from "@/lib/types";

export default function VendorsPage() {
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [total, setTotal] = useState(0);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [editing, setEditing] = useState<Vendor | null>(null);
  const [createOpen, setCreateOpen] = useState(false);

  const load = useCallback(async () => {
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "20" });
      if (search) query.set("search", search);
      const result = await api.get<Page<Vendor>>(`/vendors?${query}`);
      setVendors(result.items); setTotal(result.total);
      setError("");
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Vendor records could not be loaded."); }
    finally { setLoading(false); }
  }, [page, search]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);

  async function save(event: FormEvent<HTMLFormElement>, vendor?: Vendor) {
    event.preventDefault(); const data = new FormData(event.currentTarget);
    setError(""); setSuccess("");
    const payload = {
      name: data.get("name"), contact_name: data.get("contact_name") || null,
      email: data.get("email") || null, phone: data.get("phone") || null, address: data.get("address") || null,
    };
    try {
      if (vendor) await api.patch(`/vendors/${vendor.id}`, payload);
      else await api.post("/vendors", payload);
      setSuccess(vendor ? "Vendor updated." : "Vendor added."); setEditing(null); setCreateOpen(false); await load();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Vendor could not be saved."); }
  }

  async function toggle(vendor: Vendor) {
    setError(""); setSuccess("");
    try { await api.patch(`/vendors/${vendor.id}`, { is_active: !vendor.is_active }); setSuccess(vendor.is_active ? "Vendor deactivated." : "Vendor activated."); await load(); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Vendor status could not be changed."); }
  }

  const pageCount = Math.max(1, Math.ceil(total / 20));
  return <>
    <PageHeader eyebrow="Directory" title="Vendors" description="Maintain supplier contacts linked to assets and warranty records." action={<button className="button button-primary" type="button" onClick={() => setCreateOpen(true)}>＋ Add vendor</button>} />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}{success && <p className="alert alert-success" role="status">{success}</p>}
    <section className="card section-block card-pad">
      <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}>
        <label className="field field-search"><span className="visually-hidden">Search vendors</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search vendor or contact" /></label>
        <button className="button button-secondary" type="submit">Search</button><span className="toolbar-meta">{total} vendors</span>
      </form>
      {loading ? <LoadingState /> : vendors.length === 0 ? <EmptyState title="No vendors found" message={search ? "Try another search term." : "Add a vendor when you need to link suppliers to assets or warranties."} /> :
        <div className="table-wrap"><table><thead><tr><th>Vendor</th><th>Contact</th><th>Phone</th><th>Status</th><th>Actions</th></tr></thead><tbody>{vendors.map((vendor) => <tr key={vendor.id}>
          <td><span className="table-primary">{vendor.name}</span><span className="table-secondary">{vendor.email ?? "No email recorded"}</span></td>
          <td>{vendor.contact_name ?? "—"}</td><td>{vendor.phone ?? "—"}</td>
          <td><span className={`badge ${vendor.is_active ? "badge-green" : ""}`}>{vendor.is_active ? "Active" : "Inactive"}</span></td>
          <td><div className="table-actions"><button className="button button-small button-secondary" type="button" onClick={() => setEditing(vendor)}>Edit</button><button className="button button-small button-quiet" type="button" onClick={() => void toggle(vendor)}>{vendor.is_active ? "Deactivate" : "Activate"}</button></div></td>
        </tr>)}</tbody></table></div>}
      {total > 20 && <div className="form-actions"><button className="button button-secondary button-small" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">Previous</button><span className="muted">Page {page} of {pageCount}</span><button className="button button-secondary button-small" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)} type="button">Next</button></div>}
    </section>
    <VendorForm open={createOpen} title="Add vendor" onClose={() => setCreateOpen(false)} onSubmit={(event) => void save(event)} />
    <VendorForm open={Boolean(editing)} title="Edit vendor" vendor={editing ?? undefined} onClose={() => setEditing(null)} onSubmit={(event) => void save(event, editing ?? undefined)} />
  </>;
}

function VendorForm({ open, title, vendor, onClose, onSubmit }: Readonly<{ open: boolean; title: string; vendor?: Vendor; onClose: () => void; onSubmit: (event: FormEvent<HTMLFormElement>) => void }>) {
  return <Modal open={open} title={title} onClose={onClose}><form className="form-stack" onSubmit={onSubmit}>
    <div className="form-grid"><label className="field"><span>Vendor name</span><input name="name" defaultValue={vendor?.name ?? ""} required maxLength={180} /></label>
      <label className="field"><span>Contact name</span><input name="contact_name" defaultValue={vendor?.contact_name ?? ""} maxLength={160} /></label>
      <label className="field"><span>Email</span><input name="email" type="email" defaultValue={vendor?.email ?? ""} /></label>
      <label className="field"><span>Phone</span><input name="phone" defaultValue={vendor?.phone ?? ""} maxLength={40} /></label></div>
    <label className="field"><span>Address</span><textarea name="address" defaultValue={vendor?.address ?? ""} maxLength={2000} /></label>
    <div className="form-actions"><button className="button button-secondary" type="button" onClick={onClose}>Cancel</button><button className="button button-primary" type="submit">Save vendor</button></div>
  </form></Modal>;
}
