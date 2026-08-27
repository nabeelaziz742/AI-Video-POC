export type CharacterDraft = { name: string; role: string; age_description: string; appearance: string; clothing: string; personality: string; description: string; visual_prompt: string };

export const emptyCharacter = (): CharacterDraft => ({ name: "", role: "", age_description: "", appearance: "", clothing: "", personality: "", description: "", visual_prompt: "" });
