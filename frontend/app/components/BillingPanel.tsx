"use client";

import { useEffect, useState } from "react";
import { api, CreditBalance } from "../api";

type Plan = { code: string; name: string; monthly_price_usd: string; monthly_credits: number; max_duration: number; available: boolean };
type Subscription = { plan_code: string; status: string; provider: string; current_period_start: string | null; current_period_end: string | null; cancel_at_period_end: boolean };

type BillingData = { plans: Plan[]; subscription: Subscription; credits: CreditBalance };

export default function BillingPanel() {
  const [data, setData] = useState<BillingData | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let active = true;
    Promise.all([
      api<{ plans: Plan[] }>("/billing/plans/"),
      api<Subscription>("/billing/subscription/"),
      api<CreditBalance>("/credits/"),
    ]).then(([planData, subscription, credits]) => {
      if (active) setData({ plans: planData.plans, subscription, credits });
    }).catch(() => {
      if (active) setMessage("Unable to load billing information.");
    });
    return () => { active = false; };
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
    setBusy(plan.code); setMessage("");
    try {
      const result = await api<{ checkout_url?: string; plan_code?: string }>("/billing/subscription/change/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ plan_code: plan.code }) });
      if (result.checkout_url) window.location.assign(result.checkout_url);
      else await refresh();
    } catch (error) { setMessage(error instanceof Error ? error.message : "Unable to change plan."); }
    finally { setBusy(null); }
  }

  const plans = data?.plans ?? [];
  const subscription = data?.subscription;
  const credits = data?.credits;

  return <section className="mt-8 rounded-2xl border border-white/10 bg-white/[0.025] p-5"><div className="flex flex-wrap items-start justify-between gap-4"><div><p className="text-xs font-semibold uppercase tracking-[0.18em] text-violet-400">Billing</p><h2 className="mt-1 text-lg font-semibold">Plan & credits</h2><p className="mt-1 text-sm text-white/35">Current plan: {subscription?.plan_code ?? "—"} · {credits?.balance ?? "—"} credits</p></div><span className="rounded-full bg-white/5 px-3 py-1.5 text-xs text-white/55">{subscription?.status ?? "loading"}</span></div>{message && <p className="mt-4 rounded-lg border border-white/10 px-3 py-2 text-sm text-white/60">{message}</p>}<div className="mt-5 grid gap-3 md:grid-cols-3">{plans.map((plan) => <div key={plan.code} className="rounded-xl border border-white/10 p-4"><div className="flex items-center justify-between"><h3 className="font-semibold">{plan.name}</h3>{plan.code === subscription?.plan_code && <span className="text-[10px] uppercase tracking-wider text-violet-300">Current</span>}</div><p className="mt-3 text-2xl font-semibold">${plan.monthly_price_usd}<span className="text-xs font-normal text-white/35"> / month</span></p><p className="mt-1 text-xs text-white/40">{plan.monthly_credits} credits · up to {plan.max_duration}s</p><button disabled={!plan.available || plan.code === subscription?.plan_code || busy !== null} onClick={() => choose(plan)} className="mt-4 w-full rounded-lg bg-white px-3 py-2 text-xs font-semibold text-black disabled:cursor-not-allowed disabled:opacity-30">{busy === plan.code ? "Opening checkout…" : plan.code === subscription?.plan_code ? "Current plan" : plan.available ? "Choose plan" : "Not configured"}</button></div>)}</div></section>;
}
