/** Fills `{key}` placeholders; a function replacer keeps `$&`-style text in values literal. */
export function fillTemplate({
  template,
  values,
}: {
  template: string;
  values: Record<string, string>;
}): string {
  // Single pass: substituted values (user URL text) are never re-scanned.
  return template.replace(
    /\{(\w+)\}/g,
    (placeholder, key: string) => values[key] ?? placeholder,
  );
}
