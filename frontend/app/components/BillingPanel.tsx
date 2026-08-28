"use client";

import { useEffect, useState } from "react";
import { api, CreditBalance } from "../api";

type Plan = {
  code: string;
  name: string;
  monthly_price_usd: string;
  monthly_credits: number;
  max_duration: number;
  available: boolean;
};

type Subscription = {
  plan_code: string;
  status: string;
  provider: string;
  current_period_start: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
};

type BillingData = {
  plans: Plan[];
  subscription: Subscription;
  credits: CreditBalance;
};

export default function BillingPanel() {
  const [data, setData] = useState<BillingData | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    Promise.all([
      api<{ plans: Plan[] }>("/billing/plans/"),
      api<Subscription>("/billing/subscription/"),
      api<CreditBalance>("/credits/"),
    ])
      .then(([planData, subscription, credits]) => {
        if (active) setData({ plans: planData.plans, subscription, credits });
      })
      .catch(() => {
        if (active) setMessage("Unable to load billing details.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  async function refresh() {
    const [planData, subscription, credits] = await Promise.all([
      api<{ plans: Plan[] }>("/billing/plans/"),
      api<Subscription>("/billing/subscription/"),
      api<CreditBalance>("/credits/"),
    ]);
    setData({ plans: planData.plans, subscription, credits });
  }

  async function choose(plan: Plan) {
    setBusy(plan.code);
    setMessage("");
    try {
      const result = await api<{ checkout_url?: string; plan_code?: string }>(
        "/billing/subscription/change/",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ plan_code: plan.code }),
        }
      );
      if (result.checkout_url) {
        window.location.assign(result.checkout_url);
      } else {
        await refresh();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Unable to process plan change.");
    } finally {
      setBusy(null);
    }
  }

  const plans = data?.plans ?? [];
  const subscription = data?.subscription;
  const credits = data?.credits;

  if (loading) {
    return (
      <section className="mb-8 rounded-3xl border border-white/10 bg-white/[0.02] p-6">
        <div className="animate-pulse space-y-4">
          <div className="h-4 w-32 rounded bg-white/10" />
          <div className="h-8 w-48 rounded bg-white/10" />
          <div className="grid gap-4 md:grid-cols-3">
            <div className="h-40 rounded-2xl bg-white/5" />
            <div className="h-40 rounded-2xl bg-white/5" />
            <div className="h-40 rounded-2xl bg-white/5" />
          </div>
        </div>
      </section>
    );
  }

  return (
    <section aria-labelledby="billing-section-title" className="mb-8 rounded-3xl border border-white/10 bg-white/[0.025] p-6 shadow-xl">
      {/* Header Info */}
      <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-center">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Subscription & Credits</p>
          <h2 id="billing-section-title" className="mt-1 text-xl font-bold tracking-tight text-white">
            Plan & Generation Allowance
          </h2>
          <p className="mt-1 text-xs text-white/45">
            Active Tier: <span className="font-semibold uppercase text-white">{subscription?.plan_code || "Free"}</span> · Available Balance:{" "}
            <span className="font-semibold text-violet-300">{credits?.balance ?? 0} Credits</span>
          </p>
        </div>

        <div className="flex items-center gap-2">
          {subscription?.cancel_at_period_end && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-300">
              Canceling at end of cycle
            </span>
          )}
          <span className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs uppercase tracking-wider text-white/60">
            {subscription?.status || "Active"}
          </span>
        </div>
      </div>

      {message && (
        <div role="alert" className="mt-4 rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
          {message}
        </div>
      )}

      {/* 3-Column Plan Grid */}
      <div className="mt-6 grid gap-4 md:grid-cols-3">
        {plans.map((plan) => {
          const isCurrent = plan.code === subscription?.plan_code;
          const isBusy = busy === plan.code;

          return (
            <div
              key={plan.code}
              className={`relative flex flex-col justify-between rounded-2xl border p-5 transition ${
                isCurrent
                  ? "border-violet-500/60 bg-violet-500/10 shadow-lg shadow-violet-500/5"
                  : "border-white/10 bg-white/[0.02] hover:border-white/20"
              }`}
            >
              <div>
                <div className="flex items-center justify-between">
                  <h3 className="font-bold text-white">{plan.name}</h3>
                  {isCurrent && (
                    <span className="rounded-full bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-violet-300 border border-violet-500/30">
                      Active
                    </span>
                  )}
                </div>

                <div className="mt-3 flex items-baseline gap-1">
                  <span className="text-3xl font-extrabold text-white">${plan.monthly_price_usd}</span>
                  <span className="text-xs text-white/40">/month</span>
                </div>

                <ul className="mt-4 space-y-2 text-xs text-white/60">
                  <li className="flex items-center gap-2">
                    <svg className="h-4 w-4 shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span><strong>{plan.monthly_credits}</strong> monthly credits</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <svg className="h-4 w-4 shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Up to <strong>{plan.max_duration}s</strong> video duration</span>
                  </li>
                  <li className="flex items-center gap-2">
                    <svg className="h-4 w-4 shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                    <span>Character continuity engine</span>
                  </li>
                </ul>
              </div>

              <div className="mt-6">
                <button
                  type="button"
                  disabled={!plan.available || isCurrent || busy !== null}
                  onClick={() => choose(plan)}
                  className={`w-full rounded-xl py-2.5 text-xs font-semibold transition ${
                    isCurrent
                      ? "bg-white/10 text-white/50 cursor-default"
                      : plan.available
                      ? "bg-white text-black hover:bg-white/90"
                      : "bg-white/5 text-white/30 cursor-not-allowed"
                  }`}
                >
                  {isBusy
                    ? "Processing Checkout…"
                    : isCurrent
                    ? "Current Plan"
                    : plan.available
                    ? `Upgrade to ${plan.name}`
                    : "Not Configured"}
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
