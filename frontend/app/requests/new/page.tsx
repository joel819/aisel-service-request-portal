"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { RequestForm } from "@/components/RequestForm";
import { api } from "@/lib/api";
import type { RequestInput, ServiceRequest } from "@/lib/types";

export default function NewRequestPage() {
  const router = useRouter();

  async function create(values: RequestInput) {
    await api<ServiceRequest>("/api/requests", { method: "POST", body: values });
    router.push("/requests");
  }

  return (
    <div className="mx-auto max-w-2xl">
      <Link href="/requests" className="text-sm text-ink/75 underline decoration-2 underline-offset-2">
        &larr; Back to requests
      </Link>
      <h1 className="mb-4 mt-2 font-serif text-2xl font-bold">New service request</h1>
      <div className="card p-6">
        <RequestForm showPriority submitLabel="Create request" onSubmit={create} />
      </div>
    </div>
  );
}
