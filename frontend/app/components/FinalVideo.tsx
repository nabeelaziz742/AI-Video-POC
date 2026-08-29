"use client";

import { useRef, useState } from "react";
import { VideoProject, videoAspectClass } from "../api";

interface FinalVideoProps {
  project: VideoProject | null;
  onEditStory?: () => void;
  onOpenVersions?: () => void;
}

export function FinalVideo({ project, onEditStory, onOpenVersions }: FinalVideoProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [copied, setCopied] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  if (!project || project.status !== "completed" || !project.video_url) {
    return null;
  }

  const handlePlayToggle = () => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  };

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
    <div className="mt-5 overflow-hidden rounded-3xl border border-emerald-500/30 bg-[#0d0e14] shadow-2xl animate-fade-in">
      {/* Celebration Header */}
      <div className="flex items-center justify-between border-b border-white/10 bg-emerald-500/10 px-5 py-3.5">
        <div className="flex items-center gap-2">
          <span className="text-base">🎉</span>
          <p className="text-xs font-bold text-emerald-300">Your video is ready</p>
        </div>
        <span className="rounded-full bg-emerald-500/20 px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-300 border border-emerald-500/30">
          V{project.version_number} · {project.duration}s ({project.aspect_ratio})
        </span>
      </div>

      {/* Video Container */}
      <div className="relative flex items-center justify-center bg-black p-3">
        <video
          ref={videoRef}
          controls
          playsInline
          src={project.video_url}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          className={`max-h-[460px] w-full rounded-2xl object-contain shadow-lg ${videoAspectClass(project.aspect_ratio)}`}
        />
      </div>

      {/* Action Footer */}
      <div className="flex flex-col gap-3 border-t border-white/10 bg-white/[0.02] p-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold text-white line-clamp-1">{project.title}</p>
          <p className="mt-0.5 text-[11px] text-white/40">
            {project.duration} seconds • {project.aspect_ratio} • Version V{project.version_number}
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={handlePlayToggle}
            className="rounded-xl border border-white/15 bg-white/[0.05] px-3.5 py-2 text-xs font-semibold text-white transition hover:bg-white/10"
          >
            {isPlaying ? "❚❚ Pause" : "▶ Play"}
          </button>

          <a
            href={project.video_url}
            download={`${project.title.toLowerCase().replace(/\s+/g, "_")}_v${project.version_number}.mp4`}
            target="_blank"
            rel="noreferrer"
            className="rounded-xl bg-white px-3.5 py-2 text-xs font-semibold text-black transition hover:bg-white/90 shadow-md shadow-white/5"
          >
            ⬇ Download MP4
          </a>

          {onEditStory && (
            <button
              type="button"
              onClick={onEditStory}
              className="rounded-xl border border-violet-500/40 bg-violet-500/10 px-3.5 py-2 text-xs font-semibold text-violet-300 transition hover:bg-violet-500/20"
            >
              ✍ Edit Story
            </button>
          )}

          {onOpenVersions && (
            <button
              type="button"
              onClick={onOpenVersions}
              className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-medium text-white/70 transition hover:bg-white/10 hover:text-white"
            >
              ↺ History
            </button>
          )}

          <button
            type="button"
            onClick={copyUrl}
            className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-medium text-white/60 transition hover:bg-white/10 hover:text-white"
          >
            {copied ? "✓ Copied" : "Copy Link"}
          </button>
        </div>
      </div>
    </div>
  );
}
