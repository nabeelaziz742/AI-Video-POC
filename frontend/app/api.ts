export type InputType = "story" | "script";
export type SceneStatus = "planned" | "processing" | "completed" | "failed";
export type ProjectStatus = "draft" | "queued" | "processing" | "completed" | "failed";

export interface User { id: number; username: string; email: string; first_name: string; }
export interface Character { id: number; name: string; role: string; age_description: string; appearance: string; clothing: string; personality: string; description: string; visual_prompt: string; reference_image_url: string | null; consistency_prompt: string; }
export interface VideoScene { id: number; scene_number: number; duration: number; prompt: string; characters: Character[]; status: SceneStatus; provider: string; provider_project_id: string | null; video_url: string | null; error_message: string | null; }
export interface VideoProject { id: number; title: string; input_type: InputType; prompt: string; aspect_ratio: string; duration: number; status: ProjectStatus; provider: string; provider_project_id: string | null; video_url: string | null; error_message: string | null; characters: Character[]; scenes: VideoScene[]; created_at?: string; updated_at?: string; }

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:9000/api/video";

function getCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((cookie) => cookie.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.substring(name.length + 1)) : null;
}

async function ensureCsrfToken(): Promise<string> {
  const existing = getCookie("csrftoken");
  if (existing) return existing;
  const response = await fetch(`${API_BASE_URL}/auth/csrf/`, { credentials: "include" });
  if (!response.ok) throw new Error("Unable to initialize a secure session.");
  const token = getCookie("csrftoken");
  if (!token) throw new Error("Unable to initialize a secure session.");
  return token;
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && path !== "/auth/csrf/") {
    headers.set("X-CSRFToken", await ensureCsrfToken());
  }
  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, method, headers, credentials: "include" });
  const text = await response.text();
  let data: unknown = {};
  try { data = text ? JSON.parse(text) : {}; } catch { data = { detail: text || "Request failed." }; }
  if (!response.ok) {
    const message = typeof data === "object" && data !== null && "detail" in data
      ? String((data as { detail: unknown }).detail)
      : response.status === 401 || response.status === 403 ? "Your session has expired. Please sign in again." : "Request failed.";
    throw new Error(message);
  }
  return data as T;
}

export function videoAspectClass(aspectRatio: string): string {
  if (aspectRatio === "16:9") return "aspect-video";
  if (aspectRatio === "1:1") return "aspect-square";
  return "aspect-[9/16]";
}
