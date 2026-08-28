"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { api, User } from "../api";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError("");
    try { await api<{ user: User }>("/auth/signup/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(form) }); router.push("/dashboard"); router.refresh(); }
    catch (err) { setError(err instanceof Error ? err.message : "Unable to create your account."); }
    finally { setBusy(false); }
  }

  return <main className="flex min-h-screen items-center justify-center bg-[#08090d] px-6 text-white"><div className="w-full max-w-md rounded-3xl border border-white/10 bg-white/[0.025] p-8 shadow-2xl"><div className="mb-8"><p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">AI Video Studio</p><h1 className="text-3xl font-semibold tracking-tight">Create your account</h1><p className="mt-2 text-sm text-white/45">Your projects stay private to your account.</p></div><form onSubmit={submit} className="space-y-5"><label className="block"><span className="mb-2 block text-sm text-white/65">Username</span><input required minLength={3} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} autoComplete="username" className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 outline-none focus:border-violet-500/60" /></label><label className="block"><span className="mb-2 block text-sm text-white/65">Email <span className="text-white/25">(optional)</span></span><input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} autoComplete="email" className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 outline-none focus:border-violet-500/60" /></label><label className="block"><span className="mb-2 block text-sm text-white/65">Password</span><input required minLength={8} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" className="w-full rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 outline-none focus:border-violet-500/60" /></label>{error && <p role="alert" className="rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">{error}</p>}<button disabled={busy} className="w-full rounded-xl bg-white px-4 py-3 font-semibold text-black disabled:cursor-not-allowed disabled:opacity-50">{busy ? "Creating account…" : "Create account"}</button></form><p className="mt-6 text-center text-sm text-white/40">Already have an account? <a href="/login" className="text-white hover:underline">Sign in</a></p></div></main>;
}
