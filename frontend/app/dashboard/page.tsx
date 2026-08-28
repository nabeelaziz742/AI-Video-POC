"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, User, VideoProject } from "../api";
import BillingPanel from "../components/BillingPanel";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [credits, setCredits] = useState<{ balance: number; monthly_allowance: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const [filterQuery, setFilterQuery] = useState("");
  const [filterStatus, setFilterStatus] = useState<string>("all");

  useEffect(() => {
    Promise.all([
      api<{ user: User }>("/auth/me/"),
      api<VideoProject[]>("/projects/"),
      api<{ balance: number; monthly_allowance: number }>("/credits/"),
    ])
      .then(([me, data, creditData]) => {
        setUser(me.user);
        setProjects(data);
        setCredits(creditData);
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function logout() {
    try {
      await api("/auth/logout/", { method: "POST" });
    } finally {
      router.replace("/login");
    }
  }

  const filteredProjects = projects.filter((p) => {
    const matchesQuery =
      p.title.toLowerCase().includes(filterQuery.toLowerCase()) ||
      p.prompt.toLowerCase().includes(filterQuery.toLowerCase());
    const matchesStatus = filterStatus === "all" || p.status === filterStatus;
    return matchesQuery && matchesStatus;
  });

  const renderStatusBadge = (status: VideoProject["status"]) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-400 border border-emerald-500/20">
            <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Completed
          </span>
        );
      case "processing":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-amber-400 border border-amber-500/20">
            <svg className="h-3 w-3 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Processing
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-red-400 border border-red-500/20">
            <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Failed
          </span>
        );
      case "queued":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-blue-400 border border-blue-500/20">
            <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <circle cx="12" cy="12" r="9" />
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 7v5l3 3" />
            </svg>
            Queued
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-white/50 border border-white/10">
            Draft
          </span>
        );
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen bg-[#08090d] text-white">
        <header className="border-b border-white/10 bg-[#0b0c11]/90">
          <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between px-6 py-3">
            <div className="h-4 w-32 animate-pulse rounded bg-white/10" />
            <div className="h-8 w-24 animate-pulse rounded-lg bg-white/10" />
          </div>
        </header>
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="animate-pulse space-y-6">
            <div className="h-8 w-48 rounded bg-white/10" />
            <div className="h-32 rounded-3xl bg-white/5" />
            <div className="grid gap-4 md:grid-cols-3">
              <div className="h-44 rounded-2xl bg-white/5" />
              <div className="h-44 rounded-2xl bg-white/5" />
              <div className="h-44 rounded-2xl bg-white/5" />
            </div>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#08090d] text-white">
      {/* Top Header */}
      <header className="border-b border-white/10 bg-[#0b0c11]/90 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-6 py-3">
          <Link href="/" className="flex items-center gap-2.5">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600 text-xs font-bold text-white shadow-lg shadow-violet-500/20">
              AI
            </span>
            <div>
              <p className="text-sm font-semibold tracking-tight">AI Video Studio</p>
              <p className="text-[11px] text-white/40">{user?.username}</p>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            {user?.is_staff && (
              <button
                onClick={() => router.push("/admin")}
                className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-400 transition hover:bg-amber-500/20"
              >
                Admin
              </button>
            )}
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/70">
              Credits: <span className="font-semibold text-violet-300">{credits?.balance ?? "—"}</span>
            </div>
            <button
              onClick={() => router.push("/")}
              className="rounded-lg border border-white/10 bg-white/[0.04] px-3.5 py-1.5 text-xs font-medium text-white transition hover:bg-white/10"
            >
              + Create Video
            </button>
            <button
              onClick={logout}
              className="rounded-lg px-3 py-1.5 text-xs text-white/45 transition hover:text-white"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      {/* Main Container */}
      <div className="mx-auto max-w-7xl px-6 py-10">
        {/* Page Title & New Project CTA */}
        <div className="mb-8 flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Workspace</p>
            <h1 className="text-3xl font-bold tracking-tight">Your Video Projects</h1>
            <p className="mt-1 text-sm text-white/45">
              Review generated videos, check rendering status, and branch new versions.
            </p>
          </div>
          <button
            onClick={() => router.push("/")}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-white px-5 py-3 text-sm font-semibold text-black transition hover:bg-white/90 shadow-lg shadow-white/5"
          >
            <span>+</span> New Video
          </button>
        </div>

        {/* Subscription & Billing */}
        <BillingPanel />

        {/* Search & Filter Bar */}
        <div className="mt-8 mb-6 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div className="relative flex-1 max-w-md">
            <input
              type="text"
              value={filterQuery}
              onChange={(e) => setFilterQuery(e.target.value)}
              placeholder="Search videos by title or prompt…"
              className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-xs text-white placeholder-white/30 outline-none transition focus:border-violet-500/60"
            />
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-white/40">Status:</span>
            <select
              value={filterStatus}
              onChange={(e) => setFilterStatus(e.target.value)}
              className="rounded-xl border border-white/10 bg-[#101117] px-3 py-2 text-xs text-white outline-none focus:border-violet-500/60"
            >
              <option value="all">All Statuses ({projects.length})</option>
              <option value="completed">Completed</option>
              <option value="processing">Processing</option>
              <option value="queued">Queued</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>

        {/* Projects Grid or Empty State */}
        {!projects.length ? (
          <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.015] px-6 py-16 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-2xl text-violet-400">
              🎬
            </div>
            <h2 className="text-lg font-bold text-white">No video projects yet</h2>
            <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-white/40">
              Start with a story prompt, configure recurring characters with visual styles, and let our pipeline generate multi-scene consistent videos.
            </p>
            <button
              onClick={() => router.push("/")}
              className="mt-6 rounded-xl bg-white px-5 py-3 text-xs font-semibold text-black transition hover:bg-white/90"
            >
              Create your first video
            </button>
          </div>
        ) : !filteredProjects.length ? (
          <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-8 text-center text-xs text-white/45">
            No projects matched your search query &quot;{filterQuery}&quot;.
          </div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filteredProjects.map((project) => (
              <button
                key={project.id}
                onClick={() => router.push(`/?project=${project.id}`)}
                className="group relative flex flex-col justify-between rounded-2xl border border-white/10 bg-white/[0.025] p-5 text-left transition hover:border-violet-500/40 hover:bg-white/[0.04]"
              >
                <div>
                  <div className="flex items-start justify-between gap-3">
                    <h2 className="font-semibold text-white group-hover:text-violet-300 transition line-clamp-1">
                      {project.title}
                    </h2>
                    {renderStatusBadge(project.status)}
                  </div>

                  <p className="mt-3 line-clamp-2 text-xs leading-relaxed text-white/40">
                    {project.prompt}
                  </p>
                </div>

                <div className="mt-6 border-t border-white/5 pt-3.5 flex items-center justify-between text-[11px] text-white/35">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-white/60">V{project.version_number}</span>
                    <span>·</span>
                    <span>{project.duration}s ({project.aspect_ratio})</span>
                  </div>
                  <span>{project.scenes?.length || 0} scenes</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}
