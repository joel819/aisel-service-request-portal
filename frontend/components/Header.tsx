"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";

import { clearToken } from "@/lib/api";

export function BrandMark({ size = "h-9 w-9" }: { size?: string }) {
  return (
    <span
      className={`flex ${size} items-center justify-center rounded-xl border-2 border-ink bg-sun text-sm font-bold text-ink shadow-hard-sm`}
    >
      SR
    </span>
  );
}

export function BrandTitle({ className = "text-xl" }: { className?: string }) {
  return (
    <span className={`font-serif font-bold ${className}`}>
      Service <span className="shadow-[inset_0_-0.4em_0_0_#36d6a0]">Requests</span>
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
    <header className="sticky top-0 z-10 border-b-2 border-ink bg-cream">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3">
        <div className="flex items-center gap-5">
          <Link href="/requests" className="flex items-center gap-3">
            <BrandMark />
            <span className="hidden sm:inline">
              <BrandTitle />
            </span>
          </Link>
          <Link href="/assistant" className="text-sm font-bold underline decoration-lilac decoration-2 underline-offset-4">
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
