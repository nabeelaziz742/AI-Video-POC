"use client";

import { VideoProject, VideoScene, Character } from "../api";

interface ProgressPanelProps {
  project: VideoProject | null;
  progress: string;
  onRegenerate: (sceneId: number) => void;
  busySceneId: number | null;
  isGenerating?: boolean;
}

export function ProgressPanel({
  project,
  progress,
  onRegenerate,
  busySceneId,
  isGenerating = false,
}: ProgressPanelProps) {
  if (!project) {
    return (
      <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.015] p-8 text-center">
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-2xl text-violet-400">
          ✦
        </div>
        <h3 className="text-sm font-semibold text-white">Live Pipeline Preview</h3>
        <p className="mt-1.5 max-w-xs text-xs leading-5 text-white/40">
          Your generation progress, character references, and scene clips will update here in real time.
        </p>
      </div>
    );
  }

  const getStatusBadge = (status: VideoScene["status"]) => {
    switch (status) {
      case "completed":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-500/20">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
            </svg>
            Ready
          </span>
        );
      case "processing":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-500/20">
            <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
            </svg>
            Rendering
          </span>
        );
      case "failed":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-red-500/10 px-2.5 py-0.5 text-[11px] font-medium text-red-400 border border-red-500/20">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
            Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white/5 px-2.5 py-0.5 text-[11px] font-medium text-white/40 border border-white/10">
            <span className="h-1.5 w-1.5 rounded-full bg-white/30" />
            Planned
          </span>
        );
    }
  };

  return (
    <div className="space-y-5">
      {/* Current Step Banner */}
      <div className="rounded-xl border border-white/10 bg-white/[0.025] p-3.5">
        <div className="flex items-center gap-2.5">
          {isGenerating ? (
            <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-violet-400" />
          ) : (
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
          )}
          <p className="text-xs font-semibold text-white">{progress}</p>
        </div>
      </div>

      {/* Character References Section (if any) */}
      {project.characters && project.characters.length > 0 && (
        <div>
          <h4 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
            Character Reference Consistency
          </h4>
          <div className="grid gap-2 sm:grid-cols-2">
            {project.characters.map((char: Character) => (
              <div
                key={char.id}
                className="flex items-center gap-3 rounded-xl border border-white/10 bg-black/30 p-2.5"
              >
                {char.reference_image_url ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={char.reference_image_url}
                    alt={char.name}
                    className="h-10 w-10 shrink-0 rounded-lg object-cover border border-white/10"
                  />
                ) : (
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 text-xs font-bold text-violet-300 border border-violet-500/20">
                    {char.name.charAt(0).toUpperCase()}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium text-white">{char.name}</p>
                  <p className="text-[10px] text-white/40">
                    {char.reference_image_url ? "Reference Locked" : "Generating sheet…"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Scene Generation Cards */}
      <div>
        <div className="mb-2.5 flex items-center justify-between">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-white/40">
            Scenes ({project.scenes?.length || 0})
          </h4>
          <span className="text-[10px] text-white/30">{project.duration}s total duration</span>
        </div>

        <div className="space-y-2.5">
          {project.scenes?.map((scene: VideoScene) => (
            <div
              key={scene.id}
              className="rounded-xl border border-white/10 bg-black/25 p-3.5 transition hover:border-white/20"
            >
              {/* Scene Title + Status */}
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-white">Scene {scene.scene_number}</span>
                  <span className="text-[11px] text-white/35">· {scene.duration}s</span>
                </div>
                {getStatusBadge(scene.status)}
              </div>

              {/* Scene Prompt */}
              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-white/50">{scene.prompt}</p>

              {/* Completed Scene Preview */}
              {scene.status === "completed" && scene.video_url && (
                <div className="mt-3 overflow-hidden rounded-lg border border-white/10 bg-black">
                  <video
                    src={scene.video_url}
                    controls
                    playsInline
                    className="max-h-40 w-full object-contain"
                  />
                </div>
              )}

              {/* Error Message & Regenerate Button */}
              {scene.status === "failed" && (
                <div className="mt-3 rounded-lg border border-red-500/20 bg-red-500/5 p-3">
                  <p className="text-xs text-red-300 leading-relaxed">
                    {scene.error_message || "Generation encountered an issue at the provider."}
                  </p>
                  <button
                    type="button"
                    disabled={busySceneId !== null || isGenerating}
                    onClick={() => onRegenerate(scene.id)}
                    className="mt-2.5 inline-flex items-center gap-1.5 rounded-lg border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-xs font-medium text-red-200 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    {busySceneId === scene.id ? (
                      <>
                        <svg className="h-3 w-3 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Regenerating…
                      </>
                    ) : (
                      <>
                        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                          <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Regenerate Scene
                      </>
                    )}
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
