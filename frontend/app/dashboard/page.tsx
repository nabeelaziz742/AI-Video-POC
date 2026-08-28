"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, User, VideoProject } from "../api";

function statusLabel(status: VideoProject["status"]) { return status.charAt(0).toUpperCase() + status.slice(1); }

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<VideoProject[]>([]);
  const [credits, setCredits] = useState<{ balance: number; monthly_allowance: number } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api<{ user: User }>("/auth/me/"), api<VideoProject[]>("/projects/"), api<{ balance: number; monthly_allowance: number }>("/credits/")])
      .then(([me, data, creditData]) => { setUser(me.user); setProjects(data); setCredits(creditData); })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function logout() { try { await api("/auth/logout/", { method: "POST" }); } finally { router.replace("/login"); } }
  if (loading) return <main className="flex min-h-screen items-center justify-center bg-[#08090d] text-sm text-white/50">Loading your workspace…</main>;

  return <main className="min-h-screen bg-[#08090d] text-white"><header className="border-b border-white/10 bg-[#0b0c11]/90"><div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-6 py-3"><div><p className="text-sm font-semibold">AI Video Studio</p><p className="text-xs text-white/35">{user?.username}</p></div><div className="flex items-center gap-3"><div className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/60">Credits: <span className="font-semibold text-white">{credits?.balance ?? "—"}</span></div><button onClick={() => router.push("/")} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:text-white">Create video</button><button onClick={logout} className="rounded-lg px-3 py-2 text-xs text-white/45 hover:text-white">Log out</button></div></div></header><div className="mx-auto max-w-7xl px-6 py-10"><div className="mb-8 flex items-end justify-between gap-4"><div><p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Dashboard</p><h1 className="text-3xl font-semibold tracking-tight">Your projects</h1><p className="mt-2 text-sm text-white/40">Create, monitor, and revisit your video projects.</p></div><button onClick={() => router.push("/")} className="rounded-xl bg-white px-4 py-3 text-sm font-semibold text-black">+ New video</button></div>{!projects.length ? <div className="rounded-3xl border border-dashed border-white/10 bg-white/[0.02] px-6 py-16 text-center"><h2 className="text-lg font-semibold">No videos yet</h2><p className="mx-auto mt-2 max-w-md text-sm text-white/35">Start with a story, add recurring characters, and generate your first video.</p><button onClick={() => router.push("/")} className="mt-6 rounded-xl bg-white px-4 py-3 text-sm font-semibold text-black">Create your first video</button></div> : <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{projects.map((project) => <button key={project.id} onClick={() => router.push(`/?project=${project.id}`)} className="rounded-2xl border border-white/10 bg-white/[0.025] p-5 text-left transition hover:border-white/20 hover:bg-white/[0.04]"><div className="flex items-start justify-between gap-3"><h2 className="font-semibold">{project.title}</h2><span className="rounded-full bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-wider text-white/45">{statusLabel(project.status)}</span></div><p className="mt-3 line-clamp-2 text-sm leading-6 text-white/35">{project.prompt}</p><div className="mt-5 flex items-center justify-between text-xs text-white/30"><span>{project.duration}s · {project.aspect_ratio}</span><span>{project.scenes.length} scenes</span></div></button>)}</div>}</div></main>;
}
