export type InputType = "story" | "script";
export type SceneStatus = "planned" | "processing" | "completed" | "failed";
export type ProjectStatus = "draft" | "queued" | "processing" | "completed" | "failed";

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  is_staff?: boolean;
  is_superuser?: boolean;
}

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
  reference_generation_attempt: number;
  consistency_prompt: string;
}

export interface VideoScene {
  id: number;
  scene_number: number;
  duration: number;
  prompt: string;
  characters: Character[];
  status: SceneStatus;
  provider: string;
  provider_project_id: string | null;
  video_url: string | null;
  error_message: string | null;
  generation_attempt: number;
  processing_started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
}

export interface VideoProject {
  id: number;
  title: string;
  version_group: string;
  version_number: number;
  input_type: InputType;
  prompt: string;
  aspect_ratio: string;
  duration: number;
  status: ProjectStatus;
  provider: string;
  provider_project_id: string | null;
  video_url: string | null;
  error_message: string | null;
  generation_attempt: number;
  processing_started_at: string | null;
  completed_at: string | null;
  failed_at: string | null;
  characters: Character[];
  scenes: VideoScene[];
  created_at?: string;
  updated_at?: string;
}

export interface CreditBalance {
  balance: number;
  monthly_allowance: number;
  used: number;
}

export interface UsageSummary {
  projects: number;
  scenes: number;
  character_references: number;
  assemblies: number;
  credits_consumed: number;
}

export interface AdminStats {
  users: { total: number; staff: number };
  subscriptions: { active_total: number; by_plan: Record<string, number> };
  projects: { total: number; completed: number; processing: number; queued: number; failed: number; draft: number };
  scenes: { total: number; completed: number; processing: number; failed: number; planned: number };
  credits: { total_circulating_balance: number; total_granted: number; total_consumed: number };
  usage: { projects: number; scenes: number; character_references: number; assemblies: number };
}

export interface AdminUserItem {
  id: number;
  username: string;
  email: string;
  is_staff: boolean;
  is_active: boolean;
  date_joined: string;
  credits_balance: number;
  monthly_allowance: number;
  plan_code: string;
  subscription_status: string;
  total_projects: number;
}

export interface AdminProjectItem {
  id: number;
  title: string;
  user: { id: number | null; username: string; email: string };
  version_number: number;
  status: ProjectStatus;
  input_type: InputType;
  duration: number;
  aspect_ratio: string;
  provider: string;
  scene_count: number;
  video_url: string | null;
  error_message: string | null;
  generation_attempt: number;
  created_at: string;
  updated_at: string;
}

export interface AdminSystemHealth {
  status: string;
  database: { connected: boolean; engine: string };
  storage: { media_root_configured: boolean; media_root_writable: boolean; static_root_configured: boolean };
  providers: {
    fal_pixverse: { configured: boolean; key_preview: string; image_model: string; resolution: string };
    json2video: { configured: boolean; key_preview: string };
    stripe: { configured: boolean; secret_key_preview: string; webhook_configured: boolean; webhook_preview: string };
  };
  environment: { debug: boolean; allowed_hosts: string[]; cors_origins: string[] };
}

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
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text || "Request failed." };
  }
  if (!response.ok) {
    const message =
      typeof data === "object" && data !== null && "detail" in data
        ? String((data as { detail: unknown }).detail)
        : response.status === 401 || response.status === 403
        ? "Your session has expired. Please sign in again."
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
