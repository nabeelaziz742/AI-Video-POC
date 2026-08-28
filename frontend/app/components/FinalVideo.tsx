"use client";

import { useState } from "react";
import { VideoProject, videoAspectClass } from "../api";

interface FinalVideoProps {
  project: VideoProject | null;
}

export function FinalVideo({ project }: FinalVideoProps) {
  const [copied, setCopied] = useState(false);

  if (!project || project.status !== "completed" || !project.video_url) {
    return null;
  }

  const copyUrl = async () => {
    if (!project.video_url) return;
    try {
      await navigator.clipboard.writeText(project.video_url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Ignored
    }
  };

  return (
    <div className="mt-5 overflow-hidden rounded-2xl border border-white/10 bg-[#0d0e14] shadow-2xl">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.02] px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-emerald-400" />
          <p className="text-xs font-semibold text-white">Final Render Complete</p>
        </div>
        <span className="rounded-full bg-white/5 px-2.5 py-0.5 text-[10px] uppercase tracking-wider text-white/45">
          V{project.version_number} · {project.aspect_ratio}
        </span>
      </div>

      {/* Video Container */}
      <div className="flex items-center justify-center bg-black p-2">
        <video
          controls
          playsInline
          src={project.video_url}
          className={`max-h-[480px] w-full rounded-xl object-contain ${videoAspectClass(project.aspect_ratio)}`}
        />
      </div>

      {/* Action Footer */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-white/10 bg-white/[0.02] px-4 py-3.5">
        <div>
          <p className="text-xs font-medium text-white">{project.title}</p>
          <p className="text-[11px] text-white/40">
            {project.duration}s runtime · {project.scenes?.length || 0} stitched scenes
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={copyUrl}
            className="rounded-xl border border-white/10 bg-white/[0.04] px-3 py-2 text-xs font-medium text-white/70 transition hover:bg-white/10 hover:text-white"
          >
            {copied ? "✓ Copied Link" : "Copy Link"}
          </button>

          <a
            href={project.video_url}
            target="_blank"
            rel="noreferrer"
            className="rounded-xl bg-white px-4 py-2 text-xs font-semibold text-black transition hover:bg-white/90"
          >
            Open MP4
          </a>
        </div>
      </div>
    </div>
  );
}
