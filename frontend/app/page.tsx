"use client";

import { FormEvent, useEffect, useState } from "react";

type InputType = "story" | "script";

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
}

const API_BASE_URL = "http://127.0.0.1:9000/api/video";

export default function Home() {
  const [inputType, setInputType] = useState<InputType>("story");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(10);
  const [aspectRatio, setAspectRatio] = useState("9:16");

  const [project, setProject] = useState<VideoProject | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState("");

  async function generateVideo(event: FormEvent) {
    event.preventDefault();

    if (!prompt.trim()) {
      setError("Please enter a story or script.");
      return;
    }

    setError("");
    setProject(null);
    setIsGenerating(true);

    try {
      const response = await fetch(`${API_BASE_URL}/projects/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: title.trim() || "Untitled Video",
          input_type: inputType,
          prompt: prompt.trim(),
          aspect_ratio: aspectRatio,
          duration,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.error || data.detail || "Generation failed.");
      }

      setProject(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Something went wrong while generating the video."
      );
      setIsGenerating(false);
    }
  }

  useEffect(() => {
    if (!project?.id) return;

    if (
      project.status === "completed" ||
      project.status === "failed"
    ) {
      setIsGenerating(false);
      return;
    }

    const interval = setInterval(async () => {
      try {
        const response = await fetch(
          `${API_BASE_URL}/projects/${project.id}/status/`
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail || "Unable to check status.");
        }

        setProject(data);

        if (
          data.status === "completed" ||
          data.status === "failed"
        ) {
          setIsGenerating(false);
        }
      } catch (err) {
        setError(
          err instanceof Error
            ? err.message
            : "Unable to check generation status."
        );
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [project?.id, project?.status]);

  return (
    <main className="min-h-screen bg-[#08090d] text-white">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0b0c11]/90">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              AI Video Studio
            </h1>

            <p className="text-xs text-white/40">
              Story to Video
            </p>
          </div>

          <div className="rounded-full border border-white/10 bg-white/[0.03] px-4 py-2 text-xs text-white/50">
            POC
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl gap-8 px-6 py-10 lg:grid-cols-[1fr_420px]">
        {/* Left */}
        <section>
          <div className="mb-8">
            <p className="mb-3 text-sm font-medium text-violet-400">
              CREATE VIDEO
            </p>

            <h2 className="text-4xl font-semibold tracking-tight">
              Turn your story into a video.
            </h2>

            <p className="mt-3 max-w-2xl text-sm leading-6 text-white/45">
              Enter a story or complete script and generate a video
              from a single prompt.
            </p>
          </div>

          <form onSubmit={generateVideo}>
            {/* Input type */}
            <div className="mb-5 flex rounded-xl border border-white/10 bg-white/[0.03] p-1">
              <button
                type="button"
                onClick={() => setInputType("story")}
                className={`flex-1 rounded-lg px-4 py-3 text-sm transition ${
                  inputType === "story"
                    ? "bg-white text-black"
                    : "text-white/50 hover:text-white"
                }`}
              >
                Story Prompt
              </button>

              <button
                type="button"
                onClick={() => setInputType("script")}
                className={`flex-1 rounded-lg px-4 py-3 text-sm transition ${
                  inputType === "script"
                    ? "bg-white text-black"
                    : "text-white/50 hover:text-white"
                }`}
              >
                Complete Script
              </button>
            </div>

            {/* Title */}
            <div className="mb-5">
              <label className="mb-2 block text-sm text-white/60">
                Project Title
              </label>

              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. The Farmer and His Buffalo"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-4 py-3 text-sm outline-none transition placeholder:text-white/20 focus:border-violet-500/60"
              />
            </div>

            {/* Prompt */}
            <div className="mb-5">
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm text-white/60">
                  {inputType === "story"
                    ? "Describe your story"
                    : "Paste your script"}
                </label>

                <span className="text-xs text-white/25">
                  {prompt.length} characters
                </span>
              </div>

              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                rows={10}
                placeholder={
                  inputType === "story"
                    ? "A kind farmer lives in a beautiful rural village..."
                    : "Farmer: Good morning...\nNarrator: Early one morning..."
                }
                className="w-full resize-none rounded-2xl border border-white/10 bg-white/[0.03] px-5 py-4 text-sm leading-6 outline-none transition placeholder:text-white/20 focus:border-violet-500/60"
              />
            </div>

            {/* Settings */}
            <div className="mb-6 grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-2 block text-sm text-white/60">
                  Duration
                </label>

                <select
                  value={duration}
                  onChange={(e) =>
                    setDuration(Number(e.target.value))
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#101117] px-4 py-3 text-sm outline-none"
                >
                  <option value={10}>10 seconds — Test</option>
                  <option value={30}>30 seconds</option>
                  <option value={60}>60 seconds</option>
                </select>
              </div>

              <div>
                <label className="mb-2 block text-sm text-white/60">
                  Aspect Ratio
                </label>

                <select
                  value={aspectRatio}
                  onChange={(e) =>
                    setAspectRatio(e.target.value)
                  }
                  className="w-full rounded-xl border border-white/10 bg-[#101117] px-4 py-3 text-sm outline-none"
                >
                  <option value="9:16">9:16 — Vertical</option>
                  <option value="16:9">16:9 — Landscape</option>
                  <option value="1:1">1:1 — Square</option>
                </select>
              </div>
            </div>

            {error && (
              <div className="mb-5 rounded-xl border border-red-500/20 bg-red-500/5 px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={isGenerating}
              className="w-full rounded-xl bg-white px-5 py-4 text-sm font-semibold text-black transition hover:bg-white/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isGenerating
                ? "Generating Video..."
                : "✨ Generate Video"}
            </button>
          </form>
        </section>

        {/* Right */}
        <aside>
          <div className="sticky top-8 rounded-2xl border border-white/10 bg-white/[0.025] p-5">
            <div className="mb-5 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-semibold">
                  Generation
                </h3>

                <p className="mt-1 text-xs text-white/30">
                  Your video will appear here
                </p>
              </div>

              {project && (
                <span className="rounded-full bg-white/5 px-3 py-1 text-[10px] uppercase tracking-wider text-white/40">
                  {project.status}
                </span>
              )}
            </div>

            {/* Empty */}
            {!project && !isGenerating && (
              <div className="flex aspect-[9/12] items-center justify-center rounded-xl border border-dashed border-white/10 bg-black/20">
                <div className="px-8 text-center">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-500/10 text-2xl">
                    ✦
                  </div>

                  <p className="text-sm text-white/50">
                    Your generated video will appear here.
                  </p>

                  <p className="mt-2 text-xs leading-5 text-white/25">
                    Enter your story or script and start
                    generation.
                  </p>
                </div>
              </div>
            )}

            {/* Processing */}
            {project &&
              project.status !== "completed" &&
              project.status !== "failed" && (
                <div className="flex aspect-[9/12] items-center justify-center rounded-xl bg-black/30">
                  <div className="w-full px-8">
                    <div className="mx-auto mb-6 h-12 w-12 animate-spin rounded-full border-2 border-white/10 border-t-violet-400" />

                    <p className="text-center text-sm font-medium">
                      Generating your video
                    </p>

                    <p className="mt-2 text-center text-xs leading-5 text-white/30">
                      The AI rendering service is processing
                      your request.
                    </p>

                    <div className="mt-6 h-1 overflow-hidden rounded-full bg-white/10">
                      <div className="h-full w-2/3 animate-pulse rounded-full bg-violet-500" />
                    </div>
                  </div>
                </div>
              )}

            {/* Failed */}
            {project?.status === "failed" && (
              <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-6">
                <p className="text-sm font-medium text-red-300">
                  Generation failed
                </p>

                <p className="mt-2 text-xs leading-5 text-red-300/60">
                  {project.error_message ||
                    "The video could not be generated."}
                </p>
              </div>
            )}

            {/* Completed */}
            {project?.status === "completed" &&
              project.video_url && (
                <div>
                  <div className="overflow-hidden rounded-xl bg-black">
                    <video
                      src={project.video_url}
                      controls
                      className="aspect-[9/16] w-full object-contain"
                    />
                  </div>

                  <div className="mt-4">
                    <a
                      href={project.video_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full rounded-xl bg-white px-4 py-3 text-center text-sm font-semibold text-black transition hover:bg-white/90"
                    >
                      Download Video
                    </a>
                  </div>
                </div>
              )}
          </div>
        </aside>
      </div>
    </main>
  );
}