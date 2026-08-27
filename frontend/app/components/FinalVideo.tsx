import { VideoProject, videoAspectClass } from "../api";

export function FinalVideo({ project }: { project: VideoProject | null }) {
  if (!project || project.status !== "completed" || !project.video_url) return null;
  return <div className="mt-4 overflow-hidden rounded-xl border border-white/10 bg-black"><video controls playsInline className={`w-full ${videoAspectClass(project.aspect_ratio)}`} src={project.video_url} /><div className="flex items-center justify-between border-t border-white/10 px-4 py-3"><div><p className="text-sm font-medium">Video ready</p><p className="text-xs text-white/35">{project.duration}s · {project.aspect_ratio}</p></div><a href={project.video_url} target="_blank" rel="noreferrer" className="rounded-lg bg-white px-3 py-2 text-xs font-semibold text-black">Open MP4</a></div></div>;
}
