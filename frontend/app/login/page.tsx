"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError } from "@/lib/api";
import { useAuth } from "@/components/auth-provider";

export default function LoginPage() {
  const { login, user, loading } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (!loading && user) router.replace("/dashboard"); }, [loading, user, router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setBusy(true);
    try {
      await login(email, password);
      router.replace("/dashboard");
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "Unable to sign in. Check the API connection and try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <div className="brand-mark" aria-hidden="true">E</div>
        <p className="eyebrow">Enterprise operations</p>
        <h1 id="login-title">Sign in to EAMMS</h1>
        <p className="muted">Manage assets, maintenance, and custody from one workspace.</p>
        <form className="form-stack" onSubmit={submit}>
          <label className="field">
            <span>Email address</span>
            <input type="email" autoComplete="username" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label className="field">
            <span>Password</span>
            <input type="password" autoComplete="current-password" required value={password} onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <p className="alert alert-error" role="alert">{error}</p>}
          <button className="button button-primary button-wide" type="submit" disabled={busy || loading}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
        <p className="login-footnote">Accounts are created by your EAMMS administrator.</p>
      </section>
    </main>
  );
}
