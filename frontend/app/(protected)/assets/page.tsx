"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { ArrowDownToLine, ArrowLeftRight, ArrowRight, Box, Boxes, Eye, MapPin, Plus, QrCode, RotateCcw, Search, ShieldCheck } from "lucide-react";
import { ErrorBanner, EmptyState, LoadingState, PageHeader, SuccessBanner } from "@/components/page-header";
import { Modal } from "@/components/modal";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Asset, DirectoryEntry, Page, UserOption, Vendor } from "@/lib/types";

type Warranty = { id: string; asset_id: string; vendor_id: string | null; start_date: string; end_date: string; terms: string | null };
type Assignment = { id: string; asset_id: string; asset_tag: string; user_id: string; user_name: string; assigned_at: string; returned_at: string | null; notes: string | null };
type AssetDetails = Asset & { assignments: Assignment[]; warranties: Warranty[] };
const statusOptions = ["available", "assigned", "in_repair", "retired"] as const;

function dateLabel(value?: string | null) { return value ? new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "Not recorded"; }
function initials(name: string) { return name.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase(); }

export default function AssetsPage() {
  const { user } = useAuth();
  const canManage = user?.role === "administrator" || user?.role === "asset_manager";
  const [assets, setAssets] = useState<Asset[]>([]);
  const [categories, setCategories] = useState<DirectoryEntry[]>([]);
  const [locations, setLocations] = useState<DirectoryEntry[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);
  const [people, setPeople] = useState<UserOption[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [locationFilter, setLocationFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [warrantyAsset, setWarrantyAsset] = useState<Asset | null>(null);
  const [details, setDetails] = useState<AssetDetails | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [qrUrl, setQrUrl] = useState("");
  const [recipient, setRecipient] = useState<Record<string, string>>({});
  const [destination, setDestination] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "20" });
      if (search) query.set("search", search);
      if (statusFilter) query.set("status", statusFilter);
      if (categoryFilter) query.set("category_id", categoryFilter);
      if (locationFilter) query.set("location_id", locationFilter);
      const [assetPage, categoryData, locationData] = await Promise.all([
        api.get<Page<Asset>>(`/assets?${query}`), api.get<DirectoryEntry[]>("/categories"), api.get<DirectoryEntry[]>("/locations"),
      ]);
      setAssets(assetPage.items); setTotal(assetPage.total); setCategories(categoryData); setLocations(locationData);
      if (canManage) {
        const [vendorPage, directory] = await Promise.all([api.get<Page<Vendor>>("/vendors?page_size=100"), api.get<UserOption[]>("/users/directory")]);
        setVendors(vendorPage.items); setPeople(directory);
      }
      setError("");
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Asset records could not be loaded."); }
    finally { setLoading(false); }
  }, [page, search, statusFilter, categoryFilter, locationFilter, canManage]);

  useEffect(() => { let alive = true; queueMicrotask(() => { if (alive) void load(); }); return () => { alive = false; }; }, [load]);
  useEffect(() => {
    const initialSearch = new URLSearchParams(window.location.search).get("search");
    if (initialSearch) queueMicrotask(() => { setSearchInput(initialSearch); setSearch(initialSearch); });
    const onSearch = (event: Event) => { const value = (event as CustomEvent<string>).detail ?? ""; queueMicrotask(() => { setSearchInput(value); setSearch(value); setPage(1); }); };
    window.addEventListener("eamms:asset-search", onSearch);
    return () => window.removeEventListener("eamms:asset-search", onSearch);
  }, []);
  useEffect(() => () => { if (qrUrl) URL.revokeObjectURL(qrUrl); }, [qrUrl]);

  async function action(operation: () => Promise<unknown>, message: string) {
    setError(""); setSuccess("");
    try { await operation(); setSuccess(message); await load(); return true; }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "The requested operation could not be completed."); return false; }
  }

  async function createAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form);
    const created = await action(() => api.post<Asset>("/assets", {
      asset_tag: data.get("asset_tag"), serial_number: data.get("serial_number") || null, name: data.get("name"), description: data.get("description") || null,
      category_id: data.get("category_id"), location_id: data.get("location_id"), vendor_id: data.get("vendor_id") || null,
      purchase_date: data.get("purchase_date"), purchase_cost: data.get("purchase_cost"), residual_value: data.get("residual_value") || "0", useful_life_months: Number(data.get("useful_life_months")),
    }), "Asset created successfully.");
    if (created) { form.reset(); setCreateOpen(false); }
  }

  async function addWarranty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); if (!warrantyAsset) return;
    const data = new FormData(event.currentTarget);
    const saved = await action(() => api.post<Warranty>(`/assets/${warrantyAsset.id}/warranties`, { vendor_id: data.get("vendor_id") || null, start_date: data.get("start_date"), end_date: data.get("end_date"), terms: data.get("terms") || null }), "Warranty recorded.");
    if (saved) { setWarrantyAsset(null); if (details?.id === warrantyAsset.id) void openDetails(warrantyAsset); }
  }

  async function openDetails(asset: Asset) {
    setDetailsLoading(true); setDetails({ ...asset, assignments: [], warranties: [] });
    try {
      const [full, assignmentsResult, warranties] = await Promise.all([
        api.get<Asset>(`/assets/${asset.id}`), api.get<Assignment[]>(`/assets/${asset.id}/assignments`).then((items) => ({ items })).catch((reason: unknown) => { if (reason instanceof ApiError && reason.status === 403) return { items: [] as Assignment[] }; throw reason; }), api.get<Warranty[]>(`/assets/${asset.id}/warranties`),
      ]);
      const assignmentHistory = "items" in assignmentsResult ? assignmentsResult.items : [];
      setDetails({ ...full, assignments: assignmentHistory, warranties }); setError("");
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "Asset details could not be loaded."); }
    finally { setDetailsLoading(false); }
  }

  async function loadQr(asset: Asset) {
    try { const blob = await api.get<Blob>(`/assets/${asset.id}/qr`); if (qrUrl) URL.revokeObjectURL(qrUrl); setQrUrl(URL.createObjectURL(blob)); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "QR code could not be generated."); }
  }

  const pageCount = Math.max(1, Math.ceil(total / 20));
  return <div className="page-stack">
    <PageHeader eyebrow="Inventory" title="Asset register" description="Track equipment, ownership, location, warranty coverage, and lifecycle." action={canManage && <button className="button button-primary" type="button" onClick={() => setCreateOpen(true)}><Plus size={16} /> Register asset</button>} />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}{success && <SuccessBanner message={success} />}
    {canManage && <div className="asset-register-banner"><span className="asset-register-icon"><Boxes size={18} /></span><div><strong>Inventory control</strong><span>Allocate assets, record returns, move items between locations, or review full asset history.</span></div><a href="/catalogs" className="text-link">Manage catalogs <ArrowRight size={14} /></a></div>}
    <section className="card card-pad">
      <form className="toolbar asset-toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}>
        <label className="toolbar-search"><Search size={15} /><span className="visually-hidden">Search the asset register</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search by asset, tag, or serial number" /></label>
        <select className="filter-select" aria-label="Filter by status" value={statusFilter} onChange={(event) => { setStatusFilter(event.target.value); setPage(1); }}><option value="">All statuses</option>{statusOptions.map((status) => <option value={status} key={status}>{status.replaceAll("_", " ")}</option>)}</select>
        <select className="filter-select" aria-label="Filter by category" value={categoryFilter} onChange={(event) => { setCategoryFilter(event.target.value); setPage(1); }}><option value="">All categories</option>{categories.map((category) => <option value={category.id} key={category.id}>{category.name}</option>)}</select>
        <select className="filter-select" aria-label="Filter by location" value={locationFilter} onChange={(event) => { setLocationFilter(event.target.value); setPage(1); }}><option value="">All locations</option>{locations.map((location) => <option value={location.id} key={location.id}>{location.name}</option>)}</select>
        <button className="button button-secondary" type="submit">Search</button>
        <span className="toolbar-meta">{total.toLocaleString()} {total === 1 ? "asset" : "assets"}</span>
      </form>
      {loading ? <LoadingState label="Loading the asset register..." /> : assets.length === 0 ? <EmptyState title={search || statusFilter || categoryFilter || locationFilter ? "No matching assets" : "Your register is ready"} message={search || statusFilter || categoryFilter || locationFilter ? "Adjust the search or filters to see more records." : "Registered equipment will appear in this table."} action={canManage && <button className="button button-primary button-small" type="button" onClick={() => setCreateOpen(true)}><Plus size={14} /> Register first asset</button>} /> : <div className="table-wrap asset-table-wrap"><table className="asset-table"><thead><tr><th>Asset</th><th>Category</th><th>Location</th><th>Status</th><th>Custodian</th>{canManage && <th>Book cost</th>}<th>Details</th>{canManage && <th>Actions</th>}</tr></thead><tbody>{assets.map((asset) => <tr key={asset.id}>
        <td><div className="asset-name-cell"><span className="asset-type-icon"><Box size={16} /></span><span><strong>{asset.name}</strong><small>{asset.asset_tag}{asset.serial_number ? ` · ${asset.serial_number}` : ""}</small></span></div></td>
        <td>{asset.category_name}</td><td><span className="table-location"><MapPin size={12} />{asset.location_name}</span></td>
        <td><StatusBadge status={asset.status} /></td><td>{asset.current_assignee_name ? <span className="avatar-cell"><span className="avatar-small">{initials(asset.current_assignee_name)}</span>{asset.current_assignee_name}</span> : <span className="cell-muted">Unassigned</span>}</td>
        {canManage && <td className="cell-primary">{asset.purchase_cost ? new Intl.NumberFormat(undefined, { style: "currency", currency: asset.company_currency ?? "INR", maximumFractionDigits: 0 }).format(Number(asset.purchase_cost)) : "—"}</td>}
        <td><button className="button button-small button-quiet" type="button" onClick={() => void openDetails(asset)}><Eye size={13} /> View</button></td>
        {canManage && <td><div className="table-actions asset-actions">
          {asset.status === "available" && <><select aria-label={`Allocate ${asset.asset_tag} to`} value={recipient[asset.id] ?? ""} onChange={(event) => setRecipient((current) => ({ ...current, [asset.id]: event.target.value }))}><option value="">Allocate to...</option>{people.filter((person) => person.role === "employee").map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}</select><button className="button button-small button-secondary" type="button" disabled={!recipient[asset.id]} onClick={() => void action(() => api.post(`/assets/${asset.id}/allocate`, { user_id: recipient[asset.id] }), `${asset.asset_tag} allocated.`)}>Allocate</button></>}
          {asset.status === "assigned" && <button className="button button-small button-secondary" type="button" onClick={() => void action(() => api.post(`/assets/${asset.id}/return`, {}), `${asset.asset_tag} returned.`)}><RotateCcw size={12} /> Return</button>}
          <select aria-label={`Transfer ${asset.asset_tag} to`} value={destination[asset.id] ?? ""} onChange={(event) => setDestination((current) => ({ ...current, [asset.id]: event.target.value }))}><option value="">Move to...</option>{locations.filter((location) => location.id !== asset.location_id).map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select><button className="button button-small button-secondary" type="button" disabled={!destination[asset.id]} onClick={() => void action(() => api.post(`/assets/${asset.id}/transfer`, { to_location_id: destination[asset.id], reason: "Location transfer" }), `${asset.asset_tag} transferred.`)}><ArrowLeftRight size={12} /> Move</button>
          <button className="icon-action" type="button" aria-label={`Record warranty for ${asset.asset_tag}`} title="Record warranty" onClick={() => setWarrantyAsset(asset)}><ShieldCheck size={15} /></button>
          {asset.status !== "retired" && <button className="icon-action icon-action-danger" type="button" aria-label={`Retire ${asset.asset_tag}`} title="Retire asset" onClick={() => { if (window.confirm(`Retire ${asset.asset_tag}? This is a permanent lifecycle record.`)) void action(() => api.post(`/assets/${asset.id}/retire?reason=${encodeURIComponent("Retired by asset manager")}`), `${asset.asset_tag} retired.`); }}><ArrowDownToLine size={15} /></button>}
        </div></td>}
      </tr>)}</tbody></table></div>}
      {total > 20 && !loading && <div className="pagination"><button className="button button-secondary button-small" disabled={page <= 1} onClick={() => setPage((value) => value - 1)} type="button">Previous</button><span>Page {page} of {pageCount}</span><button className="button button-secondary button-small" disabled={page >= pageCount} onClick={() => setPage((value) => value + 1)} type="button">Next</button></div>}
    </section>

    <Modal open={createOpen} title="Register an asset" description="Enter the asset identity and accounting basis for the register." onClose={() => setCreateOpen(false)} size="wide">
      <form className="form-stack" onSubmit={(event) => void createAsset(event)}><div className="form-grid form-grid-3">
        <label className="field"><span>Asset tag</span><input name="asset_tag" required maxLength={80} placeholder="e.g. LAP-0042" /></label><label className="field"><span>Asset name</span><input name="name" required maxLength={180} placeholder="Equipment name" /></label><label className="field"><span>Serial number <span className="field-hint">Optional</span></span><input name="serial_number" maxLength={120} /></label>
        <label className="field"><span>Category</span><select name="category_id" required defaultValue=""><option value="" disabled>Select category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Location</span><select name="location_id" required defaultValue=""><option value="" disabled>Select location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>Vendor <span className="field-hint">Optional</span></span><select name="vendor_id" defaultValue=""><option value="">No vendor</option>{vendors.filter((vendor) => vendor.is_active).map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}</select></label>
        <label className="field"><span>Purchase date</span><input name="purchase_date" type="date" required /></label><label className="field"><span>Purchase cost</span><input name="purchase_cost" type="number" min="0" step="0.01" required /></label><label className="field"><span>Residual value</span><input name="residual_value" type="number" min="0" step="0.01" defaultValue="0" required /></label><label className="field"><span>Useful life (months)</span><input name="useful_life_months" type="number" min="1" max="1200" required /></label>
      </div><label className="field"><span>Description <span className="field-hint">Optional</span></span><textarea name="description" maxLength={5000} /></label><div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setCreateOpen(false)}>Cancel</button><button className="button button-primary" type="submit"><Plus size={15} /> Save asset</button></div></form>
    </Modal>

    <Modal open={Boolean(warrantyAsset)} title={`Record warranty${warrantyAsset ? ` · ${warrantyAsset.asset_tag}` : ""}`} description="Link coverage dates and terms to this asset." onClose={() => setWarrantyAsset(null)}>
      <form className="form-stack" onSubmit={(event) => void addWarranty(event)}><div className="form-grid"><label className="field"><span>Vendor</span><select name="vendor_id" defaultValue=""><option value="">Use asset vendor / unspecified</option>{vendors.map((vendor) => <option key={vendor.id} value={vendor.id}>{vendor.name}</option>)}</select></label><label className="field"><span>Start date</span><input name="start_date" type="date" required /></label><label className="field"><span>End date</span><input name="end_date" type="date" required /></label></div><label className="field"><span>Coverage terms</span><textarea name="terms" maxLength={5000} /></label><div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setWarrantyAsset(null)}>Cancel</button><button className="button button-primary" type="submit"><ShieldCheck size={15} /> Save warranty</button></div></form>
    </Modal>

    <Modal open={Boolean(details)} title={details?.name ?? "Asset details"} description={details ? `${details.asset_tag}${details.serial_number ? ` · ${details.serial_number}` : ""}` : undefined} onClose={() => { setDetails(null); setQrUrl(""); }} size="wide">
      {detailsLoading || !details ? <LoadingState label="Loading asset history..." /> : <div className="asset-detail-layout">
        <div className="asset-detail-main"><div className="asset-detail-summary"><span className="asset-detail-icon"><Box size={22} /></span><div><StatusBadge status={details.status} /><p>{details.description || "No description recorded."}</p></div></div>
          <div className="detail-grid"><Detail label="Category" value={details.category_name} /><Detail label="Location" value={details.location_name} /><Detail label="Current custodian" value={details.current_assignee_name ?? "Unassigned"} /><Detail label="Purchase date" value={dateLabel(details.purchase_date)} /><Detail label="Purchase cost" value={details.purchase_cost ? new Intl.NumberFormat(undefined, { style: "currency", currency: details.company_currency ?? "INR" }).format(Number(details.purchase_cost)) : "Not available"} /><Detail label="Useful life" value={details.useful_life_months ? `${details.useful_life_months} months` : "Not recorded"} /></div>
          <section className="detail-section"><div className="section-heading"><div><h2>Allocation history</h2><p>Recorded custody changes for this asset.</p></div></div>{details.assignments.length === 0 ? <p className="detail-empty">No allocation history is available for your account.</p> : <div className="history-list">{details.assignments.map((assignment) => <div className="history-row" key={assignment.id}><span className="avatar-small">{initials(assignment.user_name)}</span><span><strong>{assignment.user_name}</strong><small>{dateLabel(assignment.assigned_at)}{assignment.returned_at ? ` · Returned ${dateLabel(assignment.returned_at)}` : " · Currently assigned"}</small></span></div>)}</div>}</section>
          <section className="detail-section"><div className="section-heading"><div><h2>Warranty coverage</h2><p>Coverage associated with the asset.</p></div>{canManage && <button className="button button-secondary button-small" type="button" onClick={() => setWarrantyAsset(details)}><Plus size={13} /> Add warranty</button>}</div>{details.warranties.length === 0 ? <p className="detail-empty">No warranty coverage recorded.</p> : <div className="warranty-list">{details.warranties.map((warranty) => <div className="warranty-row" key={warranty.id}><span className="warranty-icon"><ShieldCheck size={15} /></span><span><strong>{dateLabel(warranty.start_date)} – {dateLabel(warranty.end_date)}</strong><small>{warranty.terms || "Coverage terms not recorded"}</small></span></div>)}</div>}</section>
        </div><aside className="asset-detail-qr"><div className="qr-preview-card"><span className="qr-icon"><QrCode size={20} /></span><strong>Asset QR code</strong><p>Scan this code to identify the asset.</p>{qrUrl ? <Image src={qrUrl} width={210} height={210} unoptimized alt={`QR code for ${details.asset_tag}`} /> : <div className="qr-placeholder"><QrCode size={38} /></div>}<button className="button button-secondary button-wide" type="button" onClick={() => void loadQr(details)}><QrCode size={14} /> {qrUrl ? "Refresh QR code" : "Generate QR code"}</button>{qrUrl && <a className="text-link" href={qrUrl} download={`${details.asset_tag}.png`}>Download PNG <ArrowRight size={13} /></a>}</div></aside>
      </div>}
    </Modal>
  </div>;
}

function StatusBadge({ status }: Readonly<{ status: Asset["status"] }>) {
  const tone = status === "available" ? "badge-green" : status === "assigned" ? "badge-blue" : status === "in_repair" ? "badge-amber" : "badge-red";
  return <span className={`badge ${tone}`}><span className="badge-dot" />{status.replaceAll("_", " ")}</span>;
}

function Detail({ label, value }: Readonly<{ label: string; value: string }>) { return <div className="detail-cell"><small>{label}</small><strong>{value}</strong></div>; }
