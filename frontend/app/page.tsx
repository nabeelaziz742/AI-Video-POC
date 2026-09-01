"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, InputType, User, VideoJob, VideoProject } from "./api";

import { CharacterDraft, emptyCharacter } from "./character-types";
import { CharacterEditor } from "./components/CharacterEditor";
import { FinalVideo } from "./components/FinalVideo";
import { ProgressPanel } from "./components/ProgressPanel";
import { VersionHistoryDrawer } from "./components/VersionHistoryDrawer";
import { Toast } from "./components/Toast";

const initialCharacter: CharacterDraft = {
  name: "Protagonist",
  role: "main character",
  age_description: "young adult in their 20s",
  appearance: "distinctive friendly face, expressive eyes, well-proportioned features",
  clothing: "modern stylish apparel suited for their adventure",
  personality: "curious, determined, and expressive",
  description: "The central character in the story",
  visual_prompt: "polished 3D animated character, Pixar and DreamWorks inspired, soft cinematic lighting",
};

export default function Home() {
  const router = useRouter();
  const promptInputRef = useRef<HTMLTextAreaElement>(null);

  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);

  // Form State
  const [inputType, setInputType] = useState<InputType>("story");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [characters, setCharacters] = useState<CharacterDraft[]>([initialCharacter]);
  const [showAdvancedControl, setShowAdvancedControl] = useState(false);
  const [versionsDrawerOpen, setVersionsDrawerOpen] = useState(false);

  // Project & Job Pipeline State
  const [project, setProject] = useState<VideoProject | null>(null);
  const [currentJob, setCurrentJob] = useState<VideoJob | null>(null);
  const [busy, setBusy] = useState(false);
  const [busySceneId, setBusySceneId] = useState<number | null>(null);
  const [progress, setProgress] = useState("Ready");
  const [error, setError] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [toastType, setToastType] = useState<"success" | "error" | "info">("info");

  const planCode = user?.plan_code || "free";
  const isPaidUser = planCode === "creator" || planCode === "pro";
  const maxAllowedDuration = planCode === "pro" ? 60 : planCode === "creator" ? 30 : 10;
  const creditsBalance = user?.credits_balance ?? 0;

  useEffect(() => {
    api<{ user: User }>("/auth/me/")
      .then((data) => {
        setUser(data.user);
      })
      .catch(() => {
        setUser(null);
      })
      .finally(() => setAuthLoading(false));

    const projectId = Number(new URLSearchParams(window.location.search).get("project"));
    if (projectId) {
      api<VideoProject>(`/projects/${projectId}/status/`)
        .then((p) => {
          setProject(p);
          setTitle(p.title);
          setPrompt(p.prompt);
          setInputType(p.input_type);
          setDuration(p.duration);
          setAspectRatio(p.aspect_ratio);
        })
        .catch(() => undefined);
    }
  }, []);

  async function pollJob(jobId: number, projectId: number) {
    for (;;) {
      const job = await api<VideoJob>(`/jobs/${jobId}/`);
      setCurrentJob(job);

      // Fetch refreshed project status to update scene clips & characters in real time
      try {
        const p = await api<VideoProject>(`/projects/${projectId}/status/`);
        setProject(p);
      } catch {
        // Ignore transient status errors
      }

      if (job.status === "completed") {
        setProgress("Video Ready");
        return job;
      }
      if (job.status === "failed") {
        throw new Error(job.error_message || "Video generation encountered an error.");
      }
      if (job.status === "cancelled") {
        throw new Error("Job was cancelled by user.");
      }

      // Map progress text based on current stage
      if (job.current_stage === "character_reference") {
        setProgress("Generating character consistency references…");
      } else if (job.current_stage === "generating_scenes") {
        setProgress(`Generating scene clips (${job.completed_scenes}/${job.total_scenes})…`);
      } else if (job.current_stage === "assembling") {
        setProgress("Assembling and rendering final movie (JSON2Video)…");
      } else {
        setProgress("Processing video generation job…");
      }

      await new Promise((resolve) => setTimeout(resolve, 2500));
    }
  }

  async function cancelCurrentJob() {
    if (!currentJob) return;
    try {
      const cancelled = await api<VideoJob>(`/jobs/${currentJob.id}/cancel/`, { method: "POST" });
      setCurrentJob(cancelled);
      setProgress("Job Cancelled");
      setToastType("info");
      setToastMessage("Generation cancelled. Credits refunded.");
      api<{ user: User }>("/auth/me/").then((d) => setUser(d.user)).catch(() => null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to cancel job.");
    } finally {
      setBusy(false);
      setBusySceneId(null);
    }
  }

  async function generateVideo(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim()) {
      setError("Please enter a story or script before generating.");
      return;
    }

    if (duration > maxAllowedDuration) {
      setError(`Your ${planCode.toUpperCase()} plan supports videos up to ${maxAllowedDuration} seconds. Upgrade to unlock longer videos.`);
      return;
    }

    if (user && creditsBalance < duration) {
      setError("Your free generation has been used. Upgrade to create more videos.");
      return;
    }

    setBusy(true);
    setError("");
    setProgress("Submitting generation job…");

    try {
      let activeProject: VideoProject;
      const payload: Record<string, unknown> = {
        title: title.trim() || "Untitled Video",
        input_type: inputType,
        prompt: prompt.trim(),
        aspect_ratio: aspectRatio,
        duration,
      };

      if (isPaidUser && showAdvancedControl && characters.length > 0) {
        payload.characters = characters;
      }

      // If a completed/failed project already exists, branch a clean new version
      if (project && (project.status === "completed" || project.status === "failed" || project.status === "cancelled")) {
        setProgress("Creating new video version…");
        activeProject = await api<VideoProject>(`/projects/${project.id}/versions/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: title.trim() || project.title,
            input_type: inputType,
            prompt: prompt.trim(),
            aspect_ratio: aspectRatio,
            duration,
            ...(isPaidUser && showAdvancedControl ? { characters } : {}),
          }),
        });
      } else {
        setProgress("Understanding story & planning scenes…");
        activeProject = await api<VideoProject>("/projects/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }

      setProject(activeProject);

      // Create and dispatch asynchronous VideoJob
      setProgress("Starting AI video pipeline…");
      const job = await api<VideoJob>("/jobs/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: activeProject.id,
          job_type: "full_generation",
        }),
      });

      setCurrentJob(job);
      await pollJob(job.id, activeProject.id);

      setProgress("Video Ready");
      setToastType("success");
      setToastMessage(
        activeProject.version_number > 1
          ? `Version ${activeProject.version_number} generated successfully!`
          : "Video generation completed successfully!"
      );
      // Refresh user balance
      api<{ user: User }>("/auth/me/").then((d) => setUser(d.user)).catch(() => null);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Video generation encountered an error.";
      setError(msg);
      setProgress("Generation Failed");
    } finally {
      setBusy(false);
    }
  }

  async function regenerateScene(sceneId: number) {
    if (!project || busySceneId) return;
    setBusySceneId(sceneId);
    setError("");
    setProgress(`Regenerating Scene…`);
    try {
      const job = await api<VideoJob>("/jobs/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project_id: project.id,
          job_type: "scene_regeneration",
          scene_id: sceneId,
        }),
      });
      setCurrentJob(job);
      await pollJob(job.id, project.id);
      setProgress("Video Ready");
      setToastType("success");
      setToastMessage("Scene regenerated and movie updated successfully!");
      api<{ user: User }>("/auth/me/").then((d) => setUser(d.user)).catch(() => null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scene regeneration failed.");
      setProgress("Failed");
    } finally {
      setBusySceneId(null);
    }
  }

  function selectVersion(next: VideoProject) {
    setProject(next);
    setInputType(next.input_type);
    setPrompt(next.prompt);
    setTitle(next.title);
    setDuration(next.duration);
    setAspectRatio(next.aspect_ratio);
    if (next.characters?.length) {
      setCharacters(
        next.characters.map((c) => ({
          name: c.name,
          role: c.role,
          age_description: c.age_description,
          appearance: c.appearance,
          clothing: c.clothing,
          personality: c.personality,
          description: c.description,
          visual_prompt: c.visual_prompt,
        }))
      );
    }
    setError("");
  }

  function handleEditStory() {
    if (promptInputRef.current) {
      promptInputRef.current.focus();
      promptInputRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }


  // Polling for assembly status if processing
  useEffect(() => {
    if (!project?.id || project.status !== "processing" || !project.provider_project_id) return;
    const timer = setInterval(async () => {
      try {
        const data = await api<VideoProject>(`/projects/${project.id}/status/`);
        setProject(data);
        if (data.status === "completed") {
          setProgress("Video Ready");
          setToastType("success");
          setToastMessage("Your video render is ready to watch!");
        }
        if (data.status === "failed") {
          setProgress("Render Failed");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to check rendering status.");
      }
    }, 5000);
    return () => clearInterval(timer);
  }, [project?.id, project?.status, project?.provider_project_id]);

  async function logout() {
    try {
      await api("/auth/logout/", { method: "POST" });
    } finally {
      router.replace("/login");
    }
  }

  if (authLoading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-[#08090d] text-sm text-white/50">
        Loading AI Video Studio…
      </main>
    );
  }

  // ==========================================
  // 1. PUBLIC LANDING PAGE (Unauthenticated)
  // ==========================================
  if (!user) {
    return (
      <main className="min-h-screen bg-[#08090d] text-white">
        {/* Navigation Bar */}
        <header className="sticky top-0 z-40 border-b border-white/10 bg-[#08090d]/80 backdrop-blur-xl">
          <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between px-6 py-3">
            <Link href="/" className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-600 text-sm font-bold text-white shadow-lg shadow-violet-500/25">
                AI
              </span>
              <span className="text-base font-bold tracking-tight text-white">AI Video Studio</span>
            </Link>

            <div className="flex items-center gap-3">
              <Link
                href="/login"
                className="rounded-xl px-4 py-2 text-xs font-medium text-white/70 transition hover:text-white"
              >
                Sign in
              </Link>
              <Link
                href="/signup"
                className="rounded-xl bg-white px-4 py-2.5 text-xs font-semibold text-black transition hover:bg-white/90 shadow-lg shadow-white/5"
              >
                Get 10 Free Credits →
              </Link>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <section className="relative overflow-hidden px-6 pt-20 pb-24 text-center">
          <div className="mx-auto max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-violet-300">
              <span className="h-2 w-2 rounded-full bg-violet-400 animate-pulse" />
              100% Automated Character Continuity
            </div>

            <h1 className="mt-6 text-4xl font-extrabold tracking-tight sm:text-6xl sm:leading-[1.1]">
              Transform Stories into Multi-Scene{" "}
              <span className="bg-gradient-to-r from-violet-400 via-purple-300 to-indigo-400 bg-clip-text text-transparent">
                Consistent Character
              </span>{" "}
              AI Videos.
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-white/55 sm:text-lg">
              Type your story, choose duration, and let our engine automatically extract characters, plan scenes, generate clips, and assemble the final MP4.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/signup"
                className="w-full sm:w-auto rounded-2xl bg-white px-8 py-4 text-sm font-semibold text-black transition hover:bg-white/90 shadow-xl shadow-white/10"
              >
                Claim 10 Free Credits & Start
              </Link>
              <Link
                href="/login"
                className="w-full sm:w-auto rounded-2xl border border-white/15 bg-white/[0.03] px-8 py-4 text-sm font-semibold text-white transition hover:bg-white/10"
              >
                Sign In to Studio
              </Link>
            </div>
          </div>
        </section>

        {/* 4-Step Simplified Journey */}
        <section className="border-t border-white/10 bg-white/[0.015] px-6 py-20">
          <div className="mx-auto max-w-7xl">
            <div className="text-center mb-16">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Streamlined Creation</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">4 Steps to Your AI Video</h2>
            </div>

            <div className="grid gap-6 md:grid-cols-4">
              <div className="rounded-2xl border border-white/10 bg-black/40 p-6 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-sm font-bold text-violet-400 mb-4 border border-violet-500/20">
                  1
                </div>
                <h3 className="text-base font-bold text-white">Story / Prompt</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Type your storyline. The engine automatically detects characters and scene plot points.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/40 p-6 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-sm font-bold text-violet-400 mb-4 border border-violet-500/20">
                  2
                </div>
                <h3 className="text-base font-bold text-white">Duration</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Pick 10s (Free), 30s (Creator), or 60s (Pro). 1 second equals exactly 1 credit.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/40 p-6 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-sm font-bold text-violet-400 mb-4 border border-violet-500/20">
                  3
                </div>
                <h3 className="text-base font-bold text-white">Aspect Ratio</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Select 9:16 vertical Shorts, 16:9 widescreen landscape, or 1:1 square.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/40 p-6 text-center">
                <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/10 text-sm font-bold text-violet-400 mb-4 border border-violet-500/20">
                  4
                </div>
                <h3 className="text-base font-bold text-white">Generate & Watch</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  The AI locks character consistency across scenes and renders the final MP4.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="border-t border-white/10 bg-[#06070a] px-6 py-8 text-center text-xs text-white/30">
          <p>© {new Date().getFullYear()} AI Video Studio. Production AI Video Platform.</p>
        </footer>
      </main>
    );
  }

  // ==========================================
  // 2. AUTHENTICATED STUDIO WORKSPACE
  // ==========================================
  return (
    <main className="min-h-screen bg-[#08090d] text-white">
      {/* Toast Notification */}
      <Toast message={toastMessage} type={toastType} onClose={() => setToastMessage("")} />

      {/* Version History Slide-out Drawer */}
      {project && (
        <VersionHistoryDrawer
          project={project}
          isOpen={versionsDrawerOpen}
          onClose={() => setVersionsDrawerOpen(false)}
          onSelectVersion={selectVersion}
        />
      )}

      {/* Studio Header */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#0b0c11]/90 backdrop-blur-xl">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-6 py-3">
          <div className="flex items-center gap-3">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-violet-600 text-xs font-bold text-white shadow-lg shadow-violet-500/20">
              AI
            </span>
            <div>
              <h1 className="text-sm font-semibold tracking-tight">AI Video Studio</h1>
              <p className="text-[11px] text-white/40">Story to Video Creator</p>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {user.is_staff && (
              <button
                onClick={() => router.push("/admin")}
                className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-1.5 text-xs font-medium text-amber-400 transition hover:bg-amber-500/20"
              >
                Admin
              </button>
            )}
            <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/70">
              Credits: <span className="font-semibold text-violet-300">{creditsBalance}</span>
            </div>
            <button
              onClick={() => router.push("/dashboard")}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/70 transition hover:text-white"
            >
              Dashboard
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

      {/* Main Studio Grid */}
      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[1fr_460px]">
        {/* Left Column: Simple Story Creator */}
        <section aria-labelledby="studio-form-heading">
          {/* Header Title */}
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Creation Studio</p>
                <h2 id="studio-form-heading" className="text-3xl font-bold tracking-tight">
                  {project && project.version_number > 0
                    ? `Editing Story (V${project.version_number})`
                    : "Create a Video"}
                </h2>
              </div>

              {project && (
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setVersionsDrawerOpen(true)}
                    className="rounded-xl border border-violet-500/30 bg-violet-500/10 px-3 py-1.5 text-xs font-medium text-violet-300 hover:bg-violet-500/20 transition"
                  >
                    Version History · V{project.version_number}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      setProject(null);
                      setTitle("");
                      setPrompt("");
                      setError("");
                    }}
                    className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs font-medium text-white/60 hover:text-white"
                  >
                    + Blank Project
                  </button>
                </div>
              )}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-white/45">
              Enter your story, choose duration & aspect ratio, and click generate. Character understanding and scene planning are handled automatically.
            </p>
          </div>

          {/* Form */}
          <form onSubmit={generateVideo} className="space-y-6">
            {/* Story / Script Mode Switcher */}
            <div className="flex rounded-xl border border-white/10 bg-white/[0.03] p-1">
              <button
                type="button"
                disabled={busy}
                onClick={() => setInputType("story")}
                className={`flex-1 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                  inputType === "story" ? "bg-white text-black shadow" : "text-white/50 hover:text-white"
                }`}
              >
                Story Prompt
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setInputType("script")}
                className={`flex-1 rounded-lg px-4 py-2 text-xs font-semibold transition ${
                  inputType === "script" ? "bg-white text-black shadow" : "text-white/50 hover:text-white"
                }`}
              >
                Complete Script
              </button>
            </div>

            {/* Story Input */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label htmlFor="project-prompt-input" className="text-xs font-medium uppercase tracking-wider text-white/60">
                  {inputType === "story" ? "Your Story" : "Your Script"}
                </label>
                <span className="text-[11px] text-white/30">{prompt.length} characters</span>
              </div>
              <textarea
                ref={promptInputRef}
                id="project-prompt-input"
                required
                value={prompt}
                disabled={busy}
                onChange={(e) => setPrompt(e.target.value)}
                rows={6}
                placeholder={
                  inputType === "story"
                    ? "A young explorer walks through a futuristic city at sunset and discovers a glowing doorway…"
                    : "SCENE 1: Sunset futuristic city. A young explorer walks forward.\nSCENE 2: The explorer pauses before a glowing doorway."
                }
                className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs leading-relaxed text-white placeholder-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            {/* Duration Selector: [ 10 sec ] [ 30 sec ] [ 60 sec ] */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-xs font-medium uppercase tracking-wider text-white/60">
                  Duration (1 second = 1 credit)
                </label>
                <span className="text-[11px] text-violet-400 font-semibold">
                  Cost: {duration} Credits
                </span>
              </div>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { sec: 10, label: "10 sec", sub: "Quick Clip · 2 Scenes", minPlan: "free" },
                  { sec: 30, label: "30 sec", sub: "Standard · 5 Scenes", minPlan: "creator" },
                  { sec: 60, label: "60 sec", sub: "Narrative · 10 Scenes", minPlan: "pro" },
                ].map((item) => {
                  const isLocked = item.sec > maxAllowedDuration;
                  const isSelected = duration === item.sec;

                  return (
                    <button
                      key={item.sec}
                      type="button"
                      disabled={busy}
                      onClick={() => {
                        if (isLocked) {
                          setError(`The ${item.sec}s duration requires the ${item.minPlan.toUpperCase()} plan. Upgrade to unlock longer videos.`);
                        } else {
                          setDuration(item.sec);
                          setError("");
                        }
                      }}
                      className={`relative flex flex-col items-center justify-center rounded-2xl border p-3.5 text-center transition ${
                        isSelected
                          ? "border-violet-500 bg-violet-500/15 text-white shadow-lg shadow-violet-500/10"
                          : isLocked
                          ? "border-white/5 bg-white/[0.01] text-white/40 hover:border-white/10"
                          : "border-white/10 bg-white/[0.02] text-white/60 hover:border-white/20 hover:text-white"
                      } disabled:opacity-50`}
                    >
                      {isLocked && (
                        <span className="absolute top-2 right-2 rounded bg-white/5 px-1.5 py-0.5 text-[9px] font-semibold uppercase text-amber-300 border border-amber-500/20">
                          🔒 {item.minPlan}
                        </span>
                      )}
                      <span className="text-sm font-bold">{item.label}</span>
                      <span className="text-[10px] text-white/40 mt-0.5">{item.sub}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Aspect Ratio Selector: 9:16, 16:9, 1:1 */}
            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-white/60">
                Aspect Ratio
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { ratio: "9:16", label: "9:16", sub: "Vertical (Shorts / Reels)" },
                  { ratio: "16:9", label: "16:9", sub: "Landscape (YouTube)" },
                  { ratio: "1:1", label: "1:1", sub: "Square (Social Feed)" },
                ].map((item) => (
                  <button
                    key={item.ratio}
                    type="button"
                    disabled={busy}
                    onClick={() => setAspectRatio(item.ratio)}
                    className={`flex flex-col items-center justify-center rounded-2xl border p-3 text-center transition ${
                      aspectRatio === item.ratio
                        ? "border-violet-500 bg-violet-500/15 text-white shadow-lg shadow-violet-500/10"
                        : "border-white/10 bg-white/[0.02] text-white/60 hover:border-white/20 hover:text-white"
                    } disabled:opacity-50`}
                  >
                    <span className="text-sm font-bold">{item.label}</span>
                    <span className="text-[10px] text-white/40 mt-0.5">{item.sub}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Advanced Character Control — Locked for Free / Unlocked for Creator & Pro */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowAdvancedControl(!showAdvancedControl)}
                  className="flex items-center gap-2 text-xs font-semibold text-white/80 hover:text-white"
                >
                  <span>{showAdvancedControl ? "▼" : "▶"}</span>
                  <span>Advanced Character Control</span>
                  {!isPaidUser && (
                    <span className="rounded-md bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-300 border border-amber-500/20">
                      🔒 Creator & Pro only
                    </span>
                  )}
                </button>

                {isPaidUser && showAdvancedControl && (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => setCharacters([...characters, emptyCharacter()])}
                    className="text-xs font-medium text-violet-400 hover:text-violet-300"
                  >
                    + Add Character
                  </button>
                )}
              </div>

              {showAdvancedControl && (
                <div className="mt-4 pt-4 border-t border-white/5">
                  {!isPaidUser ? (
                    <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs text-amber-200/80 space-y-3">
                      <p className="leading-relaxed">
                        Automatic story character extraction is enabled for Free accounts. Upgrade to Creator or Pro to manually customize character clothing, facial appearance, personality, and multiple character consistency sheets.
                      </p>
                      <Link
                        href="/dashboard"
                        className="inline-flex items-center gap-1.5 rounded-lg bg-amber-400 px-3.5 py-1.5 text-xs font-bold text-black transition hover:bg-amber-300"
                      >
                        Upgrade Plan →
                      </Link>
                    </div>
                  ) : (
                    <CharacterEditor characters={characters} setCharacters={setCharacters} disabled={busy} />
                  )}
                </div>
              )}
            </div>

            {/* Error Display */}
            {error && (
              <div role="alert" className="flex items-start gap-3 rounded-2xl border border-red-500/20 bg-red-500/10 p-4 text-xs text-red-300">
                <svg className="h-5 w-5 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span>{error}</span>
              </div>
            )}

            {/* Generate CTA Button */}
            <button
              type="submit"
              disabled={busy}
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-white px-6 py-4 text-sm font-bold text-black transition hover:bg-white/90 shadow-xl shadow-white/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy ? (
                <>
                  <svg className="h-4 w-4 animate-spin text-black" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span>{progress}</span>
                </>
              ) : project && (project.status === "completed" || project.status === "failed") ? (
                <>
                  <span>✨</span>
                  <span>Generate New Version (V{project.version_number + 1} · {duration} Credits)</span>
                </>
              ) : (
                <>
                  <span>✨</span>
                  <span>Generate Video ({duration} Credits)</span>
                </>
              )}
            </button>
          </form>
        </section>

        {/* Right Column: Live Pipeline Monitor & Final Render */}
        <aside aria-label="Pipeline monitor">
          <div className="sticky top-24 rounded-3xl border border-white/10 bg-[#0d0e14]/90 p-5 shadow-2xl backdrop-blur-xl space-y-4">
            <div className="flex items-center justify-between border-b border-white/5 pb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Pipeline Monitor</h3>
                <p className="mt-0.5 text-[11px] text-white/40">Status: {progress}</p>
              </div>

              {project && (
                <button
                  type="button"
                  onClick={() => setVersionsDrawerOpen(true)}
                  className="rounded-full bg-violet-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-violet-300 border border-violet-500/20 hover:bg-violet-500/20 transition"
                >
                  Version History · V{project.version_number}
                </button>
              )}
            </div>

            <ProgressPanel
              project={project}
              job={currentJob}
              progress={progress}
              onRegenerate={regenerateScene}
              busySceneId={busySceneId}
              isGenerating={busy}
              onCancel={cancelCurrentJob}
              onRetry={() => {
                if (project) {
                  setBusy(true);
                  setError("");
                  api<VideoJob>("/jobs/", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      project_id: project.id,
                      job_type: "full_generation",
                    }),
                  })
                    .then((job) => {
                      setCurrentJob(job);
                      return pollJob(job.id, project.id);
                    })
                    .catch((err) => {
                      setError(err instanceof Error ? err.message : "Retry failed.");
                    })
                    .finally(() => setBusy(false));
                }
              }}
            />


            <FinalVideo
              project={project}
              onEditStory={handleEditStory}
              onOpenVersions={() => setVersionsDrawerOpen(true)}
            />
          </div>
        </aside>
      </div>
    </main>
  );
}
