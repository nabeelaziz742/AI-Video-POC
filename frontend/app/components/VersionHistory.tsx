"use client";

import { useEffect, useState } from "react";
import { api, VideoProject } from "../api";

interface VersionHistoryProps {
  project: VideoProject;
  onSelect: (project: VideoProject) => void;
  disabled?: boolean;
}

export function VersionHistory({ project, onSelect, disabled = false }: VersionHistoryProps) {
  const [versions, setVersions] = useState<VideoProject[]>([]);
  const [prompt, setPrompt] = useState(project.prompt);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const promptTimer = window.setTimeout(() => setPrompt(project.prompt), 0);
    api<VideoProject[]>(`/projects/${project.id}/versions/`)
      .then((data) => setVersions(data.sort((a, b) => a.version_number - b.version_number)))
      .catch(() => setVersions([]));
    return () => window.clearTimeout(promptTimer);
  }, [project.id, project.prompt]);

  async function createVersion() {
    if (!prompt.trim() || prompt.trim() === project.prompt.trim()) return;
    setBusy(true);
    setError("");
    try {
      const next = await api<VideoProject>(`/projects/${project.id}/versions/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          prompt: prompt.trim(),
          title: project.title,
          input_type: project.input_type,
          duration: project.duration,
          aspect_ratio: project.aspect_ratio,
        }),
      });
      setVersions((current) => [...current, next].sort((a, b) => a.version_number - b.version_number));
      onSelect(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create a new version.");
    } finally {
      setBusy(false);
    }
  }

  const isPromptChanged = prompt.trim() !== "" && prompt.trim() !== project.prompt.trim();

  return (
    <section aria-labelledby="version-history-heading" className="mt-8 rounded-3xl border border-white/10 bg-white/[0.02] p-6">
      {/* Header */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h3 id="version-history-heading" className="text-sm font-semibold text-white">
              Project Version History
            </h3>
            <span className="rounded-full bg-violet-500/10 px-2.5 py-0.5 text-[11px] font-semibold text-violet-300 border border-violet-500/20">
              Active: V{project.version_number}
            </span>
          </div>
          <p className="mt-1 text-xs text-white/40">
            Iterate on your story safely. Each iteration creates an immutable new version while preserving previous versions intact.
          </p>
        </div>
      </div>

      {/* Version Selector Pills */}
      <div className="mb-5 flex flex-wrap gap-2">
        {versions.map((ver) => {
          const isActive = ver.id === project.id;
          return (
            <button
              key={ver.id}
              type="button"
              disabled={disabled || busy}
              onClick={() => onSelect(ver)}
              className={`flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-medium transition ${
                isActive
                  ? "border-violet-500 bg-violet-500/15 text-white shadow-lg shadow-violet-500/10"
                  : "border-white/10 bg-white/[0.02] text-white/60 hover:border-white/20 hover:text-white"
              } disabled:opacity-50`}
            >
              <span>V{ver.version_number}</span>
              {ver.status === "completed" && (
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              )}
              {ver.status === "failed" && (
                <span className="h-1.5 w-1.5 rounded-full bg-red-400" />
              )}
              {ver.status === "processing" && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-400" />
              )}
              <span className="text-[10px] uppercase tracking-wider text-white/40">
                {ver.status}
              </span>
            </button>
          );
        })}
      </div>

      {/* Modify Story for New Version */}
      <div className="rounded-2xl border border-white/5 bg-black/30 p-4">
        <label
          htmlFor="version-prompt-input"
          className="mb-2 block text-xs font-medium text-white/60"
        >
          Branch a new version from modified prompt:
        </label>
        <textarea
          id="version-prompt-input"
          value={prompt}
          disabled={disabled || busy}
          onChange={(e) => setPrompt(e.target.value)}
          rows={4}
          className="w-full resize-none rounded-xl border border-white/10 bg-white/[0.03] p-3 text-xs leading-relaxed text-white placeholder-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
          placeholder="Edit prompt to create a new version…"
        />

        {error && (
          <p role="alert" className="mt-2 text-xs text-red-300">
            {error}
          </p>
        )}

        <div className="mt-3 flex items-center justify-between">
          <p className="text-[11px] text-white/35">
            {isPromptChanged
              ? "Prompt modified. Ready to generate next version."
              : "Make changes to the prompt above to enable creating a new version."}
          </p>

          <button
            type="button"
            disabled={!isPromptChanged || busy || disabled}
            onClick={createVersion}
            className="rounded-xl bg-white px-4 py-2 text-xs font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-30"
          >
            {busy ? "Branching Version…" : `Create Version ${project.version_number + 1}`}
          </button>
        </div>
      </div>
    </section>
  );
}
