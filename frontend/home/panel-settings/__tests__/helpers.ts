import { vi } from "vitest";

import type { PanelSection, QueueSink } from "../types.js";

export function makeSection(
  overrides: Partial<PanelSection> = {},
): PanelSection {
  return {
    id: "urls-sort",
    panel: "urls",
    title: "URL sort",
    scope: "utub",
    render: vi.fn(),
    save: vi.fn(async () => ({ outcome: "ok" as const })),
    ...overrides,
  };
}

export function makeSink(
  overrides: Partial<QueueSink> = {},
): { [Key in keyof QueueSink]: ReturnType<typeof vi.fn> } & QueueSink {
  return {
    report: vi.fn(),
    forceReadOnly: vi.fn(),
    announce: vi.fn(),
    resynced: vi.fn(),
    isForcedReadOnly: vi.fn(() => false),
    ...overrides,
  } as { [Key in keyof QueueSink]: ReturnType<typeof vi.fn> } & QueueSink;
}
