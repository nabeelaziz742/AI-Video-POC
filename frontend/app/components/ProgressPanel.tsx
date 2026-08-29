"use client";

import { VideoProject, VideoScene, Character } from "../api";

interface ProgressPanelProps {
  project: VideoProject | null;
  progress: string;
  onRegenerate: (sceneId: number) => void;
  busySceneId: number | null;
  isGenerating?: boolean;
  onRetry?: () => void;
}

export function ProgressPanel({
  project,
  progress,
  onRegenerate,
  busySceneId,
  isGenerating = false,
  onRetry,
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

  const isFailed = project.status === "failed";
  const isCompleted = project.status === "completed";

  // Derive real pipeline stages based strictly on real backend state
  const hasCharacters = Boolean(project.characters && project.characters.length > 0);
  const allCharactersHaveRefs = hasCharacters && project.characters.every((c) => Boolean(c.reference_image_url));
  const scenesCount = project.scenes?.length || 0;
  const completedScenesCount = project.scenes?.filter((s) => s.status === "completed").length || 0;
  const anySceneProcessing = project.scenes?.some((s) => s.status === "processing");
  const allScenesCompleted = scenesCount > 0 && completedScenesCount === scenesCount;
  const isAssembling = project.provider_project_id && project.status === "processing";

  const stages = [
    {
      id: "story",
      label: "Understanding story",
      status: scenesCount > 0 ? "done" : isGenerating ? "active" : "pending",
    },
    {
      id: "characters",
      label: "Creating characters",
      status: allCharactersHaveRefs ? "done" : isGenerating && scenesCount > 0 ? "active" : "pending",
    },
    {
      id: "scenes",
      label: `Generating scenes (${completedScenesCount}/${scenesCount})`,
      status: allScenesCompleted ? "done" : anySceneProcessing || (isGenerating && allCharactersHaveRefs) ? "active" : "pending",
    },
    {
      id: "assembly",
      label: "Assembling video",
      status: isCompleted ? "done" : isAssembling ? "active" : "pending",
    },
    {
      id: "ready",
      label: "Video Ready",
      status: isCompleted ? "done" : "pending",
    },
  ];

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
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth={4} />
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
      <div className="rounded-2xl border border-white/10 bg-white/[0.025] p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            {isFailed ? (
              <span className="flex h-3 w-3 items-center justify-center rounded-full bg-red-500 text-[9px] font-bold text-white">
                !
              </span>
            ) : isGenerating ? (
              <div className="h-2.5 w-2.5 animate-pulse rounded-full bg-violet-400 shadow-sm shadow-violet-400/50" />
            ) : isCompleted ? (
              <div className="h-2.5 w-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
            ) : (
              <div className="h-2.5 w-2.5 rounded-full bg-white/40" />
            )}
            <p className="text-xs font-semibold text-white">{progress}</p>
          </div>

          <span className="text-[10px] font-medium uppercase tracking-wider text-white/40">
            V{project.version_number}
          </span>
        </div>

        {/* Failed State Display */}
        {isFailed && (
          <div className="mt-3.5 border-t border-white/5 pt-3">
            <p className="text-xs text-red-300">
              ❌ {project.error_message || "Generation failed. Credits refunded."}
            </p>
            {onRetry && (
              <button
                type="button"
                onClick={onRetry}
                className="mt-3 rounded-xl bg-white px-4 py-2 text-xs font-semibold text-black transition hover:bg-white/90"
              >
                Try Again
              </button>
            )}
          </div>
        )}
      </div>

      {/* Real-State Progress Stepper */}
      {(isGenerating || isCompleted || project.status === "processing") && (
        <div className="rounded-2xl border border-white/10 bg-black/30 p-4 space-y-2.5">
          <h4 className="text-[11px] font-semibold uppercase tracking-wider text-white/40 mb-3">
            Generation Stages
          </h4>
          {stages.map((st) => (
            <div key={st.id} className="flex items-center gap-3 text-xs">
              {st.status === "done" ? (
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-emerald-400 font-bold text-[10px] border border-emerald-500/30">
                  ✓
                </span>
              ) : st.status === "active" ? (
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-500/20 text-violet-300 font-bold text-[10px] border border-violet-500/40 animate-pulse">
                  ●
                </span>
              ) : (
                <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-white/5 text-white/30 font-bold text-[10px] border border-white/10">
                  ○
                </span>
              )}
              <span
                className={`transition ${
                  st.status === "done"
                    ? "text-white font-medium"
                    : st.status === "active"
                    ? "text-violet-300 font-semibold"
                    : "text-white/35"
                }`}
              >
                {st.label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Character References Section */}
      {project.characters && project.characters.length > 0 && (
        <div>
          <h4 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wider text-white/40">
            Character Reference Continuity
          </h4>
          <div className="grid gap-2">
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
              <div className="flex items-center justify-between gap-2">
                <span className="text-xs font-semibold text-white">
                  Scene {scene.scene_number} ({scene.duration}s)
                </span>
                {getStatusBadge(scene.status)}
              </div>

              <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-white/45">
                {scene.prompt}
              </p>

              {scene.video_url && (
                <div className="mt-3 overflow-hidden rounded-lg border border-white/10 bg-black">
                  <video
                    src={scene.video_url}
                    controls
                    playsInline
                    className="max-h-36 w-full object-contain"
                  />
                </div>
              )}

              {scene.status === "failed" && (
                <div className="mt-2 flex items-center justify-between border-t border-white/5 pt-2">
                  <span className="text-[10px] text-red-300 line-clamp-1">
                    {scene.error_message || "Generation error"}
                  </span>
                  <button
                    type="button"
                    disabled={busySceneId === scene.id}
                    onClick={() => onRegenerate(scene.id)}
                    className="text-xs font-medium text-violet-400 hover:text-violet-300"
                  >
                    {busySceneId === scene.id ? "Retrying…" : "Retry"}
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
