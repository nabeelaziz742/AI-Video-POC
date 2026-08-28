"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, InputType, User, VideoProject, VideoScene } from "./api";
import { CharacterDraft, emptyCharacter } from "./character-types";
import { CharacterEditor } from "./components/CharacterEditor";
import { FinalVideo } from "./components/FinalVideo";
import { ProgressPanel } from "./components/ProgressPanel";
import { VersionHistory } from "./components/VersionHistory";
import { Toast } from "./components/Toast";

const initialCharacter: CharacterDraft = {
  name: "Farmer",
  role: "main character",
  age_description: "adult man in his 40s",
  appearance: "friendly face, medium build, black hair and neat moustache",
  clothing: "traditional brown shalwar kameez with green embroidered vest and sandals",
  personality: "kind, hardworking, and cheerful",
  description: "A warm-hearted village farmer who cares deeply for his animals and crops",
  visual_prompt: "polished 3D animated character, Pixar and DreamWorks inspired, soft cinematic lighting",
};

export default function Home() {
  const router = useRouter();
  const [authLoading, setAuthLoading] = useState(true);
  const [user, setUser] = useState<User | null>(null);

  // Form State
  const [inputType, setInputType] = useState<InputType>("story");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [characters, setCharacters] = useState<CharacterDraft[]>([initialCharacter]);
  const [showCharacters, setShowCharacters] = useState(false);

  // Project & Pipeline State
  const [project, setProject] = useState<VideoProject | null>(null);
  const [busy, setBusy] = useState(false);
  const [busySceneId, setBusySceneId] = useState<number | null>(null);
  const [progress, setProgress] = useState("Ready");
  const [error, setError] = useState("");
  const [toastMessage, setToastMessage] = useState("");
  const [toastType, setToastType] = useState<"success" | "error" | "info">("info");

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

  async function waitForScene(projectId: number, sceneId: number) {
    for (;;) {
      const scene = await api<VideoScene>(`/projects/${projectId}/scenes/${sceneId}/status/`);
      setProject((current) =>
        current ? { ...current, scenes: current.scenes.map((item) => (item.id === scene.id ? scene : item)) } : current
      );
      if (scene.status === "completed") return scene;
      if (scene.status === "failed") {
        throw new Error(scene.error_message || `Scene ${scene.scene_number} generation failed.`);
      }
      await new Promise((resolve) => setTimeout(resolve, 4000));
    }
  }

  async function runGeneration(created: VideoProject) {
    let current = created;
    setProgress("Creating character reference sheets…");
    for (const character of current.characters) {
      if (!character.reference_image_url) {
        await api(`/projects/${current.id}/characters/${character.id}/reference/`, { method: "POST" });
      }
      current = await api<VideoProject>(`/projects/${current.id}/status/`);
      setProject(current);
    }

    for (let index = 0; index < current.scenes.length; index += 1) {
      const scene = current.scenes[index];
      setProgress(`Generating Scene ${index + 1} of ${current.scenes.length}…`);
      await api(`/projects/${current.id}/scenes/${scene.id}/generate/`, { method: "POST" });
      await waitForScene(current.id, scene.id);
      current = await api<VideoProject>(`/projects/${current.id}/status/`);
      setProject(current);
    }

    setProgress("Stitching and assembling final video…");
    current = await api<VideoProject>(`/projects/${current.id}/assemble/`, { method: "POST" });
    setProject(current);
    setProgress("Rendering final video…");
  }

  async function generateVideo(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim()) {
      setError("Please enter a story or script before generating.");
      return;
    }
    if (!characters.length || characters.some((c) => !c.name.trim())) {
      setError("Please ensure every character has a valid name.");
      return;
    }

    setBusy(true);
    setError("");

    try {
      let activeProject: VideoProject;

      // If a completed/failed project already exists, branch a clean new version
      if (project && (project.status === "completed" || project.status === "failed")) {
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
          }),
        });
      } else {
        setProgress("Initializing project…");
        activeProject = await api<VideoProject>("/projects/", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: title.trim() || "Untitled Video",
            input_type: inputType,
            prompt: prompt.trim(),
            aspect_ratio: aspectRatio,
            duration,
            characters,
          }),
        });
      }

      setProject(activeProject);
      await runGeneration(activeProject);
      setToastType("success");
      setToastMessage(
        activeProject.version_number > 1
          ? `Version ${activeProject.version_number} generated successfully!`
          : "Video generation completed successfully!"
      );
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
    try {
      await api<VideoScene>(`/projects/${project.id}/scenes/${sceneId}/regenerate/`, { method: "POST" });
      await waitForScene(project.id, sceneId);
      const assembled = await api<VideoProject>(`/projects/${project.id}/assemble/`, { method: "POST" });
      setProject(assembled);
      setProgress("Rendering final video…");
      setToastType("success");
      setToastMessage(`Scene regenerated successfully!`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Scene regeneration failed.");
      setProgress("Failed");
    } finally {
      setBusySceneId(null);
    }
  }

  async function selectVersion(next: VideoProject) {
    setProject(next);
    setInputType(next.input_type);
    setPrompt(next.prompt);
    setTitle(next.title);
    setDuration(next.duration);
    setAspectRatio(next.aspect_ratio);
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
    setError("");

    if (next.status === "queued" || next.status === "draft") {
      setBusy(true);
      try {
        await runGeneration(next);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Version generation failed.");
        setProgress("Failed");
      } finally {
        setBusy(false);
      }
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
                Get started free →
              </Link>
            </div>
          </div>
        </header>

        {/* Hero Section */}
        <section className="relative overflow-hidden px-6 pt-20 pb-24 text-center">
          <div className="mx-auto max-w-4xl">
            <div className="inline-flex items-center gap-2 rounded-full border border-violet-500/30 bg-violet-500/10 px-4 py-1.5 text-xs font-semibold uppercase tracking-wider text-violet-300">
              <span className="h-2 w-2 rounded-full bg-violet-400 animate-pulse" />
              Character Continuity Engine
            </div>

            <h1 className="mt-6 text-4xl font-extrabold tracking-tight sm:text-6xl sm:leading-[1.1]">
              Transform Stories into Multi-Scene <span className="bg-gradient-to-r from-violet-400 via-purple-300 to-indigo-400 bg-clip-text text-transparent">Character Consistent</span> AI Videos.
            </h1>

            <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-white/55 sm:text-lg">
              Write your story, select your duration (10s, 30s, 60s), and generate full multi-scene animated videos with locked character continuity.
            </p>

            <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
              <Link
                href="/signup"
                className="w-full sm:w-auto rounded-2xl bg-white px-8 py-4 text-sm font-semibold text-black transition hover:bg-white/90 shadow-xl shadow-white/10"
              >
                Start Generating Videos Free
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

        {/* 3-Step Simple User Journey */}
        <section className="border-t border-white/10 bg-white/[0.015] px-6 py-20">
          <div className="mx-auto max-w-7xl">
            <div className="text-center mb-16">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Streamlined Workflow</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Simple, Powerful Creation</h2>
              <p className="mt-3 text-sm text-white/45 max-w-xl mx-auto">
                No complicated node graphs or manual rendering setups. Just write, choose duration, and generate.
              </p>
            </div>

            <div className="grid gap-6 md:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-black/40 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/10 text-lg font-bold text-violet-400 mb-5 border border-violet-500/20">
                  1
                </div>
                <h3 className="text-lg font-bold text-white">Write Your Story</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Type or paste your storyline or script. The AI automatically parses plot points into structured scenes.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/40 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/10 text-lg font-bold text-violet-400 mb-5 border border-violet-500/20">
                  2
                </div>
                <h3 className="text-lg font-bold text-white">Pick Duration & Ratio</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Select 10s, 30s, or 60s and choose 9:16 vertical for Shorts/Reels or 16:9 landscape for standard video.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-black/40 p-8 text-center">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-violet-500/10 text-lg font-bold text-violet-400 mb-5 border border-violet-500/20">
                  3
                </div>
                <h3 className="text-lg font-bold text-white">Generate & Watch</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  The engine locks character consistency, renders each scene, and stitches the final cohesive MP4.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Supported Formats */}
        <section className="px-6 py-20 border-t border-white/10">
          <div className="mx-auto max-w-7xl">
            <div className="text-center mb-16">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Formats & Durations</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Multi-Format AI Video</h2>
            </div>

            <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
                <div className="text-2xl mb-3">📱</div>
                <h3 className="text-base font-semibold text-white">9:16 Vertical Shorts</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Full HD vertical orientation designed specifically for TikTok, Instagram Reels, and YouTube Shorts.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
                <div className="text-2xl mb-3">🖥️</div>
                <h3 className="text-base font-semibold text-white">16:9 Landscape Widescreen</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Cinematic widescreen suitable for standard YouTube videos, storytelling presentations, and courses.
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-6">
                <div className="text-2xl mb-3">🎨</div>
                <h3 className="text-base font-semibold text-white">Locked Character Styles</h3>
                <p className="mt-2 text-xs leading-relaxed text-white/45">
                  Persistent character reference sheets keep characters recognizable from opening scene to credits.
                </p>
              </div>
            </div>
          </div>
        </section>

        {/* Bottom CTA */}
        <section className="border-t border-white/10 bg-gradient-to-b from-transparent to-violet-950/20 px-6 py-20 text-center">
          <div className="mx-auto max-w-3xl">
            <h2 className="text-3xl font-bold tracking-tight sm:text-4xl">
              Ready to generate your first AI video?
            </h2>
            <p className="mt-3 text-sm text-white/50">
              Create an account now and start turning stories into consistent video projects.
            </p>
            <div className="mt-8 flex justify-center gap-4">
              <Link
                href="/signup"
                className="rounded-2xl bg-white px-8 py-4 text-sm font-semibold text-black transition hover:bg-white/90 shadow-xl shadow-white/10"
              >
                Create Free Account
              </Link>
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
            <button
              onClick={() => router.push("/dashboard")}
              className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-white/70 transition hover:text-white"
            >
              Dashboard
            </button>
            <span className="hidden text-xs text-white/40 sm:block">{user.username}</span>
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
      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[1fr_440px]">
        {/* Left Column: Simple Story Creator */}
        <section aria-labelledby="studio-form-heading">
          {/* Header Title */}
          <div className="mb-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">Creation Studio</p>
                <h2 id="studio-form-heading" className="text-3xl font-bold tracking-tight">
                  {project && project.version_number > 0
                    ? `Editing Version ${project.version_number}`
                    : "Create a Video"}
                </h2>
              </div>

              {project && (
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
              )}
            </div>
            <p className="mt-1 text-xs leading-relaxed text-white/45">
              Type your story, choose duration, and generate. Editing an existing project creates a new version while preserving previous videos.
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
                id="project-prompt-input"
                required
                value={prompt}
                disabled={busy}
                onChange={(e) => setPrompt(e.target.value)}
                rows={6}
                placeholder={
                  inputType === "story"
                    ? "A friendly village farmer walks along a mountain trail with his faithful buffalo during sunrise. They encounter a lost traveler, guide him back to the village, and celebrate with warm tea as evening falls…"
                    : "SCENE 1: Morning mountain trail. Farmer walks alongside his buffalo.\nSCENE 2: The farmer helps a lost traveler.\nSCENE 3: Village gathering at sunset with hot tea."
                }
                className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.03] p-4 text-xs leading-relaxed text-white placeholder-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            {/* Duration Selector: [ 10 sec ] [ 30 sec ] [ 60 sec ] */}
            <div>
              <label className="mb-2 block text-xs font-medium uppercase tracking-wider text-white/60">
                Duration
              </label>
              <div className="grid grid-cols-3 gap-3">
                {[
                  { sec: 10, label: "10 sec", sub: "Quick Clip · 1 Scene" },
                  { sec: 30, label: "30 sec", sub: "Standard · 3 Scenes" },
                  { sec: 60, label: "60 sec", sub: "Narrative · 6 Scenes" },
                ].map((item) => (
                  <button
                    key={item.sec}
                    type="button"
                    disabled={busy}
                    onClick={() => setDuration(item.sec)}
                    className={`flex flex-col items-center justify-center rounded-2xl border p-3 text-center transition ${
                      duration === item.sec
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

            {/* Optional Character Cast & Customization (Collapsible) */}
            <div className="rounded-2xl border border-white/10 bg-white/[0.015] p-4">
              <div className="flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowCharacters(!showCharacters)}
                  className="flex items-center gap-2 text-xs font-semibold text-white/80 hover:text-white"
                >
                  <span>{showCharacters ? "▼" : "▶"}</span>
                  <span>Character Cast & Style Details</span>
                  <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-white/40">
                    {characters.length} character{characters.length > 1 ? "s" : ""}
                  </span>
                </button>

                {showCharacters && (
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

              {showCharacters && (
                <div className="mt-4 pt-4 border-t border-white/5">
                  <CharacterEditor characters={characters} setCharacters={setCharacters} disabled={busy} />
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
                  <span>Generate New Version (V{project.version_number + 1})</span>
                </>
              ) : (
                <>
                  <span>✨</span>
                  <span>Generate Video</span>
                </>
              )}
            </button>
          </form>

          {/* Version History Component */}
          {project && <VersionHistory project={project} onSelect={selectVersion} disabled={busy} />}
        </section>

        {/* Right Column: Live Pipeline Monitor & Final Render */}
        <aside aria-label="Pipeline monitor">
          <div className="sticky top-24 rounded-3xl border border-white/10 bg-[#0d0e14]/90 p-5 shadow-2xl backdrop-blur-xl">
            <div className="mb-5 flex items-center justify-between border-b border-white/5 pb-4">
              <div>
                <h3 className="text-sm font-semibold text-white">Pipeline Monitor</h3>
                <p className="mt-0.5 text-[11px] text-white/40">Status: {progress}</p>
              </div>

              {project && (
                <span className="rounded-full bg-violet-500/10 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wider text-violet-300 border border-violet-500/20">
                  V{project.version_number} · {project.status}
                </span>
              )}
            </div>

            <ProgressPanel
              project={project}
              progress={progress}
              onRegenerate={regenerateScene}
              busySceneId={busySceneId}
              isGenerating={busy}
            />

            <FinalVideo project={project} />
          </div>
        </aside>
      </div>
    </main>
  );
}
