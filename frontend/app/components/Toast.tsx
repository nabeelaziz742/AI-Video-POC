"use client";

import { useEffect } from "react";

export interface ToastProps {
  message: string;
  type?: "success" | "error" | "info";
  onClose: () => void;
  duration?: number;
}

export function Toast({ message, type = "error", onClose, duration = 4000 }: ToastProps) {
  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => {
      onClose();
    }, duration);
    return () => clearTimeout(timer);
  }, [message, duration, onClose]);

  if (!message) return null;

  const colorStyles =
    type === "success"
      ? "border-emerald-500/30 bg-[#0c1914] text-emerald-200"
      : type === "info"
      ? "border-violet-500/30 bg-[#12101e] text-violet-200"
      : "border-red-500/30 bg-[#190e10] text-red-200";

  const icon =
    type === "success" ? (
      <svg className="h-4 w-4 shrink-0 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
      </svg>
    ) : type === "info" ? (
      <svg className="h-4 w-4 shrink-0 text-violet-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ) : (
      <svg className="h-4 w-4 shrink-0 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
      </svg>
    );

  return (
    <div
      role={type === "error" ? "alert" : "status"}
      aria-live="polite"
      className={`fixed bottom-6 right-6 z-50 flex max-w-md items-center gap-3 rounded-2xl border p-4 text-sm shadow-2xl backdrop-blur-xl transition-all duration-300 ${colorStyles}`}
    >
      {icon}
      <span className="flex-1 font-medium">{message}</span>
      <button
        type="button"
        onClick={onClose}
        aria-label="Dismiss notification"
        className="rounded-lg p-1 text-white/40 hover:bg-white/10 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/40"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}
