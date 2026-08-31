"use client";

import { useEffect, useState } from "react";
import { api, VideoProject } from "../api";

interface VersionHistoryDrawerProps {
  project: VideoProject;
  isOpen: boolean;
  onClose: () => void;
  onSelectVersion: (version: VideoProject) => void;
}

export function VersionHistoryDrawer({
  project,
  isOpen,
  onClose,
  onSelectVersion,
}: VersionHistoryDrawerProps) {
  const [versions, setVersions] = useState<VideoProject[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!isOpen || !project?.id) return;
    let active = true;
    api<VideoProject[]>(`/projects/${project.id}/versions/`)
      .then((data) => {
        if (!active) return;
        // Sort descending: latest version first
        const sorted = [...data].sort((a, b) => b.version_number - a.version_number);
        setVersions(sorted);
      })
      .catch(() => {
        if (active) setVersions([project]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [isOpen, project]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm transition-opacity animate-fade-in">
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 cursor-pointer"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Drawer content */}
      <aside
        aria-label="Project version history"
        className="relative z-10 flex h-full w-full max-w-md flex-col border-l border-white/10 bg-[#0c0d12] p-6 text-white shadow-2xl transition-transform"
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-5">
          <div>
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-violet-600/20 text-xs font-bold text-violet-400 border border-violet-500/30">
                ↺
              </span>
              <h2 className="text-base font-bold tracking-tight text-white">
                Version History
              </h2>
            </div>
            <p className="mt-1 text-xs text-white/45">
              {project.title} · {versions.length} version{versions.length > 1 ? "s" : ""}
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close drawer"
            className="flex h-8 w-8 items-center justify-center rounded-xl border border-white/10 bg-white/[0.04] text-white/60 transition hover:bg-white/10 hover:text-white"
          >
            ✕
          </button>
        </div>

        {/* Versions List */}
        <div className="flex-1 overflow-y-auto py-5 space-y-3">
          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="h-24 animate-pulse rounded-2xl border border-white/5 bg-white/[0.02]"
                />
              ))}
            </div>
          ) : !versions.length ? (
            <div className="py-12 text-center text-xs text-white/40">
              No version history found.
            </div>
          ) : (
            versions.map((ver) => {
              const isCurrent = ver.id === project.id;
              return (
                <div
                  key={ver.id}
                  className={`relative flex flex-col justify-between rounded-2xl border p-4 transition ${
                    isCurrent
                      ? "border-violet-500/50 bg-violet-500/10 shadow-lg shadow-violet-500/5"
                      : "border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.035]"
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-bold text-white">
                        V{ver.version_number}
                      </span>
                      {isCurrent && (
                        <span className="rounded-md bg-violet-500/20 px-2 py-0.5 text-[10px] font-semibold text-violet-300 border border-violet-500/30">
                          Active
                        </span>
                      )}
                    </div>

                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider ${
                        ver.status === "completed"
                          ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                          : ver.status === "processing"
                          ? "bg-amber-500/10 text-amber-400 border border-amber-500/20"
                          : ver.status === "failed"
                          ? "bg-red-500/10 text-red-400 border border-red-500/20"
                          : "bg-white/5 text-white/40 border border-white/10"
                      }`}
                    >
                      {ver.status}
                    </span>
                  </div>

                  <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-white/50">
                    {ver.prompt}
                  </p>

                  <div className="mt-4 flex items-center justify-between border-t border-white/5 pt-3 text-[11px] text-white/40">
                    <span>
                      {ver.duration}s · {ver.aspect_ratio} · {ver.scenes?.length || 0} scenes
                    </span>

                    {!isCurrent ? (
                      <button
                        type="button"
                        onClick={() => {
                          onSelectVersion(ver);
                          onClose();
                        }}
                        className="rounded-lg bg-white px-3 py-1.5 text-xs font-semibold text-black transition hover:bg-white/90"
                      >
                        View
                      </button>
                    ) : (
                      <span className="text-[11px] font-medium text-violet-400">
                        Currently Loaded
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Drawer Footer */}
        <div className="border-t border-white/10 pt-4 text-center text-xs text-white/35">
          Editing this story creates a new version without overwriting previous versions.
        </div>
      </aside>
    </div>
  );
}
