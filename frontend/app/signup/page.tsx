"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { api } from "../api";

export default function SignupPage() {
  const [form, setForm] = useState({ username: "", email: "", password: "" });
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Post-Signup State
  const [createdEmail, setCreatedEmail] = useState<string | null>(null);
  const [resendBusy, setResendBusy] = useState(false);
  const [resendMessage, setResendMessage] = useState("");
  const [resendError, setResendError] = useState("");

  const isPasswordValid = form.password.length >= 8;
  const isUsernameValid = form.username.trim().length >= 3;
  const isEmailValid = Boolean(form.email.trim() && form.email.includes("@"));
  const canSubmit = isUsernameValid && isEmailValid && isPasswordValid && !busy;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError("");
    try {
      const emailToRegister = form.email.trim().toLowerCase();
      await api<{ message: string; email: string }>("/auth/signup/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: form.username.trim(),
          email: emailToRegister,
          password: form.password,
        }),
      });
      setCreatedEmail(emailToRegister);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create your account. Please check your details.");
    } finally {
      setBusy(false);
    }
  }

  async function handleSendVerificationEmail() {
    if (!createdEmail || resendBusy) return;
    setResendBusy(true);
    setResendMessage("");
    setResendError("");
    try {
      const data = await api<{ message: string }>("/auth/resend-verification/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: createdEmail }),
      });
      setResendMessage(data.message || "Verification email sent. Please check your inbox.");
    } catch (err) {
      setResendError(err instanceof Error ? err.message : "Unable to send verification email. Please try again.");
    } finally {
      setResendBusy(false);
    }
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center bg-[#08090d] px-4 py-12 text-white">
      <div className="w-full max-w-md">
        {/* Brand Header */}
        <div className="mb-8 text-center">
          <Link
            href="/"
            className="inline-flex items-center gap-2.5 rounded-full border border-white/10 bg-white/[0.03] px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400 hover:border-violet-500/30"
          >
            <span className="h-2 w-2 rounded-full bg-violet-400" />
            AI Video Studio
          </Link>
          <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">
            {createdEmail ? "Account Created" : "Get started free"}
          </h1>
          <p className="mt-2 text-sm text-white/50">
            {createdEmail
              ? "Your account has been created, but your email is not verified yet."
              : "Sign up to claim your 10 Free credits and start generating AI videos."}
          </p>
        </div>

        {/* Card */}
        <div className="rounded-3xl border border-white/10 bg-[#0d0e14]/80 p-8 shadow-2xl backdrop-blur-xl">
          {createdEmail ? (
            /* Post-Signup Dedicated Screen */
            <div className="py-2 text-center space-y-6 animate-fade-in">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-violet-500/10 text-3xl text-violet-400 border border-violet-500/20 shadow-lg shadow-violet-500/10">
                ✉
              </div>

              <div>
                <h2 className="text-xl font-bold text-white">Account Created</h2>
                <p className="mt-1.5 text-xs font-medium text-amber-300/90">
                  Your account has been created, but your email is not verified yet.
                </p>
                <p className="mt-3 text-xs leading-relaxed text-white/60">
                  We&apos;ve sent a verification link to your email (
                  <span className="font-semibold text-violet-300">{createdEmail}</span>). Please verify your email to
                  activate your account and receive your{" "}
                  <span className="font-semibold text-emerald-400">10 Free credits</span>.
                </p>
              </div>

              {resendMessage && (
                <div
                  role="status"
                  className="flex items-center justify-center gap-2 rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300"
                >
                  <svg className="h-4 w-4 shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                  </svg>
                  <span>{resendMessage}</span>
                </div>
              )}

              {resendError && (
                <div
                  role="alert"
                  className="flex items-center justify-center gap-2 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300"
                >
                  <svg className="h-4 w-4 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <span>{resendError}</span>
                </div>
              )}

              <div className="space-y-3 pt-2">
                <button
                  type="button"
                  id="send-verification-email-btn"
                  onClick={handleSendVerificationEmail}
                  disabled={resendBusy}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-6 py-3.5 text-sm font-semibold text-black transition hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 disabled:opacity-50 shadow-xl shadow-white/10"
                >
                  {resendBusy ? (
                    <>
                      <svg className="h-4 w-4 animate-spin text-black" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Sending email…
                    </>
                  ) : (
                    "Send Verification Email"
                  )}
                </button>

                <Link
                  href="/login"
                  id="go-to-login-btn"
                  className="flex w-full items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.04] px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-white/10"
                >
                  Go to Login
                </Link>
              </div>
            </div>
          ) : (
            /* Standard Signup Form */
            <>
              {error && (
                <div
                  role="alert"
                  className="mb-6 flex items-start gap-3 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-sm text-red-300"
                >
                  <svg className="h-5 w-5 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                    />
                  </svg>
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={submit} className="space-y-5">
                <div>
                  <label
                    htmlFor="signup-username"
                    className="mb-2 flex items-center justify-between text-xs font-medium uppercase tracking-wider text-white/60"
                  >
                    <span>Username</span>
                    {form.username && (
                      <span className={`text-[11px] lowercase ${isUsernameValid ? "text-emerald-400" : "text-amber-400"}`}>
                        {isUsernameValid ? "✓ valid" : "min 3 characters"}
                      </span>
                    )}
                  </label>
                  <input
                    id="signup-username"
                    required
                    minLength={3}
                    type="text"
                    value={form.username}
                    onChange={(e) => setForm({ ...form, username: e.target.value })}
                    autoComplete="username"
                    placeholder="Choose a unique username"
                    disabled={busy}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white placeholder-white/25 outline-none transition focus:border-violet-500 focus:ring-1 focus:ring-violet-500 disabled:opacity-50"
                  />
                </div>

                <div>
                  <label
                    htmlFor="signup-email"
                    className="mb-2 flex items-center justify-between text-xs font-medium uppercase tracking-wider text-white/60"
                  >
                    <span>Email Address</span>
                    {form.email && (
                      <span className={`text-[11px] lowercase ${isEmailValid ? "text-emerald-400" : "text-amber-400"}`}>
                        {isEmailValid ? "✓ valid" : "required"}
                      </span>
                    )}
                  </label>
                  <input
                    id="signup-email"
                    required
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    autoComplete="email"
                    placeholder="you@example.com"
                    disabled={busy}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white placeholder-white/25 outline-none transition focus:border-violet-500 focus:ring-1 focus:ring-violet-500 disabled:opacity-50"
                  />
                </div>

                <div>
                  <label
                    htmlFor="signup-password"
                    className="mb-2 flex items-center justify-between text-xs font-medium uppercase tracking-wider text-white/60"
                  >
                    <span>Password</span>
                    {form.password && (
                      <span className={`text-[11px] lowercase ${isPasswordValid ? "text-emerald-400" : "text-amber-400"}`}>
                        {isPasswordValid ? "✓ valid" : "min 8 characters"}
                      </span>
                    )}
                  </label>
                  <div className="relative">
                    <input
                      id="signup-password"
                      required
                      minLength={8}
                      type={showPassword ? "text" : "password"}
                      value={form.password}
                      onChange={(e) => setForm({ ...form, password: e.target.value })}
                      autoComplete="new-password"
                      placeholder="Create a strong password (8+ chars)"
                      disabled={busy}
                      className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 pr-11 text-sm text-white placeholder-white/25 outline-none transition focus:border-violet-500 focus:ring-1 focus:ring-violet-500 disabled:opacity-50"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                      className="absolute right-3 top-1/2 -translate-y-1/2 rounded-lg p-1 text-white/40 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                    >
                      {showPassword ? (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18"
                          />
                        </svg>
                      ) : (
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                          />
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                          />
                        </svg>
                      )}
                    </button>
                  </div>
                </div>

                <button
                  type="submit"
                  id="create-account-submit-btn"
                  disabled={!canSubmit}
                  className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-4 py-3.5 text-sm font-semibold text-black transition hover:bg-white/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-400 disabled:cursor-not-allowed disabled:opacity-40 shadow-xl shadow-white/10"
                >
                  {busy ? (
                    <>
                      <svg className="h-4 w-4 animate-spin text-black" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        />
                      </svg>
                      Creating account…
                    </>
                  ) : (
                    "Create free account (Get 10 Credits)"
                  )}
                </button>
              </form>

              <div className="mt-8 border-t border-white/5 pt-6 text-center text-sm text-white/40">
                Already have an account?{" "}
                <Link href="/login" className="font-medium text-violet-400 hover:text-violet-300 hover:underline">
                  Sign in
                </Link>
              </div>
            </>
          )}
        </div>

        {/* Back Link */}
        <p className="mt-6 text-center text-xs text-white/30">
          <Link href="/" className="hover:text-white/60">
            ← Back to home
          </Link>
        </p>
      </div>
    </main>
  );
}
