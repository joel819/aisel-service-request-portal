"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { clearToken } from "@/lib/api";

export function BrandMark() {
  return (
    <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white">
      SR
    </span>
  );
}

export function Header() {
  const router = useRouter();

  function logout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/requests" className="flex items-center gap-2 font-semibold text-slate-900">
          <BrandMark />
          <span>Service Requests</span>
        </Link>
        <button onClick={logout} className="btn-secondary px-3 py-1.5">
          Log out
        </button>
      </div>
    </header>
  );
}
