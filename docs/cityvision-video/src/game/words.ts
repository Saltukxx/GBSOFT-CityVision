import W from "./vo_words.json";

const WORDS = W as unknown as Record<string, [string, number][]>;

/** Scene-local frame where Sarah starts saying `word` (nth occurrence) in `scene`. */
export const w = (scene: string, word: string, nth = 0): number => {
  const hits = (WORDS[scene] || []).filter(([x]) => x === word.toLowerCase());
  if (!hits[nth]) throw new Error(`VO word not found: ${scene}/${word}#${nth}`);
  return hits[nth][1];
};
