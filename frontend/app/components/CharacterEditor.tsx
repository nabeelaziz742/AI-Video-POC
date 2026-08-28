"use client";

import { CharacterDraft } from "../character-types";

interface CharacterEditorProps {
  characters: CharacterDraft[];
  setCharacters: (value: CharacterDraft[]) => void;
  disabled?: boolean;
}

export function CharacterEditor({ characters, setCharacters, disabled = false }: CharacterEditorProps) {
  const update = (index: number, key: keyof CharacterDraft, value: string) => {
    setCharacters(
      characters.map((item, i) => (i === index ? { ...item, [key]: value } : item))
    );
  };

  const remove = (index: number) => {
    if (characters.length <= 1) return;
    setCharacters(characters.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-4">
      {characters.map((character, index) => (
        <div
          key={index}
          className="group relative rounded-2xl border border-white/10 bg-black/30 p-5 transition hover:border-white/20"
        >
          {/* Header row */}
          <div className="mb-4 flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-violet-500/20 text-xs font-semibold text-violet-300">
                {index + 1}
              </span>
              <span className="text-xs font-semibold uppercase tracking-wider text-white/70">
                {character.name.trim() ? character.name : `Character ${index + 1}`}
              </span>
              {character.role && (
                <span className="rounded-md bg-white/5 px-2 py-0.5 text-[10px] text-white/40">
                  {character.role}
                </span>
              )}
            </div>

            {characters.length > 1 && (
              <button
                type="button"
                disabled={disabled}
                onClick={() => remove(index)}
                aria-label={`Remove character ${character.name || index + 1}`}
                className="rounded-lg px-2.5 py-1 text-xs text-red-400/70 transition hover:bg-red-500/10 hover:text-red-300 disabled:opacity-40"
              >
                Remove
              </button>
            )}
          </div>

          {/* Form grid */}
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor={`char-${index}-name`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
                Name <span className="text-red-400">*</span>
              </label>
              <input
                id={`char-${index}-name`}
                value={character.name}
                disabled={disabled}
                onChange={(e) => update(index, "name", e.target.value)}
                placeholder="e.g. Farmer"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor={`char-${index}-role`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
                Role in Story
              </label>
              <input
                id={`char-${index}-role`}
                value={character.role}
                disabled={disabled}
                onChange={(e) => update(index, "role", e.target.value)}
                placeholder="e.g. Main Character, Companion"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor={`char-${index}-age`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
                Age Description
              </label>
              <input
                id={`char-${index}-age`}
                value={character.age_description}
                disabled={disabled}
                onChange={(e) => update(index, "age_description", e.target.value)}
                placeholder="e.g. adult man in his 40s"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor={`char-${index}-personality`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
                Personality
              </label>
              <input
                id={`char-${index}-personality`}
                value={character.personality}
                disabled={disabled}
                onChange={(e) => update(index, "personality", e.target.value)}
                placeholder="e.g. warm, hardworking, cheerful"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor={`char-${index}-appearance`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
                Facial & Physical Appearance
              </label>
              <input
                id={`char-${index}-appearance`}
                value={character.appearance}
                disabled={disabled}
                onChange={(e) => update(index, "appearance", e.target.value)}
                placeholder="e.g. friendly face, black hair and moustache"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>

            <div>
              <label htmlFor={`char-${index}-clothing`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
                Clothing & Attire
              </label>
              <input
                id={`char-${index}-clothing`}
                value={character.clothing}
                disabled={disabled}
                onChange={(e) => update(index, "clothing", e.target.value)}
                placeholder="e.g. simple brown shalwar kameez and sandals"
                className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2.5 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
              />
            </div>
          </div>

          <div className="mt-3">
            <label htmlFor={`char-${index}-desc`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
              General Character Summary
            </label>
            <textarea
              id={`char-${index}-desc`}
              value={character.description}
              disabled={disabled}
              onChange={(e) => update(index, "description", e.target.value)}
              placeholder="e.g. A kind-hearted farmer who cares deeply for his village and animal companions."
              rows={2}
              className="w-full resize-none rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
            />
          </div>

          <div className="mt-3">
            <label htmlFor={`char-${index}-visual`} className="mb-1 block text-[11px] font-medium uppercase tracking-wider text-white/50">
              Visual Consistency Prompt Style
            </label>
            <input
              id={`char-${index}-visual`}
              value={character.visual_prompt}
              disabled={disabled}
              onChange={(e) => update(index, "visual_prompt", e.target.value)}
              placeholder="e.g. polished 3D animation style, Pixar inspired, vibrant lighting"
              className="w-full rounded-xl border border-white/10 bg-white/[0.03] px-3.5 py-2 text-xs text-white placeholder:text-white/20 outline-none transition focus:border-violet-500/60 disabled:opacity-50"
            />
          </div>
        </div>
      ))}
    </div>
  );
}
