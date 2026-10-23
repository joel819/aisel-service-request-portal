"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { BrandMark, BrandTitle } from "@/components/Header";
import { api, setToken } from "@/lib/api";

interface LoginResponse {
  access_token: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const data = await api<LoginResponse>("/api/auth/login", {
        method: "POST",
        body: { email, password },
        redirectOn401: false,
      });
      setToken(data.access_token);
      router.replace("/requests");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Login failed");
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-4">
      <div className="mb-6 flex flex-col items-center text-center">
        <BrandMark size="h-12 w-12" />
        <h1 className="mt-4 font-serif text-3xl font-bold">
          <BrandTitle className="text-3xl" />
        </h1>
        <p className="mt-1 text-sm text-ink/65">Sign in to manage client service requests</p>
      </div>
      <form onSubmit={handleSubmit} className="card space-y-4 p-6">
        <label className="block">
          <span className="mb-1 block text-sm font-bold text-ink">Email</span>
          <input
            type="email"
            required
            autoComplete="username"
            className="input"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="block">
          <span className="mb-1 block text-sm font-bold text-ink">Password</span>
          <input
            type="password"
            required
            autoComplete="current-password"
            className="input"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-[#b3261e] font-bold">
            {error}
          </p>
        )}
        <button type="submit" disabled={loading} className="btn-primary w-full">
          {loading ? "Signing in..." : "Sign in"}
        </button>
      </form>
    </main>
  );
}
