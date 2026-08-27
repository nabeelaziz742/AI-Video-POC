export type InputType = "story" | "script";
export type SceneStatus = "planned" | "processing" | "completed" | "failed";
export type ProjectStatus = "draft" | "queued" | "processing" | "completed" | "failed";

export interface Character {
  id: number;
  name: string;
  role: string;
  age_description: string;
  appearance: string;
  clothing: string;
  personality: string;
  description: string;
  visual_prompt: string;
  reference_image_url: string | null;
  consistency_prompt: string;
}

export interface VideoScene {
  id: number;
  scene_number: number;
  duration: number;
  prompt: string;
  status: SceneStatus;
  provider: string;
  provider_project_id: string | null;
  video_url: string | null;
  error_message: string | null;
}

export interface VideoProject {
  id: number;
  title: string;
  input_type: InputType;
  prompt: string;
  aspect_ratio: string;
  duration: number;
  status: ProjectStatus;
  provider: string;
  provider_project_id: string | null;
  video_url: string | null;
  error_message: string | null;
  characters: Character[];
  scenes: VideoScene[];
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:9000/api/video";

export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  const text = await response.text();
  let data: unknown = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text || "Request failed." }; }
  if (!response.ok) {
    const message = typeof data === "object" && data !== null && "detail" in data
      ? String((data as { detail: unknown }).detail)
      : "Request failed.";
    throw new Error(message);
  }
  return data as T;
}

export function videoAspectClass(aspectRatio: string): string {
  if (aspectRatio === "16:9") return "aspect-video";
  if (aspectRatio === "1:1") return "aspect-square";
  return "aspect-[9/16]";
}
