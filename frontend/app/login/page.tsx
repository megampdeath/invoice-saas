"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { signInWithEmail, signUpWithEmail } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    const fn = mode === "signin" ? signInWithEmail : signUpWithEmail;
    const { error } = await fn(email, password);
    setBusy(false);
    if (error) {
      setErr(error.message);
      return;
    }
    if (mode === "signup") {
      setErr("Check your email to confirm your account, then sign in.");
      return;
    }
    router.push("/app/invoices");
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 px-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-lg border bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Invoice SaaS</h1>
        <p className="text-sm text-gray-500">{mode === "signin" ? "Sign in to your workspace" : "Create your account"}</p>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-600">Email</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm" />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs font-medium text-gray-600">Password</span>
          <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded border border-gray-300 px-2 py-1.5 text-sm" />
        </label>
        {err && <p className="text-sm text-red-600">{err}</p>}
        <button disabled={busy} type="submit"
          className="w-full rounded bg-gray-900 px-3 py-2 text-sm font-medium text-white hover:bg-gray-700 disabled:opacity-50">
          {busy ? "…" : mode === "signin" ? "Sign in" : "Sign up"}
        </button>
        <button type="button" onClick={() => setMode(mode === "signin" ? "signup" : "signin")}
          className="w-full text-xs text-gray-500 hover:underline">
          {mode === "signin" ? "Need an account? Sign up" : "Already have an account? Sign in"}
        </button>
      </form>
    </div>
  );
}