"use client";

import { FormEvent, useEffect, useState } from "react";

type InputType = "story" | "script";

type CharacterDraft = {
  name: string;
  role: string;
  age_description: string;
  appearance: string;
  clothing: string;
  personality: string;
  description: string;
  visual_prompt: string;
};

interface Character extends CharacterDraft {
  id: number;
  reference_image_url: string | null;
  consistency_prompt: string;
}

interface VideoScene {
  id: number;
  scene_number: number;
  duration: number;
  prompt: string;
  status: "planned" | "processing" | "completed" | "failed";
  provider: string;
  provider_project_id: string | null;
  video_url: string | null;
  error_message: string | null;
}

interface VideoProject {
  id: number;
  title: string;
  input_type: InputType;
  prompt: string;
  aspect_ratio: string;
  duration: number;
  status: "draft" | "queued" | "processing" | "completed" | "failed";
  provider: string;
  provider_project_id: string | null;
  video_url: string | null;
  error_message: string | null;
  characters: Character[];
  scenes: VideoScene[];
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:9000/api/video";

const emptyCharacter = (): CharacterDraft => ({
  name: "",
  role: "",
  age_description: "",
  appearance: "",
  clothing: "",
  personality: "",
  description: "",
  visual_prompt: "",
});

function videoAspectClass(aspectRatio: string) {
  if (aspectRatio === "16:9") return "aspect-video";
  if (aspectRatio === "1:1") return "aspect-square";
  return "aspect-[9/16]";
}

async function api(path: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || data.detail || "Request failed.");
  return data;
}

export default function Home() {
  const [inputType, setInputType] = useState<InputType>("story");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState("9:16");
  const [characters, setCharacters] = useState<CharacterDraft[]>([
    {
      name: "Farmer",
      role: "main character",
      age_description: "adult man",
      appearance: "friendly face, medium build, black hair and moustache",
      clothing: "simple brown shalwar kameez with green vest and sandals",
      personality: "kind, hardworking and cheerful",
      description: "a warm-hearted village farmer",
      visual_prompt: "polished family-friendly 3D cartoon character, rural Pakistani village aesthetic",
    },
  ]);
  const [project, setProject] = useState<VideoProject | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState("Ready");
  const [error, setError] = useState("");

  function updateCharacter(index: number, key: keyof CharacterDraft, value: string) {
    setCharacters((current) => current.map((character, i) => i === index ? { ...character, [key]: value } : character));
  }

  async function waitForScene(projectId: number, sceneId: number) {
    for (;;) {
      const scene: VideoScene = await api(`/projects/${projectId}/scenes/${sceneId}/status/`);
      setProject((current) => current ? { ...current, scenes: current.scenes.map((item) => item.id === scene.id ? scene : item) } : current);
      if (scene.status === "completed") return scene;
      if (scene.status === "failed") throw new Error(scene.error_message || `Scene ${scene.scene_number} failed.`);
      await new Promise((resolve) => setTimeout(resolve, 4000));
    }
  }

  async function runGeneration(createdProject: VideoProject) {
    setProgress("Creating character references...");
    for (let i = 0; i < createdProject.characters.length; i += 1) {
      const character = createdProject.characters[i];
      if (!character.reference_image_url) {
        await api(`/projects/${createdProject.id}/characters/${character.id}/reference/`, { method: "POST" });
      }
      const refreshed: VideoProject = await api(`/projects/${createdProject.id}/status/`);
      setProject(refreshed);
      createdProject = refreshed;
    }

    for (let i = 0; i < createdProject.scenes.length; i += 1) {
      const scene = createdProject.scenes[i];
      setProgress(`Generating scene ${i + 1} of ${createdProject.scenes.length}...`);
      await api(`/projects/${createdProject.id}/scenes/${scene.id}/generate/`, { method: "POST" });
      await waitForScene(createdProject.id, scene.id);
      createdProject = await api(`/projects/${createdProject.id}/status/`);
      setProject(createdProject);
    }

    setProgress("Assembling final video...");
    const assembled: VideoProject = await api(`/projects/${createdProject.id}/assemble/`, { method: "POST" });
    setProject(assembled);
    setProgress("Rendering final video...");
  }

  async function generateVideo(event: FormEvent) {
    event.preventDefault();
    if (!prompt.trim()) return setError("Please enter a story or script.");
    if (!characters.length || characters.some((character) => !character.name.trim())) return setError("Add at least one character with a name.");

    setError("");
    setProject(null);
    setProgress("Creating project...");
    setIsGenerating(true);

    try {
      const created: VideoProject = await api("/projects/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: title.trim() || "Untitled Video", input_type: inputType, prompt: prompt.trim(), aspect_ratio: aspectRatio, duration, characters }),
      });
      setProject(created);
      await runGeneration(created);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Generation failed.");
      setProgress("Failed");
    } finally {
      setIsGenerating(false);
    }
  }

  useEffect(() => {
    if (!project?.id || project.status !== "processing" || !project.provider_project_id) return;
    const interval = setInterval(async () => {
      try {
        const data: VideoProject = await api(`/projects/${project.id}/status/`);
        setProject(data);
        if (data.status === "completed") setProgress("Video ready");
        if (data.status === "failed") setProgress("Failed");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unable to check status.");
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [project?.id, project?.status, project?.provider_project_id]);

  return (
    <main className="min-h-screen bg-[#08090d] text-white">
      <header className="border-b border-white/10 bg-[#0b0c11]/90">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6"><div><h1 className="text-lg font-semibold tracking-tight">AI Video Studio</h1><p className="text-xs text-white/40">Story to Character Video</p></div><div className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/50">MVP</div></div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[1fr_420px]">
        <section>
          <div className="mb-8"><p className="mb-3 text-sm font-medium text-violet-400">CREATE VIDEO</p><h2 className="text-4xl font-semibold tracking-tight">Turn your story into a character video.</h2><p className="mt-3 max-w-2xl text-sm leading-6 text-white/45">Define your recurring characters, choose 10, 30 or 60 seconds, and generate a scene-based animated video.</p></div>

          <form onSubmit={generateVideo}>
            <div className="mb-5 flex rounded-xl border border-white/10 bg-white/[0.03] p-1"><button type="button" onClick={() => setInputType("story")} className={`flex-1 rounded-lg px-4 py-3 text-sm ${inputType === "story" ? "bg-white text-black" : "text-white/50"}`}>Story Prompt</button><button type="button" onClick={() => setInputType("script")} className={`flex-1 rounded-lg px-4 py-3 text-sm ${inputType === "script" ? "bg-white text-black" : "text-white/50"}`}>Complete Script</button></div>
            <div className="mb-5"><label className="mb-2 block text-sm text-white/60">Project Title</label><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. The Farmer and His Buffalo" className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm outline-none placeholder:text-white/20 focus:border-violet-500/60" /></div>
            <div className="mb-5"><div className="mb-2 flex justify-between"><label className="text-sm text-white/60">{inputType === "story" ? "Describe your story" : "Paste your script"}</label><span className="text-xs text-white/25">{prompt.length} characters</span></div><textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={8} placeholder="A kind farmer walks through a beautiful rural village with his buffalo during the early morning..." className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-6 outline-none placeholder:text-white/20 focus:border-violet-500/60" /></div>

            <div className="mb-6 rounded-2xl border border-white/10 bg-white/[0.02] p-5">
              <div className="mb-4 flex items-center justify-between"><div><h3 className="text-sm font-semibold">Recurring Characters</h3><p className="mt-1 text-xs text-white/30">These references are reused across scenes for consistency.</p></div><button type="button" onClick={() => setCharacters([...characters, emptyCharacter()])} className="rounded-lg border border-white/10 px-3 py-2 text-xs text-white/60 hover:text-white">+ Add Character</button></div>
              <div className="space-y-5">
                {characters.map((character, index) => <div key={index} className="rounded-xl border border-white/10 bg-black/20 p-4">
                  <div className="mb-3 flex items-center justify-between"><span className="text-xs font-medium text-violet-300">Character {index + 1}</span>{characters.length > 1 && <button type="button" onClick={() => setCharacters(characters.filter((_, i) => i !== index))} className="text-xs text-red-300/60">Remove</button>}</div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    {([['name','Name','Farmer'],['role','Role','Main character'],['age_description','Age','Adult man'],['appearance','Appearance','Friendly face, medium build'],['clothing','Clothing','Brown shalwar kameez, green vest'],['personality','Personality','Kind and cheerful']] as const).map(([key,label,placeholder]) => <input key={key} value={character[key]} onChange={(e) => updateCharacter(index,key,e.target.value)} placeholder={placeholder} aria-label={label} className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs outline-none placeholder:text-white/20 focus:border-violet-500/50" />)}
                  </div>
                  <textarea value={character.description} onChange={(e) => updateCharacter(index,"description",e.target.value)} placeholder="Character description" rows={2} className="mt-3 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs outline-none placeholder:text-white/20 focus:border-violet-500/50" />
                  <input value={character.visual_prompt} onChange={(e) => updateCharacter(index,"visual_prompt",e.target.value)} placeholder="Visual style: polished family-friendly 3D cartoon" className="mt-3 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2.5 text-xs outline-none placeholder:text-white/20 focus:border-violet-500/50" />
                </div>)}
              </div>
            </div>

            <div className="mb-6 grid gap-4 sm:grid-cols-2"><div><label className="mb-2 block text-sm text-white/60">Duration</label><select value={duration} onChange={(e) => setDuration(Number(e.target.value))} className="w-full rounded-xl border border-white/10 bg-[#101117] px-4 py-3 text-sm outline-none"><option value={10}>10 seconds — Test</option><option value={30}>30 seconds</option><option value={60}>60 seconds</option></select></div><div><label className="mb-2 block text-sm text-white/60">Aspect Ratio</label><select value={aspectRatio} onChange={(e) => setAspectRatio(e.target.value)} className="w-full rounded-xl border border-white/10 bg-[#101117] px-4 py-3 text-sm outline-none"><option value="9:16">9:16 — Vertical</option><option value="16:9">16:9 — Landscape</option><option value="1:1">1:1 — Square</option></select></div></div>
            {error && <div className="mb-5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">{error}</div>}
            <button type="submit" disabled={isGenerating} className="w-full rounded-xl bg-white px-5 py-4 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50">{isGenerating ? progress : "✨ Generate Video"}</button>
          </form>
        </section>

        <aside><div className="sticky top-8 rounded-2xl border border-white/10 bg-white/[0.025] p-5"><div className="mb-5 flex items-center justify-between"><div><h3 className="text-sm font-semibold">Generation</h3><p className="mt-1 text-xs text-white/30">{progress}</p></div>{project && <span className="rounded-full bg-white/5 px-3 py-1 text-[10px] uppercase tracking-wider text-white/40">{project.status}</span>}</div>
          {!project && !isGenerating && <div className="flex aspect-[9/12] items-center justify-center rounded-xl border border-dashed border-white/10 bg-black/20"><div className="px-8 text-center"><div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-2xl">✦</div><p className="text-sm text-white/50">Your generated video will appear here.</p><p className="mt-2 text-xs leading-5 text-white/25">Add characters and start generation.</p></div></div>}
          {project && project.status !== "completed" && project.status !== "failed" && <div className="rounded-xl bg-black/30 p-6"><div className="mx-auto mb-5 h-12 w-12 animate-spin rounded-full border-2 border-white/10 border-t-violet-400" /><p className="text-center text-sm font-medium">{progress}</p><div className="mt-6 space-y-2">{project.scenes?.map((scene) => <div key={scene.id} className="flex items-center justify-between rounded-lg bg-white/[0.03] px-3 py-2 text-xs"><span>Scene {scene.scene_number} · {scene.duration}s</span><span className="text-white/40">{scene.status}</span></div>)}</div></div>}
          {project?.status === "failed" && <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6"><p className="text-sm font-medium text-red-300">Generation failed</p><p className="mt-2 text-xs leading-5 text-red-300/60">{project.error_message || error || "The video could not be generated."}</p></div>}
          {project?.status === "completed" && project.video_url && <div><div className="overflow-hidden rounded-xl bg-black"><video src={project.video_url} controls className={`${videoAspectClass(project.aspect_ratio)} w-full object-contain`} /></div><div className="mt-4 rounded-xl border border-white/10 bg-white/[0.03] p-4"><p className="text-xs text-white/40">Generated video</p><p className="mt-1 text-sm">{project.duration}s · {project.aspect_ratio} · {project.scenes.length} scenes</p><p className="mt-1 text-xs text-white/40">{project.characters.length} recurring character{project.characters.length === 1 ? "" : "s"}</p></div><a href={project.video_url} target="_blank" rel="noopener noreferrer" className="mt-4 block w-full rounded-xl bg-white px-4 py-3 text-center text-sm font-semibold text-black">Download Video</a></div>}
        </div></aside>
      </div>
    </main>
  );
}
