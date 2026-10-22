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
        <div className="flex items-center gap-5">
          <Link href="/requests" className="flex items-center gap-2 font-semibold text-slate-900">
            <BrandMark />
            <span className="hidden sm:inline">Service Requests</span>
          </Link>
          <Link href="/assistant" className="text-sm font-medium text-slate-600 hover:text-indigo-600">
            Assistant
          </Link>
        </div>
        <button onClick={logout} className="btn-secondary px-3 py-1.5">
          Log out
        </button>
      </div>
    </header>
  );
}
