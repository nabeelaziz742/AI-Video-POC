"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { api, User } from "../api";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const tokenParam = searchParams.get("token") || "";

  const [tokenInput, setTokenInput] = useState(tokenParam);
  const [resendEmail, setResendEmail] = useState("");
  const [statusState, setStatusState] = useState<"idle" | "verifying" | "success" | "error">(
    tokenParam ? "verifying" : "idle"
  );
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isAlreadyUsed, setIsAlreadyUsed] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [resendSuccess, setResendSuccess] = useState("");

  useEffect(() => {
    if (!tokenParam) return;
    performVerification(tokenParam);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenParam]);

  async function performVerification(tok: string) {
    if (!tok.trim()) return;
    setStatusState("verifying");
    setError("");
    setIsAlreadyUsed(false);
    try {
      const data = await api<{ message: string; user: User }>("/auth/verify-email/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: tok.trim() }),
      });
      setStatusState("success");
      setMessage(data.message || "Email verified successfully! 10 Free credits have been granted to your account.");
      const redirectTimer = setTimeout(() => {
        router.push("/dashboard");
      }, 1500);
      return () => clearTimeout(redirectTimer);
    } catch (err) {
      setStatusState("error");
      const errText = err instanceof Error ? err.message : "Verification failed.";
      if (errText.toLowerCase().includes("already been used")) {
        setIsAlreadyUsed(true);
        setError("This verification link has already been used.");
      } else if (errText.toLowerCase().includes("invalid or expired") || errText.toLowerCase().includes("expired")) {
        setError("Invalid or expired verification link.");
      } else {
        setError(errText || "Invalid or expired verification link.");
      }
    }
  }

  async function handleManualSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!tokenInput.trim()) return;
    await performVerification(tokenInput);
  }

  async function handleResend(e: React.FormEvent) {
    e.preventDefault();
    if (!resendEmail.trim()) return;
    setResendBusy(true);
    setResendSuccess("");
    setError("");
    try {
      const data = await api<{ message: string }>("/auth/resend-verification/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: resendEmail.trim() }),
      });
      setResendSuccess(data.message || "Verification email sent. Please check your inbox.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to resend verification email.");
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
          <h1 className="mt-4 text-3xl font-bold tracking-tight sm:text-4xl">Verify your email</h1>
          <p className="mt-2 text-sm text-white/50">
            Activate your account and claim your 10 Free credits.
          </p>
        </div>

        {/* Card */}
        <div className="rounded-3xl border border-white/10 bg-[#0d0e14]/80 p-8 shadow-2xl backdrop-blur-xl">
          {statusState === "verifying" && (
            <div className="py-8 text-center space-y-4">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-violet-400">
                <svg className="h-6 w-6 animate-spin" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
                  <path
                    className="opacity-75"
                    fill="currentColor"
                    d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                  />
                </svg>
              </div>
              <h2 className="text-lg font-bold text-white">Verifying your token…</h2>
              <p className="text-xs text-white/40">
                Please wait while we activate your account and grant your 10 Free credits.
              </p>
            </div>
          )}

          {statusState === "success" && (
            <div className="py-6 text-center space-y-4">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-500/10 text-3xl text-emerald-400 border border-emerald-500/20 shadow-lg shadow-emerald-500/10 animate-bounce">
                ✓
              </div>
              <h2 className="text-xl font-bold text-white">Account Activated!</h2>
              <p className="text-xs leading-relaxed text-emerald-300">
                {message}
              </p>
              <p className="text-[11px] text-white/40">Redirecting directly to your dashboard…</p>
              <div className="pt-2">
                <Link
                  href="/dashboard"
                  id="verified-dashboard-btn"
                  className="inline-flex w-full items-center justify-center rounded-2xl bg-white px-6 py-3.5 text-sm font-semibold text-black transition hover:bg-white/90 shadow-xl shadow-white/10"
                >
                  Go to Dashboard →
                </Link>
              </div>
            </div>
          )}

          {(statusState === "idle" || statusState === "error") && (
            <div>
              {error && (
                <div
                  role="alert"
                  className="mb-6 flex items-start gap-3 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-xs text-red-300"
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

              {isAlreadyUsed ? (
                /* Already used token state */
                <div className="space-y-4">
                  <p className="text-xs text-white/60 leading-relaxed">
                    This verification link has already been used to activate your account. If you are already active, you can go straight to your dashboard or sign in.
                  </p>
                  <div className="space-y-3 pt-2">
                    <Link
                      href="/dashboard"
                      id="already-used-dashboard-btn"
                      className="inline-flex w-full items-center justify-center rounded-2xl bg-white px-6 py-3.5 text-sm font-semibold text-black transition hover:bg-white/90 shadow-xl shadow-white/10"
                    >
                      Go to Dashboard →
                    </Link>
                    <Link
                      href="/login"
                      className="inline-flex w-full items-center justify-center rounded-2xl border border-white/10 bg-white/[0.04] px-6 py-3.5 text-sm font-semibold text-white transition hover:bg-white/10"
                    >
                      Go to Login
                    </Link>
                  </div>
                </div>
              ) : (
                /* Standard verification form & resend */
                <>
                  <form onSubmit={handleManualSubmit} className="space-y-4">
                    <div>
                      <label
                        htmlFor="verify-token-input"
                        className="mb-2 block text-xs font-medium uppercase tracking-wider text-white/60"
                      >
                        Enter Verification Token
                      </label>
                      <input
                        id="verify-token-input"
                        type="text"
                        required
                        value={tokenInput}
                        onChange={(e) => setTokenInput(e.target.value)}
                        placeholder="Paste verification token here"
                        className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm text-white placeholder-white/25 outline-none transition focus:border-violet-500"
                      />
                    </div>

                    <button
                      type="submit"
                      id="verify-token-submit-btn"
                      disabled={!tokenInput.trim()}
                      className="w-full rounded-2xl bg-white px-6 py-3.5 text-sm font-semibold text-black transition hover:bg-white/90 shadow-xl shadow-white/10 disabled:cursor-not-allowed disabled:opacity-40"
                    >
                      Verify Token & Activate Account
                    </button>
                  </form>

                  {/* Resend Section */}
                  <div className="mt-8 border-t border-white/10 pt-6">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-white/40 mb-3">
                      Didn&apos;t receive a verification link?
                    </h3>

                    {resendSuccess && (
                      <p className="mb-3 text-xs text-emerald-400">✓ {resendSuccess}</p>
                    )}

                    <form onSubmit={handleResend} className="flex gap-2">
                      <input
                        type="email"
                        required
                        value={resendEmail}
                        onChange={(e) => setResendEmail(e.target.value)}
                        placeholder="Your account email address"
                        disabled={resendBusy}
                        className="flex-1 rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder-white/25 outline-none transition focus:border-violet-500 disabled:opacity-50"
                      />
                      <button
                        type="submit"
                        disabled={resendBusy || !resendEmail.trim()}
                        className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-white/10 disabled:opacity-40"
                      >
                        {resendBusy ? "Sending…" : "Resend"}
                      </button>
                    </form>
                  </div>
                </>
              )}
            </div>
          )}

          <div className="mt-6 border-t border-white/5 pt-4 text-center text-xs text-white/40">
            Already verified?{" "}
            <Link href="/login" className="font-medium text-violet-400 hover:text-violet-300">
              Sign in to Studio
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center bg-[#08090d] text-sm text-white/50">
          Loading verification…
        </main>
      }
    >
      <VerifyEmailContent />
    </Suspense>
  );
}
