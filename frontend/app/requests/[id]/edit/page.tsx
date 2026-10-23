"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { PriorityBadge, StatusBadge } from "@/components/Badge";
import { RequestForm } from "@/components/RequestForm";
import { ErrorState, Loading } from "@/components/States";
import { ApiError, api } from "@/lib/api";
import {
  PRIORITIES,
  STATUSES,
  label,
  type Priority,
  type RequestInput,
  type ServiceRequest,
  type Status,
} from "@/lib/types";

export default function EditRequestPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [request, setRequest] = useState<ServiceRequest | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    api<{ role: string }>("/api/auth/me")
      .then((me) => setIsAdmin(me.role === "admin"))
      .catch(() => setIsAdmin(false));
  }, []);

  const load = useCallback(async () => {
    setError(null);
    try {
      setRequest(await api<ServiceRequest>(`/api/requests/${id}`));
    } catch (e) {
      const notFound = e instanceof ApiError && e.status === 404;
      setError(notFound ? "This request does not exist." : (e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function patch(changes: Partial<ServiceRequest>, message: string) {
    setNotice(null);
    try {
      setRequest(await api<ServiceRequest>(`/api/requests/${id}`, { method: "PATCH", body: changes }));
      setNotice(message);
    } catch (e) {
      setNotice((e as Error).message);
    }
  }

  async function remove() {
    try {
      await api<void>(`/api/requests/${id}`, { method: "DELETE" });
      router.push("/requests");
    } catch (e) {
      setNotice((e as Error).message);
      setConfirmingDelete(false);
    }
  }

  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!request) return <Loading />;

  const initial: RequestInput = {
    client_name: request.client_name,
    contact_name: request.contact_name,
    service_type: request.service_type,
    description: request.description,
  };

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/requests" className="text-sm text-ink/75 underline decoration-2 underline-offset-2">
        &larr; Back to requests
      </Link>
      <div className="mb-4 mt-2 flex flex-wrap items-center gap-2">
        <h1 className="font-serif text-2xl font-bold">{request.reference}</h1>
        <PriorityBadge priority={request.priority} />
        <StatusBadge status={request.status} />
      </div>

      <div className="mb-4 grid grid-cols-1 gap-3 card p-4 sm:grid-cols-2">
        <label className="block text-sm">
          <span className="mb-1 block font-bold text-ink">Status</span>
          <select
            className="input"
            value={request.status}
            onChange={(e) => patch({ status: e.target.value as Status }, "Status updated")}
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {label(s)}
              </option>
            ))}
          </select>
        </label>
        <label className="block text-sm">
          <span className="mb-1 block font-bold text-ink">Priority</span>
          <select
            className="input"
            value={request.priority}
            onChange={(e) => patch({ priority: e.target.value as Priority }, "Priority updated")}
          >
            {PRIORITIES.map((p) => (
              <option key={p} value={p}>
                {label(p)}
              </option>
            ))}
          </select>
        </label>
      </div>

      {notice && (
        <p role="status" className="mb-4 text-sm text-ink">
          {notice}
        </p>
      )}

      <div className="card p-6">
        <RequestForm
          initial={initial}
          submitLabel="Save changes"
          onSubmit={(values) => patch(values, "Changes saved")}
        />
      </div>

      {isAdmin && (
        <div className="mt-6 card bg-blush/50 p-4">
          {confirmingDelete ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm">Delete {request.reference} permanently?</span>
              <button className="btn-danger" onClick={remove}>
                Yes, delete
              </button>
              <button className="btn-secondary" onClick={() => setConfirmingDelete(false)}>
                Cancel
              </button>
            </div>
          ) : (
            <button className="btn-danger" onClick={() => setConfirmingDelete(true)}>
              Delete request
            </button>
          )}
        </div>
      )}
    </div>
  );
}
