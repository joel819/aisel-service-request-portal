"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { clearToken } from "@/lib/api";

export function Header() {
  const router = useRouter();

  function logout() {
    clearToken();
    router.replace("/login");
  }

  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <Link href="/requests" className="font-semibold">
          Service Requests
        </Link>
        <button onClick={logout} className="text-sm text-slate-600 hover:text-slate-900">
          Log out
        </button>
      </div>
    </header>
  );
}
