// Leaf module: no imports. Shared by the UTub and member sorts so both order
// names exactly like the server (Python casefold + code point comparison).

// Approximates Python's str.casefold(): the upper/lower round trip performs the
// full case mapping ("ß" -> "SS" -> "ss") that a bare toLowerCase() skips. Folds
// per code point so toLowerCase() never applies the context-dependent final-sigma
// rule, and maps a final "ς" to "σ" like casefold().
export function foldName(name: string): string {
  return Array.from(name, (char) => char.toUpperCase().toLowerCase())
    .join("")
    .replace(/ς/g, "σ");
}

// Orders by Unicode code point like Python's str comparison. A plain `<` compares
// UTF-16 code units, which puts astral characters (surrogate pairs) before
// U+E000-U+FFFF. Never localeCompare / Intl.Collator, which diverge on accents.
export function compareCodePoints({
  left,
  right,
}: {
  left: string;
  right: string;
}): number {
  let leftIndex = 0;
  let rightIndex = 0;
  while (leftIndex < left.length && rightIndex < right.length) {
    const leftPoint = left.codePointAt(leftIndex) as number;
    const rightPoint = right.codePointAt(rightIndex) as number;
    if (leftPoint !== rightPoint) return leftPoint < rightPoint ? -1 : 1;
    const width = leftPoint > 0xffff ? 2 : 1;
    leftIndex += width;
    rightIndex += width;
  }
  if (leftIndex < left.length) return 1;
  if (rightIndex < right.length) return -1;
  return 0;
}
