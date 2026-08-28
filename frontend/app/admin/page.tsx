"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import {
  api,
  User,
  AdminStats,
  AdminUserItem,
  AdminProjectItem,
  AdminSystemHealth,
} from "../api";

export default function AdminPage() {
  const router = useRouter();
  const [currentUser, setCurrentUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"overview" | "users" | "projects" | "system">("overview");

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [users, setUsers] = useState<AdminUserItem[]>([]);
  const [projects, setProjects] = useState<AdminProjectItem[]>([]);
  const [systemHealth, setSystemHealth] = useState<AdminSystemHealth | null>(null);

  const [userQuery, setUserQuery] = useState("");
  const [selectedUser, setSelectedUser] = useState<AdminUserItem | null>(null);
  const [creditAdjustmentAmount, setCreditAdjustmentAmount] = useState<number>(100);
  const [creditAdjustmentNote, setCreditAdjustmentNote] = useState("");
  const [adjusting, setAdjusting] = useState(false);
  const [adjustError, setAdjustError] = useState("");
  const [adjustSuccess, setAdjustSuccess] = useState("");

  useEffect(() => {
    api<{ user: User }>("/auth/me/")
      .then((res) => {
        if (!res.user.is_staff) {
          router.replace("/dashboard");
          return;
        }
        setCurrentUser(res.user);
        loadAdminData();
      })
      .catch(() => router.replace("/login"))
      .finally(() => setLoading(false));
  }, [router]);

  async function loadAdminData() {
    try {
      const [statsData, usersData, projectsData, systemData] = await Promise.all([
        api<AdminStats>("/admin/stats/"),
        api<{ users: AdminUserItem[] }>("/admin/users/"),
        api<{ projects: AdminProjectItem[] }>("/admin/projects/"),
        api<AdminSystemHealth>("/admin/system/"),
      ]);
      setStats(statsData);
      setUsers(usersData.users);
      setProjects(projectsData.projects);
      setSystemHealth(systemData);
    } catch {
      // Handled gracefully in UI
    }
  }

  async function searchUsers(e: FormEvent) {
    e.preventDefault();
    try {
      const res = await api<{ users: AdminUserItem[] }>(`/admin/users/?q=${encodeURIComponent(userQuery)}`);
      setUsers(res.users);
    } catch {
      // Ignored
    }
  }

  async function handleAdjustCredits(e: FormEvent) {
    e.preventDefault();
    if (!selectedUser || !creditAdjustmentAmount) return;
    setAdjusting(true);
    setAdjustError("");
    setAdjustSuccess("");
    try {
      await api(`/admin/users/${selectedUser.id}/credits/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          amount: creditAdjustmentAmount,
          note: creditAdjustmentNote || "Admin adjustment",
        }),
      });
      setAdjustSuccess(`Successfully adjusted ${selectedUser.username}'s credits by ${creditAdjustmentAmount > 0 ? "+" : ""}${creditAdjustmentAmount}.`);
      setCreditAdjustmentNote("");
      await loadAdminData();
      setTimeout(() => {
        setSelectedUser(null);
        setAdjustSuccess("");
      }, 1500);
    } catch (err) {
      setAdjustError(err instanceof Error ? err.message : "Credit adjustment failed.");
    } finally {
      setAdjusting(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#08090d] text-sm text-white/50">
        Authenticating Administrator Access…
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-[#08090d] text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0b0c11]/90">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="rounded-lg bg-amber-500/10 px-2.5 py-1 text-xs font-semibold uppercase tracking-wider text-amber-400 border border-amber-500/20">
              Admin
            </span>
            <div>
              <p className="text-sm font-semibold">Infrastructure Control Center</p>
              <p className="text-xs text-white/35">Logged in as {currentUser?.username}</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push("/")}
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:text-white"
            >
              Studio
            </button>
            <button
              onClick={() => router.push("/dashboard")}
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/65 hover:text-white"
            >
              Dashboard
            </button>
            <button
              onClick={() => api("/auth/logout/", { method: "POST" }).finally(() => router.replace("/login"))}
              className="rounded-lg px-3 py-2 text-xs text-white/45 hover:text-white"
            >
              Log out
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-7xl px-6 py-10">
        {/* Title & Tabs */}
        <div className="mb-8 flex flex-col justify-between gap-4 md:flex-row md:items-end">
          <div>
            <p className="mb-2 text-xs font-semibold uppercase tracking-[0.2em] text-amber-400">Administration</p>
            <h1 className="text-3xl font-semibold tracking-tight">System & Platform Health</h1>
            <p className="mt-2 text-sm text-white/40">
              Manage accounts, credit balances, generation reliability, and infrastructure configuration.
            </p>
          </div>
          <div className="flex rounded-xl border border-white/10 bg-white/[0.03] p-1">
            <button
              onClick={() => setActiveTab("overview")}
              className={`rounded-lg px-3.5 py-2 text-xs font-medium ${
                activeTab === "overview" ? "bg-white text-black" : "text-white/60 hover:text-white"
              }`}
            >
              Overview
            </button>
            <button
              onClick={() => setActiveTab("users")}
              className={`rounded-lg px-3.5 py-2 text-xs font-medium ${
                activeTab === "users" ? "bg-white text-black" : "text-white/60 hover:text-white"
              }`}
            >
              Users & Credits
            </button>
            <button
              onClick={() => setActiveTab("projects")}
              className={`rounded-lg px-3.5 py-2 text-xs font-medium ${
                activeTab === "projects" ? "bg-white text-black" : "text-white/60 hover:text-white"
              }`}
            >
              Projects
            </button>
            <button
              onClick={() => setActiveTab("system")}
              className={`rounded-lg px-3.5 py-2 text-xs font-medium ${
                activeTab === "system" ? "bg-white text-black" : "text-white/60 hover:text-white"
              }`}
            >
              System & Providers
            </button>
          </div>
        </div>

        {/* Top Metric Cards */}
        {stats && (
          <div className="mb-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-white/40">Total Accounts</p>
              <p className="mt-2 text-3xl font-semibold">{stats.users.total}</p>
              <p className="mt-1 text-xs text-white/30">{stats.users.staff} staff administrators</p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-white/40">Active Subscriptions</p>
              <p className="mt-2 text-3xl font-semibold text-emerald-400">{stats.subscriptions.active_total}</p>
              <p className="mt-1 text-xs text-white/30">
                {stats.subscriptions.by_plan.pro || 0} Pro · {stats.subscriptions.by_plan.creator || 0} Creator
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-white/40">Total Projects</p>
              <p className="mt-2 text-3xl font-semibold">{stats.projects.total}</p>
              <p className="mt-1 text-xs text-white/30">
                {stats.projects.completed} completed · {stats.projects.failed} failed
              </p>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-5">
              <p className="text-xs font-medium uppercase tracking-wider text-white/40">Circulating Credits</p>
              <p className="mt-2 text-3xl font-semibold text-violet-400">{stats.credits.total_circulating_balance}</p>
              <p className="mt-1 text-xs text-white/30">{stats.credits.total_consumed} total consumed</p>
            </div>
          </div>
        )}

        {/* Tab 1: Overview */}
        {activeTab === "overview" && stats && (
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-6">
              <h2 className="text-base font-semibold">Video Generation Pipeline</h2>
              <p className="mt-1 text-xs text-white/35">Scene and project pipeline distribution</p>
              <div className="mt-6 space-y-4">
                <div>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-white/60">Completed Scenes</span>
                    <span className="font-semibold text-emerald-400">{stats.scenes.completed}</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{
                        width: `${stats.scenes.total ? (stats.scenes.completed / stats.scenes.total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-white/60">In Processing</span>
                    <span className="font-semibold text-amber-400">{stats.scenes.processing}</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full bg-amber-500 rounded-full"
                      style={{
                        width: `${stats.scenes.total ? (stats.scenes.processing / stats.scenes.total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
                <div>
                  <div className="flex justify-between text-xs mb-1.5">
                    <span className="text-white/60">Failed Scenes</span>
                    <span className="font-semibold text-red-400">{stats.scenes.failed}</span>
                  </div>
                  <div className="h-2 rounded-full bg-white/5 overflow-hidden">
                    <div
                      className="h-full bg-red-500 rounded-full"
                      style={{
                        width: `${stats.scenes.total ? (stats.scenes.failed / stats.scenes.total) * 100 : 0}%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-6">
              <h2 className="text-base font-semibold">Usage & Operations Breakdown</h2>
              <p className="mt-1 text-xs text-white/35">Total events recorded across user actions</p>
              <div className="mt-6 grid grid-cols-2 gap-4">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <p className="text-xs text-white/40">Projects Created</p>
                  <p className="mt-1 text-2xl font-semibold">{stats.usage.projects}</p>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <p className="text-xs text-white/40">Scenes Generated</p>
                  <p className="mt-1 text-2xl font-semibold">{stats.usage.scenes}</p>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <p className="text-xs text-white/40">Character References</p>
                  <p className="mt-1 text-2xl font-semibold">{stats.usage.character_references}</p>
                </div>
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <p className="text-xs text-white/40">Final Assemblies</p>
                  <p className="mt-1 text-2xl font-semibold">{stats.usage.assemblies}</p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Users & Credits */}
        {activeTab === "users" && (
          <div>
            <form onSubmit={searchUsers} className="mb-6 flex gap-3">
              <input
                type="text"
                value={userQuery}
                onChange={(e) => setUserQuery(e.target.value)}
                placeholder="Search users by username or email…"
                className="w-full max-w-md rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm outline-none focus:border-white/20"
              />
              <button
                type="submit"
                className="rounded-xl border border-white/10 bg-white/[0.05] px-4 py-2.5 text-sm font-medium text-white hover:bg-white/[0.08]"
              >
                Search
              </button>
            </form>

            <div className="overflow-x-auto rounded-2xl border border-white/10 bg-white/[0.02]">
              <table className="w-full text-left text-xs">
                <thead className="border-b border-white/10 bg-white/[0.02] text-white/40 uppercase tracking-wider">
                  <tr>
                    <th className="px-5 py-3.5">User</th>
                    <th className="px-5 py-3.5">Plan</th>
                    <th className="px-5 py-3.5">Credit Balance</th>
                    <th className="px-5 py-3.5">Projects</th>
                    <th className="px-5 py-3.5">Joined</th>
                    <th className="px-5 py-3.5 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                  {users.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-5 py-8 text-center text-white/40">
                        No users found matching your search.
                      </td>
                    </tr>
                  ) : (
                    users.map((u) => (
                      <tr key={u.id} className="hover:bg-white/[0.02]">
                        <td className="px-5 py-4">
                          <div className="font-semibold text-white flex items-center gap-2">
                            {u.username}
                            {u.is_staff && (
                              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-[10px] text-amber-400 border border-amber-500/20">
                                STAFF
                              </span>
                            )}
                          </div>
                          <div className="text-white/40">{u.email || "No email"}</div>
                        </td>
                        <td className="px-5 py-4 uppercase font-medium text-white/70">
                          {u.plan_code} ({u.subscription_status})
                        </td>
                        <td className="px-5 py-4 font-semibold text-violet-300">
                          {u.credits_balance} credits
                        </td>
                        <td className="px-5 py-4 text-white/50">{u.total_projects}</td>
                        <td className="px-5 py-4 text-white/40">
                          {new Date(u.date_joined).toLocaleDateString()}
                        </td>
                        <td className="px-5 py-4 text-right">
                          <button
                            onClick={() => {
                              setSelectedUser(u);
                              setCreditAdjustmentAmount(100);
                              setCreditAdjustmentNote("Admin credit grant");
                              setAdjustError("");
                              setAdjustSuccess("");
                            }}
                            className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-white/70 hover:bg-white/10 hover:text-white"
                          >
                            Adjust Credits
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab 3: Projects */}
        {activeTab === "projects" && (
          <div className="overflow-x-auto rounded-2xl border border-white/10 bg-white/[0.02]">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-white/10 bg-white/[0.02] text-white/40 uppercase tracking-wider">
                <tr>
                  <th className="px-5 py-3.5">Project</th>
                  <th className="px-5 py-3.5">Owner</th>
                  <th className="px-5 py-3.5">Status</th>
                  <th className="px-5 py-3.5">Specs</th>
                  <th className="px-5 py-3.5">Scenes</th>
                  <th className="px-5 py-3.5">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {projects.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-white/40">
                      No projects recorded on the platform yet.
                    </td>
                  </tr>
                ) : (
                  projects.map((p) => (
                    <tr key={p.id} className="hover:bg-white/[0.02]">
                      <td className="px-5 py-4 font-medium text-white">
                        <div>{p.title} (V{p.version_number})</div>
                        {p.error_message && (
                          <div className="text-[11px] text-red-400 mt-1 line-clamp-1">{p.error_message}</div>
                        )}
                      </td>
                      <td className="px-5 py-4 text-white/60">{p.user?.username || "Unknown"}</td>
                      <td className="px-5 py-4">
                        <span
                          className={`rounded-full px-2.5 py-1 text-[10px] uppercase font-semibold tracking-wider ${
                            p.status === "completed"
                              ? "bg-emerald-500/10 text-emerald-400"
                              : p.status === "failed"
                              ? "bg-red-500/10 text-red-400"
                              : "bg-amber-500/10 text-amber-400"
                          }`}
                        >
                          {p.status}
                        </span>
                      </td>
                      <td className="px-5 py-4 text-white/40">
                        {p.duration}s · {p.aspect_ratio}
                      </td>
                      <td className="px-5 py-4 text-white/50">{p.scene_count}</td>
                      <td className="px-5 py-4 text-white/40">{new Date(p.created_at).toLocaleString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab 4: System & Providers */}
        {activeTab === "system" && systemHealth && (
          <div className="grid gap-6 md:grid-cols-2">
            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-base font-semibold">AI Video Providers</h2>
                <span
                  className={`rounded-full px-2.5 py-1 text-[10px] uppercase font-semibold ${
                    systemHealth.status === "healthy" ? "bg-emerald-500/10 text-emerald-400" : "bg-amber-500/10 text-amber-400"
                  }`}
                >
                  {systemHealth.status}
                </span>
              </div>
              <div className="space-y-4 text-xs">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-white">Fal.ai PixVerse</span>
                    <span className={systemHealth.providers.fal_pixverse.configured ? "text-emerald-400" : "text-red-400"}>
                      {systemHealth.providers.fal_pixverse.configured ? "Configured" : "Missing Key"}
                    </span>
                  </div>
                  <p className="text-white/40">Key: {systemHealth.providers.fal_pixverse.key_preview || "None"}</p>
                  <p className="text-white/40">Model: {systemHealth.providers.fal_pixverse.image_model}</p>
                </div>

                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-white">JSON2Video Service</span>
                    <span className={systemHealth.providers.json2video.configured ? "text-emerald-400" : "text-red-400"}>
                      {systemHealth.providers.json2video.configured ? "Configured" : "Missing Key"}
                    </span>
                  </div>
                  <p className="text-white/40">Key: {systemHealth.providers.json2video.key_preview || "None"}</p>
                </div>

                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-white">Stripe Billing</span>
                    <span className={systemHealth.providers.stripe.configured ? "text-emerald-400" : "text-amber-400"}>
                      {systemHealth.providers.stripe.configured ? "Active" : "Unconfigured"}
                    </span>
                  </div>
                  <p className="text-white/40">Secret Key: {systemHealth.providers.stripe.secret_key_preview || "None"}</p>
                  <p className="text-white/40">Webhook: {systemHealth.providers.stripe.webhook_preview || "None"}</p>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-6">
              <h2 className="text-base font-semibold mb-4">Storage & Environment</h2>
              <div className="space-y-4 text-xs">
                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-white">Primary Database</span>
                    <span className={systemHealth.database.connected ? "text-emerald-400" : "text-red-400"}>
                      {systemHealth.database.connected ? "Connected" : "Disconnected"}
                    </span>
                  </div>
                  <p className="text-white/40">Engine: {systemHealth.database.engine}</p>
                </div>

                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-semibold text-white">Storage Volumes</span>
                    <span className={systemHealth.storage.media_root_writable ? "text-emerald-400" : "text-amber-400"}>
                      {systemHealth.storage.media_root_writable ? "Writable" : "Read-only"}
                    </span>
                  </div>
                  <p className="text-white/40">Media Root: {systemHealth.storage.media_root_configured ? "Configured" : "Default"}</p>
                  <p className="text-white/40">Static Root: {systemHealth.storage.static_root_configured ? "Configured" : "Default"}</p>
                </div>

                <div className="rounded-xl border border-white/5 bg-white/[0.02] p-4">
                  <p className="font-semibold text-white mb-1">Security & Environment</p>
                  <p className="text-white/40">Debug Mode: {String(systemHealth.environment.debug)}</p>
                  <p className="text-white/40">Allowed Hosts: {systemHealth.environment.allowed_hosts.join(", ")}</p>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Credit Adjustment Modal */}
      {selectedUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
          <div className="w-full max-w-md rounded-2xl border border-white/10 bg-[#101117] p-6 shadow-2xl">
            <h2 className="text-lg font-semibold">Adjust User Credits</h2>
            <p className="mt-1 text-xs text-white/40">
              Update balance for <span className="text-white font-medium">{selectedUser.username}</span> ({selectedUser.email || "no email"})
            </p>

            <form onSubmit={handleAdjustCredits} className="mt-5 space-y-4">
              <div>
                <label className="block text-xs text-white/60 mb-1.5">Adjustment Amount (can be negative)</label>
                <input
                  type="number"
                  value={creditAdjustmentAmount}
                  onChange={(e) => setCreditAdjustmentAmount(Number(e.target.value))}
                  className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm outline-none focus:border-white/20"
                  required
                />
              </div>

              <div>
                <label className="block text-xs text-white/60 mb-1.5">Audit Reason / Note</label>
                <input
                  type="text"
                  value={creditAdjustmentNote}
                  onChange={(e) => setCreditAdjustmentNote(e.target.value)}
                  placeholder="e.g. Compensation for failed generation attempt"
                  className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2.5 text-sm outline-none focus:border-white/20"
                />
              </div>

              {adjustError && (
                <div role="alert" className="rounded-xl border border-red-500/20 bg-red-500/10 p-3 text-xs text-red-300">
                  {adjustError}
                </div>
              )}

              {adjustSuccess && (
                <div role="status" className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-3 text-xs text-emerald-300">
                  {adjustSuccess}
                </div>
              )}

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedUser(null)}
                  className="flex-1 rounded-xl border border-white/10 px-4 py-2.5 text-xs font-medium text-white/60 hover:text-white"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={adjusting}
                  className="flex-1 rounded-xl bg-white px-4 py-2.5 text-xs font-semibold text-black hover:bg-white/90 disabled:opacity-50"
                >
                  {adjusting ? "Processing…" : "Save Adjustment"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}
