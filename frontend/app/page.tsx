"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, VideoProject, VideoScene } from "./api";
import { CharacterDraft, emptyCharacter } from "./character-types";
import { CharacterEditor } from "./components/CharacterEditor";
import { FinalVideo } from "./components/FinalVideo";
import { ProgressPanel } from "./components/ProgressPanel";

const initialCharacter: CharacterDraft = { name: "Farmer", role: "main character", age_description: "adult man", appearance: "friendly face, medium build, black hair and moustache", clothing: "simple brown shalwar kameez with green vest and sandals", personality: "kind, hardworking and cheerful", description: "a warm-hearted village farmer", visual_prompt: "polished family-friendly 3D cartoon character, rural Pakistani village aesthetic" };

export default function Home() {
  const [inputType, setInputType] = useState<"story" | "script">("story");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [characters, setCharacters] = useState<CharacterDraft[]>([initialCharacter]);
  const [project, setProject] = useState<VideoProject | null>(null);
  const [busy, setBusy] = useState(false);
  const [busySceneId, setBusySceneId] = useState<number | null>(null);
  const [progress, setProgress] = useState("Ready");
  const [error, setError] = useState("");

  async function waitForScene(projectId: number, sceneId: number) {
    for (;;) {
      const scene = await api<VideoScene>(`/projects/${projectId}/scenes/${sceneId}/status/`);
      setProject((current) => current ? { ...current, scenes: current.scenes.map((item) => item.id === scene.id ? scene : item) } : current);
      if (scene.status === "completed") return scene;
      if (scene.status === "failed") throw new Error(scene.error_message || `Scene ${scene.scene_number} failed.`);
      await new Promise((resolve) => setTimeout(resolve, 4000));
    }
  }

  async function runGeneration(created: VideoProject) {
    let current = created;
    setProgress("Creating character references...");
    for (const character of current.characters) {
      if (!character.reference_image_url) await api(`/projects/${current.id}/characters/${character.id}/reference/`, { method: "POST" });
      current = await api<VideoProject>(`/projects/${current.id}/status/`);
      setProject(current);
    }
    for (let index = 0; index < current.scenes.length; index += 1) {
      const scene = current.scenes[index];
      setProgress(`Generating scene ${index + 1} of ${current.scenes.length}...`);
      await api(`/projects/${current.id}/scenes/${scene.id}/generate/`, { method: "POST" });
      await waitForScene(current.id, scene.id);
      current = await api<VideoProject>(`/projects/${current.id}/status/`);
      setProject(current);
    }
    setProgress("Assembling final video...");
    current = await api<VideoProject>(`/projects/${current.id}/assemble/`, { method: "POST" });
    setProject(current);
    setProgress("Rendering final video...");
  }

  async function generateVideo(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim()) return setError("Please enter a story or script.");
    if (!characters.length || characters.some((character) => !character.name.trim())) return setError("Add at least one character with a name.");
    setBusy(true); setError(""); setProject(null); setProgress("Creating project...");
    try {
      const created = await api<VideoProject>("/projects/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim() || "Untitled Video", input_type: inputType, prompt: prompt.trim(), aspect_ratio: aspectRatio, duration, characters }) });
      setProject(created);
      await runGeneration(created);
    } catch (err) { setError(err instanceof Error ? err.message : "Generation failed."); setProgress("Failed"); }
    finally { setBusy(false); }
  }

  async function regenerateScene(sceneId: number) {
    if (!project || busySceneId) return;
    setBusySceneId(sceneId); setError("");
    try {
      const scene = await api<VideoScene>(`/projects/${project.id}/scenes/${sceneId}/regenerate/`, { method: "POST" });
      setProject((current) => current ? { ...current, scenes: current.scenes.map((item) => item.id === scene.id ? scene : item) } : current);
      await waitForScene(project.id, sceneId);
      const assembled = await api<VideoProject>(`/projects/${project.id}/assemble/`, { method: "POST" });
      setProject(assembled); setProgress("Rendering final video...");
    } catch (err) { setError(err instanceof Error ? err.message : "Scene regeneration failed."); setProgress("Failed"); }
    finally { setBusySceneId(null); }
  }

  useEffect(() => {
    if (!project?.id || project.status !== "processing" || !project.provider_project_id) return;
    const timer = setInterval(async () => {
      try {
        const data = await api<VideoProject>(`/projects/${project.id}/status/`);
        setProject(data);
        if (data.status === "completed") setProgress("Video ready");
        if (data.status === "failed") setProgress("Failed");
      } catch (err) { setError(err instanceof Error ? err.message : "Unable to check video status."); }
    }, 5000);
    return () => clearInterval(timer);
  }, [project?.id, project?.status, project?.provider_project_id]);

  return <main className="min-h-screen bg-[#08090d] text-white">
    <header className="border-b border-white/10 bg-[#0b0c11]/90"><div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6"><div><h1 className="text-lg font-semibold tracking-tight">AI Video Studio</h1><p className="text-xs text-white/40">Story to Character Video</p></div><span className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/50">MVP</span></div></header>
    <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[1fr_420px]">
      <section><div className="mb-8"><p className="mb-3 text-sm font-medium text-violet-400">CREATE VIDEO</p><h2 className="text-4xl font-semibold tracking-tight">Turn your story into a character video.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-white/45">Define recurring characters, choose 10, 30 or 60 seconds, and generate a scene-based animated video.</p></div>
        <form onSubmit={generateVideo}>
          <div className="mb-5 flex rounded-xl border border-white/10 bg-white/[0.03] p-1"><button type="button" onClick={() => setInputType("story")} className={`flex-1 rounded-lg px-4 py-3 text-sm ${inputType === "story" ? "bg-white text-black" : "text-white/50"}`}>Story Prompt</button><button type="button" onClick={() => setInputType("script")} className={`flex-1 rounded-lg px-4 py-3 text-sm ${inputType === "script" ? "bg-white text-black" : "text-white/50"}`}>Complete Script</button></div>
          <label className="mb-2 block text-sm text-white/60">Project Title</label><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. The Farmer and His Buffalo" className="mb-5 w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm outline-none focus:border-violet-500/60" />
          <div className="mb-5"><div className="mb-2 flex justify-between"><label className="text-sm text-white/60">{inputType === "story" ? "Describe your story" : "Paste your script"}</label><span className="text-xs text-white/25">{prompt.length} characters</span></div><textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={8} placeholder="A kind farmer walks through a beautiful rural village with his buffalo during the early morning..." className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-6 outline-none placeholder:text-white/20 focus:border-violet-500/60" /></div>
          <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5"><div className="mb-4 flex items-center justify-between"><div><h3 className="text-sm font-semibold">Recurring Characters</h3><p className="mt-1 text-xs text-white/30">Reference images are reused for character continuity.</p></div><button type="button" onClick={() => setCharacters([...characters, emptyCharacter()])} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/60 hover:text-white">+ Add Character</button></div><CharacterEditor characters={characters} setCharacters={setCharacters} /></div>
          <div className="mb-6 grid gap-4 sm:grid-cols-2"><div><label className="mb-2 block text-sm text-white/60">Duration</label><select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="w-full rounded-xl border border-white/10 bg-[#101117] px-4 py-3 text-sm outline-none"><option value={10}>10 seconds — Test</option><option value={30}>30 seconds</option><option value={60}>60 seconds</option></select></div><div><label className="mb-2 block text-sm text-white/60">Aspect Ratio</label><select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} className="w-full rounded-xl border border-white/10 bg-[#101117] px-4 py-3 text-sm outline-none"><option value="9:16">9:16 — Vertical</option><option value="16:9">16:9 — Landscape</option><option value="1:1">1:1 — Square</option></select></div></div>
          {error && <div className="mb-5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">{error}</div>}<button type="submit" disabled={busy} className="w-full rounded-xl bg-white px-5 py-4 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50">{busy ? progress : "✨ Generate Video"}</button>
        </form>
      </section>
      <aside><div className="sticky top-8 rounded-2xl border border-white/10 bg-white/[0.025] p-5"><div className="mb-5 flex items-center justify-between"><div><h3 className="text-sm font-semibold">Generation</h3><p className="mt-1 text-xs text-white/30">{progress}</p></div>{project && <span className="rounded-full bg-white/5 px-3 py-1 text-[10px] uppercase tracking-wider text-white/40">{project.status}</span>}</div>
        {project && project.status !== "completed" && <ProgressPanel project={project} progress={progress} onRegenerate={regenerateScene} busySceneId={busySceneId} />}
        {project?.status === "failed" && <div className="mt-4 rounded-xl border border-red-500/20 bg-red-500/5 p-4 text-sm text-red-300">{project.error_message || "Video generation failed."}</div>}
        <FinalVideo project={project} />
        {!project && <ProgressPanel project={null} progress={progress} onRegenerate={regenerateScene} busySceneId={busySceneId} />}
      </div></aside>
    </div>
  </main>;
}
