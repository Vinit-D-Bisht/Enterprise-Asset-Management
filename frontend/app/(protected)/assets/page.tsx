"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import Image from "next/image";
import { ErrorBanner, EmptyState, LoadingState, PageHeader } from "@/components/page-header";
import { Modal } from "@/components/modal";
import { useAuth } from "@/components/auth-provider";
import { api, ApiError } from "@/lib/api";
import type { Asset, DirectoryEntry, Page, UserOption, Vendor } from "@/lib/types";

type Warranty = { id: string; start_date: string; end_date: string; terms: string | null };

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [createOpen, setCreateOpen] = useState(false);
  const [warrantyAsset, setWarrantyAsset] = useState<Asset | null>(null);
  const [qrAsset, setQrAsset] = useState<Asset | null>(null);
  const [qrUrl, setQrUrl] = useState("");
  const [recipient, setRecipient] = useState<Record<string, string>>({});
  const [destination, setDestination] = useState<Record<string, string>>({});

  const load = useCallback(async () => {
    try {
      const query = new URLSearchParams({ page: String(page), page_size: "20" });
      if (search) query.set("search", search);
      const [assetPage, categoryData, locationData] = await Promise.all([
        api.get<Page<Asset>>(`/assets?${query}`),
        api.get<DirectoryEntry[]>("/categories"),
        api.get<DirectoryEntry[]>("/locations"),
      ]);
      setAssets(assetPage.items);
      setTotal(assetPage.total);
      setCategories(categoryData);
      setLocations(locationData);
      if (canManage) {
        const [vendorPage, users] = await Promise.all([
          api.get<Page<Vendor>>("/vendors?page_size=100"),
          api.get<UserOption[]>("/users/directory"),
        ]);
        setVendors(vendorPage.items);
        setPeople(users);
      }
      setError("");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Assets could not be loaded.");
    } finally {
      setLoading(false);
    }
  }, [page, search, canManage]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => { if (!cancelled) void load(); });
    return () => { cancelled = true; };
  }, [load]);
  useEffect(() => () => { if (qrUrl) URL.revokeObjectURL(qrUrl); }, [qrUrl]);

  async function action<T>(operation: () => Promise<T>, message: string): Promise<boolean> {
    setError(""); setSuccess("");
    try { await operation(); setSuccess(message); await load(); return true; }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "The requested operation failed."); return false; }
  }

  async function createAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const saved = await action(() => api.post<Asset>("/assets", {
      asset_tag: data.get("asset_tag"), serial_number: data.get("serial_number") || null,
      name: data.get("name"), description: data.get("description") || null,
      category_id: data.get("category_id"), location_id: data.get("location_id"), vendor_id: data.get("vendor_id") || null,
      purchase_date: data.get("purchase_date"), purchase_cost: data.get("purchase_cost"),
      residual_value: data.get("residual_value") || "0", useful_life_months: Number(data.get("useful_life_months")),
    }), "Asset created successfully.");
    if (saved) setCreateOpen(false);
  }

  async function addDirectory(event: FormEvent<HTMLFormElement>, kind: "categories" | "locations") {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const saved = await action(async () => {
      const record = kind === "categories"
        ? await api.post<DirectoryEntry>(`/${kind}`, { name: data.get("name"), description: data.get("description") || null })
        : await api.post<DirectoryEntry>(`/${kind}`, { name: data.get("name"), code: data.get("code") || null, description: data.get("description") || null });
      return record;
    }, `${kind === "categories" ? "Category" : "Location"} added.`);
    if (saved) form.reset();
  }

  async function addWarranty(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!warrantyAsset) return;
    const data = new FormData(event.currentTarget);
    const saved = await action(() => api.post<Warranty>(`/assets/${warrantyAsset.id}/warranties`, {
      vendor_id: data.get("vendor_id") || null,
      start_date: data.get("start_date"), end_date: data.get("end_date"), terms: data.get("terms") || null,
    }), "Warranty recorded.");
    if (saved) setWarrantyAsset(null);
  }

  const pageCount = Math.max(1, Math.ceil(total / 20));
  const visibleAssets = assets;

  return <>
    <PageHeader eyebrow="Register" title="Assets" description="Track asset identity, location, custody, warranties, and lifecycle status."
      action={canManage ? <button className="button button-primary" type="button" onClick={() => setCreateOpen(true)}>＋ Add asset</button> : undefined} />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}
    {success && <p className="alert alert-success" role="status">{success}</p>}

    {canManage && <section className="card section-block">
      <div className="section-heading card-pad" style={{ paddingBottom: 0 }}><div><h2>Register setup</h2><p className="muted">Add categories and locations before registering assets.</p></div></div>
      <div className="form-grid card-pad">
        <form className="inline-form" onSubmit={(event) => void addDirectory(event, "categories")}>
          <label className="field"><span>New category</span><input name="name" maxLength={100} required placeholder="e.g. Mobile devices" /></label>
          <button className="button button-secondary" type="submit">Add category</button>
        </form>
        <form className="inline-form" onSubmit={(event) => void addDirectory(event, "locations")}>
          <label className="field"><span>New location</span><input name="name" maxLength={160} required placeholder="e.g. London office" /></label>
          <label className="field"><span>Code</span><input name="code" maxLength={40} placeholder="Optional" /></label>
          <button className="button button-secondary" type="submit">Add location</button>
        </form>
      </div>
    </section>}

    <section className="card section-block">
      <div className="card-pad">
        <form className="toolbar" onSubmit={(event) => { event.preventDefault(); setPage(1); setSearch(searchInput.trim()); }}>
          <label className="field field-search"><span className="visually-hidden">Search assets</span><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} placeholder="Search tag, serial number, or asset name" /></label>
          <button className="button button-secondary" type="submit">Search</button>
          {search && <button className="button button-quiet" type="button" onClick={() => { setSearchInput(""); setSearch(""); }}>Clear</button>}
          <span className="toolbar-meta">{total} {total === 1 ? "asset" : "assets"}</span>
        </form>
        {loading ? <LoadingState /> : visibleAssets.length === 0 ? <EmptyState title="No assets found" message={search ? "Try a different search term." : "Assets will appear here when registered."} /> :
          <div className="table-wrap"><table><thead><tr><th>Asset</th><th>Category / location</th><th>Status</th><th>Current custodian</th>{canManage && <th>Cost</th>}{canManage && <th>Actions</th>}</tr></thead><tbody>
            {visibleAssets.map((asset) => <tr key={asset.id}>
              <td><span className="table-primary">{asset.name}</span><span className="table-secondary">{asset.asset_tag}{asset.serial_number ? ` · ${asset.serial_number}` : ""}</span></td>
              <td>{asset.category_name}<span className="table-secondary">{asset.location_name}</span></td>
              <td><span className={`badge ${asset.status === "available" ? "badge-green" : asset.status === "in_repair" ? "badge-amber" : asset.status === "assigned" ? "badge-blue" : ""}`}>{asset.status.replaceAll("_", " ")}</span></td>
              <td>{asset.current_assignee_name ?? <span className="muted">Unassigned</span>}</td>
              {canManage && <td>{asset.purchase_cost ? new Intl.NumberFormat(undefined, { style: "currency", currency: asset.company_currency ?? "INR" }).format(Number(asset.purchase_cost)) : "—"}</td>}
              {canManage && <td><div className="table-actions">
                {asset.status === "available" && <><select aria-label={`Allocate ${asset.asset_tag} to`} value={recipient[asset.id] ?? ""} onChange={(event) => setRecipient((current) => ({ ...current, [asset.id]: event.target.value }))}><option value="">Allocate to…</option>{people.filter((person) => person.role === "employee").map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}</select><button className="button button-small button-secondary" type="button" disabled={!recipient[asset.id]} onClick={() => void action(() => api.post(`/assets/${asset.id}/allocate`, { user_id: recipient[asset.id] }), `${asset.asset_tag} allocated.`)}>Allocate</button></>}
                {asset.status === "assigned" && <button className="button button-small button-secondary" type="button" onClick={() => void action(() => api.post(`/assets/${asset.id}/return`, {}), `${asset.asset_tag} returned.`)}>Return</button>}
                <select aria-label={`Transfer ${asset.asset_tag} to`} value={destination[asset.id] ?? ""} onChange={(event) => setDestination((current) => ({ ...current, [asset.id]: event.target.value }))}><option value="">Move to…</option>{locations.filter((location) => location.id !== asset.location_id).map((location) => <option key={location.id} value={location.id}>{location.name}</option>)}</select>
                <button className="button button-small button-secondary" type="button" disabled={!destination[asset.id]} onClick={() => void action(() => api.post(`/assets/${asset.id}/transfer`, { to_location_id: destination[asset.id], reason: "Location transfer" }), `${asset.asset_tag} transferred.`)}>Transfer</button>
                <button className="button button-small button-quiet" type="button" onClick={() => setWarrantyAsset(asset)}>Warranty</button>
                <button className="button button-small button-quiet" type="button" onClick={async () => { try { const blob = await api.get<Blob>(`/assets/${asset.id}/qr`); if (qrUrl) URL.revokeObjectURL(qrUrl); setQrUrl(URL.createObjectURL(blob)); setQrAsset(asset); } catch (reason) { setError(reason instanceof ApiError ? reason.message : "QR code could not be generated."); } }}>QR</button>
                {asset.status !== "retired" && <button className="button button-small button-danger" type="button" onClick={() => { if (window.confirm(`Retire ${asset.asset_tag}? This is a permanent lifecycle record.`)) void action(() => api.post(`/assets/${asset.id}/retire?reason=${encodeURIComponent("Retired by asset manager")}`), `${asset.asset_tag} retired.`); }}>Retire</button>}
              </div></td>}
            </tr>)}
          </tbody></table></div>}
        {!loading && total > 20 && <div className="form-actions"><button className="button button-secondary button-small" disabled={page <= 1} onClick={() => setPage((current) => current - 1)} type="button">Previous</button><span className="muted">Page {page} of {pageCount}</span><button className="button button-secondary button-small" disabled={page >= pageCount} onClick={() => setPage((current) => current + 1)} type="button">Next</button></div>}
      </div>
    </section>

    <Modal open={createOpen} title="Register an asset" description="Asset tag and financial values are validated by the backend." onClose={() => setCreateOpen(false)}>
      <form className="form-stack" onSubmit={(event) => void createAsset(event)}>
        <div className="form-grid">
          <label className="field"><span>Asset tag</span><input name="asset_tag" required maxLength={80} /></label>
          <label className="field"><span>Asset name</span><input name="name" required maxLength={180} /></label>
          <label className="field"><span>Serial number</span><input name="serial_number" maxLength={120} /></label>
          <label className="field"><span>Category</span><select name="category_id" required defaultValue=""><option value="" disabled>Select category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Location</span><select name="location_id" required defaultValue=""><option value="" disabled>Select location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Vendor</span><select name="vendor_id" defaultValue=""><option value="">None</option>{vendors.filter((vendor) => vendor.is_active).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Purchase date</span><input name="purchase_date" type="date" required /></label>
          <label className="field"><span>Purchase cost</span><input name="purchase_cost" type="number" min="0" step="0.01" required /></label>
          <label className="field"><span>Residual value</span><input name="residual_value" type="number" min="0" step="0.01" defaultValue="0" required /></label>
          <label className="field"><span>Useful life (months)</span><input name="useful_life_months" type="number" min="1" max="1200" required /></label>
        </div>
        <label className="field"><span>Description</span><textarea name="description" maxLength={5000} /></label>
        <div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setCreateOpen(false)}>Cancel</button><button className="button button-primary" type="submit">Save asset</button></div>
      </form>
    </Modal>

    <Modal open={Boolean(warrantyAsset)} title={`Record warranty${warrantyAsset ? ` · ${warrantyAsset.asset_tag}` : ""}`} onClose={() => setWarrantyAsset(null)}>
      <form className="form-stack" onSubmit={(event) => void addWarranty(event)}>
        <div className="form-grid">
          <label className="field"><span>Vendor</span><select name="vendor_id" defaultValue=""><option value="">Use asset vendor / unspecified</option>{vendors.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
          <label className="field"><span>Start date</span><input name="start_date" type="date" required /></label>
          <label className="field"><span>End date</span><input name="end_date" type="date" required /></label>
        </div>
        <label className="field"><span>Terms</span><textarea name="terms" maxLength={5000} /></label>
        <div className="form-actions"><button className="button button-secondary" type="button" onClick={() => setWarrantyAsset(null)}>Cancel</button><button className="button button-primary" type="submit">Save warranty</button></div>
      </form>
    </Modal>

    <Modal open={Boolean(qrAsset)} title={`Asset QR · ${qrAsset?.asset_tag ?? ""}`} description="Scan to identify this asset in EAMMS." onClose={() => setQrAsset(null)}>
      {qrUrl && <div className="qr-preview"><Image src={qrUrl} width={240} height={240} unoptimized alt={`QR code for ${qrAsset?.asset_tag}`} /><a className="button button-secondary" href={qrUrl} download={`${qrAsset?.asset_tag}.png`}>Download QR code</a></div>}
    </Modal>
  </>;
}
