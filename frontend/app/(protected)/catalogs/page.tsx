"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { Boxes, MapPin, Plus, Tags } from "lucide-react";
import { ErrorBanner, EmptyState, LoadingState, PageHeader, SuccessBanner } from "@/components/page-header";
import { api, ApiError } from "@/lib/api";
import type { DirectoryEntry } from "@/lib/types";

export default function CatalogsPage() {
  const [categories, setCategories] = useState<DirectoryEntry[]>([]);
  const [locations, setLocations] = useState<DirectoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try { const [categoryRows, locationRows] = await Promise.all([api.get<DirectoryEntry[]>("/categories"), api.get<DirectoryEntry[]>("/locations")]); setCategories(categoryRows); setLocations(locationRows); setError(""); }
    catch (reason) { setError(reason instanceof ApiError ? reason.message : "Asset catalogs could not be loaded."); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { queueMicrotask(() => void load()); }, [load]);

  async function create(event: FormEvent<HTMLFormElement>, kind: "categories" | "locations") {
    event.preventDefault(); const form = event.currentTarget; const data = new FormData(form); setError(""); setSuccess("");
    try {
      if (kind === "categories") await api.post<DirectoryEntry>("/categories", { name: data.get("name"), description: data.get("description") || null });
      else await api.post<DirectoryEntry>("/locations", { name: data.get("name"), code: data.get("code") || null, description: data.get("description") || null });
      form.reset(); setSuccess(kind === "categories" ? "Category added to the asset catalog." : "Location added to the asset catalog."); await load();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "The catalog entry could not be saved."); }
  }

  return <div className="page-stack">
    <PageHeader eyebrow="Inventory setup" title="Categories & locations" description="Keep the asset register consistent with reusable categories and operating locations." />
    {error && <ErrorBanner message={error} onRetry={() => void load()} />}{success && <SuccessBanner message={success} />}
    <section className="surface-grid surface-grid-2">
      <article className="card card-pad catalog-card"><div className="section-heading"><div className="catalog-title"><span className="catalog-icon"><Tags size={17} /></span><span><h2>Asset categories</h2><p>Organize equipment by type or function.</p></span></div><span className="count-pill">{categories.length}</span></div>
        <form className="catalog-form" onSubmit={(event) => void create(event, "categories")}><label className="field"><span>Category name</span><input name="name" required maxLength={100} placeholder="e.g. Mobile devices" /></label><label className="field"><span>Description <span className="field-hint">Optional</span></span><input name="description" maxLength={2000} placeholder="What belongs in this category?" /></label><button className="button button-primary" type="submit"><Plus size={15} /> Add category</button></form>
        <div className="catalog-list-heading"><strong>Registered categories</strong><span>{categories.length} total</span></div>
        {loading ? <LoadingState label="Loading categories..." /> : categories.length === 0 ? <EmptyState title="No categories yet" message="Add a category to classify assets as they are registered." /> : <div className="catalog-list">{categories.map((row) => <div className="catalog-row" key={row.id}><span className="catalog-row-icon"><Boxes size={15} /></span><span><strong>{row.name}</strong>{row.description && <small>{row.description}</small>}</span></div>)}</div>}
      </article>
      <article className="card card-pad catalog-card"><div className="section-heading"><div className="catalog-title"><span className="catalog-icon catalog-icon-green"><MapPin size={17} /></span><span><h2>Locations</h2><p>Track the site or office responsible for each asset.</p></span></div><span className="count-pill">{locations.length}</span></div>
        <form className="catalog-form" onSubmit={(event) => void create(event, "locations")}><div className="form-grid"><label className="field"><span>Location name</span><input name="name" required maxLength={160} placeholder="e.g. Central office" /></label><label className="field"><span>Location code <span className="field-hint">Optional</span></span><input name="code" maxLength={40} placeholder="e.g. HQ-01" /></label></div><button className="button button-primary" type="submit"><Plus size={15} /> Add location</button></form>
        <div className="catalog-list-heading"><strong>Registered locations</strong><span>{locations.length} total</span></div>
        {loading ? <LoadingState label="Loading locations..." /> : locations.length === 0 ? <EmptyState title="No locations yet" message="Add an operating location before assigning assets to a site." /> : <div className="catalog-list">{locations.map((row) => <div className="catalog-row" key={row.id}><span className="catalog-row-icon catalog-row-icon-green"><MapPin size={15} /></span><span><strong>{row.name}</strong><small>{row.code ? `Code ${row.code}` : row.description || "No location code recorded"}</small></span></div>)}</div>}
      </article>
    </section>
    <p className="catalog-footnote">Catalog entries are shared across the asset register. Existing entries are read-only because the current asset API does not expose edit or delete operations.</p>
  </div>;
}
