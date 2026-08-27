export function Toast({ message, onClose }: { message: string; onClose: () => void }) {
  if (!message) return null;
  return <div role="alert" className="fixed bottom-5 right-5 z-50 flex max-w-sm items-center gap-3 rounded-xl border border-red-400/20 bg-[#14151b] px-4 py-3 text-sm text-red-200 shadow-2xl"><span>{message}</span><button type="button" onClick={onClose} aria-label="Dismiss" className="text-white/40 hover:text-white">×</button></div>;
}
