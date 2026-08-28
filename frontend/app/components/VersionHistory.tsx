"use client";

import { useEffect, useState } from "react";
import { api, VideoProject } from "../api";

interface Props {
  project: VideoProject;
  onSelect: (project: VideoProject) => void;
}

export function VersionHistory({ project, onSelect }: Props) {
  const [versions, setVersions] = useState<VideoProject[]>([]);
  const [prompt, setPrompt] = useState(project.prompt);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setPrompt(project.prompt);
    api<VideoProject[]>(`/projects/${project.id}/versions/`).then(setVersions).catch(() => setVersions([project]));
  }, [project.id, project.prompt, project]);

  async function createVersion() {
    if (!prompt.trim() || prompt.trim() === project.prompt.trim()) return;
    setBusy(true);
    setError("");
    try {
      const next = await api<VideoProject>(`/projects/${project.id}/versions/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim(), title: project.title, input_type: project.input_type, duration: project.duration, aspect_ratio: project.aspect_ratio }),
      });
      setVersions((current) => [...current, next].sort((a, b) => a.version_number - b.version_number));
      onSelect(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create a new version.");
    } finally {
      setBusy(false);
    }
  }

  return <section className="mt-5 rounded-2xl border border-white/10 bg-white/[0.02] p-4">
    <div className="mb-3 flex items-center justify-between gap-3">
      <div><h3 className="text-sm font-semibold">Version history</h3><p className="mt-1 text-xs text-white/30">Editing creates a new version. Older videos stay intact.</p></div>
      <span className="rounded-full bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-wider text-white/40">V{project.version_number}</span>
    </div>
    <div className="mb-4 flex flex-wrap gap-2">
      {versions.map((version) => <button key={version.id} type="button" onClick={() => onSelect(version)} className={`rounded-lg border px-3 py-2 text-xs ${version.id === project.id ? "border-violet-400/40 bg-violet-400/10 text-white" : "border-white/10 text-white/45 hover:text-white"}`}>Version {version.version_number}{version.status === "completed" ? " · Ready" : version.status === "failed" ? " · Failed" : ""}</button>)}
    </div>
    <label className="mb-2 block text-xs text-white/45" htmlFor="version-prompt">Create a new version from this prompt</label>
    <textarea id="version-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} rows={4} className="w-full resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3 py-3 text-xs leading-5 outline-none focus:border-violet-500/60" />
    {error && <p role="alert" className="mt-2 text-xs text-red-300">{error}</p>}
    <button type="button" disabled={busy || !prompt.trim() || prompt.trim() === project.prompt.trim()} onClick={createVersion} className="mt-3 w-full rounded-xl border border-white/10 px-3 py-3 text-xs font-semibold text-white/70 hover:text-white disabled:cursor-not-allowed disabled:opacity-40">{busy ? "Creating version…" : `Create Version ${project.version_number + 1}`}</button>
  </section>;
}
