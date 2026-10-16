"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PriorityBadge, StatusBadge } from "@/components/Badge";
import { EmptyState, ErrorState, Loading } from "@/components/States";
import { api } from "@/lib/api";
import {
  PRIORITIES,
  SERVICE_TYPES,
  STATUSES,
  label,
  type RequestPage,
  type ServiceRequest,
} from "@/lib/types";

const PAGE_SIZE = 10;

interface Filters {
  q: string;
  status: string;
  priority: string;
  service_type: string;
}

const NO_FILTERS: Filters = { q: "", status: "", priority: "", service_type: "" };

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export default function RequestsPage() {
  const [filters, setFilters] = useState<Filters>(NO_FILTERS);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<RequestPage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((f) => ({ ...f, q: search }));
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    Object.entries(filters).forEach(([key, value]) => value && params.set(key, value));
    try {
      setData(await api<RequestPage>(`/api/requests?${params}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load requests");
    } finally {
      setLoading(false);
    }
  }, [filters, page]);

  useEffect(() => {
    load();
  }, [load]);

  function setFilter(key: keyof Filters, value: string) {
    setFilters((f) => ({ ...f, [key]: value }));
    setPage(1);
  }

  const hasFilters = Object.values(filters).some(Boolean);
  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Service requests</h1>
          <p className="text-sm text-slate-500">Track and update client work in one place</p>
        </div>
        <Link href="/requests/new" className="btn-primary">
          New request
        </Link>
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <input
          className="input"
          placeholder="Search client, contact, reference..."
          aria-label="Search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <FilterSelect
          name="Status"
          allLabel="All statuses"
          value={filters.status}
          options={STATUSES}
          onChange={(v) => setFilter("status", v)}
        />
        <FilterSelect
          name="Priority"
          allLabel="All priorities"
          value={filters.priority}
          options={PRIORITIES}
          onChange={(v) => setFilter("priority", v)}
        />
        <FilterSelect
          name="Service type"
          allLabel="All service types"
          value={filters.service_type}
          options={SERVICE_TYPES}
          onChange={(v) => setFilter("service_type", v)}
        />
      </div>

      {loading && !data && <Loading />}
      {error && <ErrorState message={error} onRetry={load} />}
      {data && !error && (
        <>
          {data.total === 0 && !hasFilters ? (
            <EmptyState />
          ) : data.total === 0 ? (
            <p className="py-12 text-center text-slate-600">No requests match your filters.</p>
          ) : (
            <div className={loading ? "opacity-60" : undefined}>
              <RequestTable items={data.items} />
              <RequestCards items={data.items} />
              <div className="mt-4 flex items-center justify-between text-sm">
                <span className="text-slate-600">
                  Page {data.page} of {totalPages} · {data.total} total
                </span>
                <div className="flex gap-2">
                  <button
                    className="btn-secondary"
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous
                  </button>
                  <button
                    className="btn-secondary"
                    disabled={page >= totalPages}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function FilterSelect({
  name,
  allLabel,
  value,
  options,
  onChange,
}: {
  name: string;
  allLabel: string;
  value: string;
  options: readonly string[];
  onChange: (value: string) => void;
}) {
  return (
    <select
      className="input"
      aria-label={name}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{allLabel}</option>
      {options.map((o) => (
        <option key={o} value={o}>
          {label(o)}
        </option>
      ))}
    </select>
  );
}

function RequestTable({ items }: { items: ServiceRequest[] }) {
  return (
    <div className="card hidden overflow-hidden md:block">
      <table className="w-full text-left text-sm">
        <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
          <tr>
            <th className="px-4 py-3 font-medium">Reference</th>
            <th className="px-4 py-3 font-medium">Client</th>
            <th className="px-4 py-3 font-medium">Service type</th>
            <th className="px-4 py-3 font-medium">Priority</th>
            <th className="px-4 py-3 font-medium">Status</th>
            <th className="px-4 py-3 font-medium">Updated</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((r) => (
            <tr key={r.id} className="transition hover:bg-indigo-50/40">
              <td className="px-4 py-3">
                <Link href={`/requests/${r.id}/edit`} className="font-medium text-indigo-600 hover:underline">
                  {r.reference}
                </Link>
              </td>
              <td className="px-4 py-3">{r.client_name}</td>
              <td className="px-4 py-3">{label(r.service_type)}</td>
              <td className="px-4 py-3">
                <PriorityBadge priority={r.priority} />
              </td>
              <td className="px-4 py-3">
                <StatusBadge status={r.status} />
              </td>
              <td className="px-4 py-3 text-slate-600">{formatDate(r.updated_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function RequestCards({ items }: { items: ServiceRequest[] }) {
  return (
    <ul className="space-y-3 md:hidden">
      {items.map((r) => (
        <li key={r.id}>
          <Link
            href={`/requests/${r.id}/edit`}
            className="card block p-4 transition hover:border-indigo-300"
          >
            <div className="flex items-center justify-between">
              <span className="font-medium text-indigo-600">{r.reference}</span>
              <span className="text-xs text-slate-500">{formatDate(r.updated_at)}</span>
            </div>
            <p className="mt-1 font-medium">{r.client_name}</p>
            <p className="text-sm text-slate-600">{label(r.service_type)}</p>
            <div className="mt-2 flex gap-2">
              <PriorityBadge priority={r.priority} />
              <StatusBadge status={r.status} />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}
