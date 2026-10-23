import { vi } from "vitest";

import { setState } from "../../../store/app-store.js";
import type { ResolvedUtubSettings } from "../../../types/settings.js";
import type { UtubSummaryItem } from "../../../types/utub.js";
import { registerSection } from "../registry.js";
import type {
  PanelSection,
  QueueSink,
  SaveResult,
  SectionContext,
} from "../types.js";

export const UTUB_ID = 7;
export const OTHER_UTUB_ID = 8;
export const SETTINGS: ResolvedUtubSettings = {
  utubs: {},
  members: {},
  tags: {},
  urls: { sort: "old" },
} as unknown as ResolvedUtubSettings;

export const FIXTURE = `
  <button id="UTubDeckHeaderAndCaret" type="button">utubs</button>
  <button id="MemberDeckHeaderAndCaret" type="button">members</button>
  <button id="TagDeckHeaderAndCaret" type="button">tags</button>
  <button id="urlBtnCreate" type="button">create</button>
  <button id="utubBtnSettings" class="panelSettingsGear hidden" data-panel="utubs"
    aria-label="UTubs settings" aria-haspopup="dialog" aria-expanded="false"
    aria-controls="panelSettingsPopover"></button>
  <button id="memberBtnSettings" class="panelSettingsGear hidden" data-panel="members"
    aria-label="Members settings" aria-haspopup="dialog" aria-expanded="false"
    aria-controls="panelSettingsPopover"></button>
  <button id="utubTagBtnSettings" class="panelSettingsGear hidden" data-panel="tags"
    aria-label="Tags settings" aria-haspopup="dialog" aria-expanded="false"
    aria-controls="panelSettingsPopover"></button>
  <button id="urlBtnSettings" class="panelSettingsGear hidden" data-panel="urls"
    aria-label="URLs settings" aria-haspopup="dialog" aria-expanded="false"
    aria-controls="panelSettingsPopover"></button>
  <button id="outside" type="button">outside</button>
  <div id="panelSettingsRoot">
    <div id="panelSettingsPopover" class="panelSettingsPopover hidden"
      role="dialog" tabindex="-1"></div>
    <div id="panelSettingsBackdrop" class="panelSettingsBackdrop hidden" aria-hidden="true"></div>
    <div id="panelSettingsSheet" class="panelSettingsSheet hidden" role="dialog"
      aria-modal="true" aria-labelledby="panelSettingsSheetTitle" tabindex="-1">
      <span id="panelSettingsSheetGrabber" class="panelSettingsSheetGrabber" aria-hidden="true"></span>
      <div id="panelSettingsSheetHeader" class="panelSettingsSheetHeader">
        <h2 id="panelSettingsSheetTitle" class="panelSettingsSheetTitle"></h2>
        <button id="panelSettingsSheetClose" class="panelSettingsSheetClose" type="button"
          aria-label="Close"></button>
      </div>
      <div id="panelSettingsSheetBody" class="panelSettingsSheetBody"></div>
    </div>
    <div id="PanelSettingsAnnouncement" aria-live="polite"></div>
  </div>
`;

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

// ------------------------------------------------------------ breakpoint

export interface BreakpointMock {
  matches: boolean;
  cross({ matches }: { matches: boolean }): void;
}

export function mockBreakpoint({
  matches,
}: {
  matches: boolean;
}): BreakpointMock {
  const listeners = new Set<() => void>();
  const query = {
    matches,
    addEventListener: (_event: string, listener: () => void) =>
      listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) =>
      listeners.delete(listener),
  };
  window.matchMedia = vi.fn(() => query) as unknown as typeof window.matchMedia;
  return {
    get matches() {
      return query.matches;
    },
    cross({ matches: next }) {
      query.matches = next;
      listeners.forEach((listener) => listener());
    },
  };
}

// ------------------------------------------------------------------- DOM

export function el(id: string): HTMLElement {
  return document.getElementById(id) as HTMLElement;
}

export function gear(panel: string): HTMLElement {
  return document.querySelector(
    `.panelSettingsGear[data-panel="${panel}"]`,
  ) as HTMLElement;
}

export function openGear(panel: string): void {
  gear(panel).click();
}

export function pressKey({
  key,
  shiftKey = false,
  target = document.body,
}: {
  key: string;
  shiftKey?: boolean;
  target?: HTMLElement;
}): KeyboardEvent {
  const event = new KeyboardEvent("keydown", {
    key,
    shiftKey,
    bubbles: true,
    cancelable: true,
  });
  target.dispatchEvent(event);
  return event;
}

// ----------------------------------------------------------------- state

export function summaries(ids: number[]): UtubSummaryItem[] {
  return ids.map((id) => ({ id, name: `UTub ${id}` })) as UtubSummaryItem[];
}

export function selectUTub({
  utubID = UTUB_ID,
  owner = true,
  locked = false,
  settings = SETTINGS,
}: {
  utubID?: number;
  owner?: boolean;
  locked?: boolean;
  settings?: ResolvedUtubSettings;
} = {}): void {
  setState({
    utubs: summaries([UTUB_ID, OTHER_UTUB_ID]),
    activeUTubID: utubID,
    isCurrentUserOwner: owner,
    isCurrentUTubLocked: locked,
    settings,
  });
}

// -------------------------------------------------------------- sections

export interface Deferred {
  promise: Promise<SaveResult>;
  resolve: (result: SaveResult) => void;
}

export function deferred(): Deferred {
  let resolve!: (result: SaveResult) => void;
  const promise = new Promise<SaveResult>((innerResolve) => {
    resolve = innerResolve;
  });
  return { promise, resolve };
}

export interface Harness {
  section: PanelSection;
  pending: Deferred[];
  ctxs: SectionContext[];
  cleanup: ReturnType<typeof vi.fn>;
  unregister: () => void;
}

// A registered section rendering one input; saves resolve through `pending`.
export function registerControlled(
  overrides: Partial<PanelSection> = {},
): Harness {
  const pending: Deferred[] = [];
  const ctxs: SectionContext[] = [];
  const cleanup = vi.fn();
  const section = makeSection({
    id: "sort",
    panel: "urls",
    title: "Sort",
    render: vi.fn(({ container, ctx }) => {
      ctxs.push(ctx);
      container.innerHTML = '<input id="sort-input" />';
      return cleanup;
    }),
    save: vi.fn(() => {
      const next = deferred();
      pending.push(next);
      return next.promise;
    }),
    ...overrides,
  });
  const unregister = registerSection(section);
  return { section, pending, ctxs, cleanup, unregister };
}

// --------------------------------------------------------------- history

export interface HistoryStub {
  pushState: ReturnType<typeof vi.fn>;
  replaceState: ReturnType<typeof vi.fn>;
  back: ReturnType<typeof vi.fn>;
  entries(): unknown[];
  index(): number;
  restore(): void;
}

/**
 * Hand-written `history`: an entries array plus index, a `state` getter for the
 * current entry, `pushState` truncating forward entries, `replaceState`
 * replacing the current one and a synchronous `back()` that moves the index and
 * dispatches a `PopStateEvent` carrying that entry's state. No-op spies are not
 * allowed for any test that exercises a close path: `history.state` would stay
 * null and every user close would take the "key missing = forced" branch.
 */
export function installHistoryStub(): HistoryStub {
  const entries: unknown[] = [history.state ?? null];
  let index = 0;
  const original = {
    state: Object.getOwnPropertyDescriptor(History.prototype, "state"),
    pushState: history.pushState,
    replaceState: history.replaceState,
    back: history.back,
  };

  const pushState = vi.fn((state: unknown) => {
    entries.splice(index + 1);
    entries.push(state);
    index = entries.length - 1;
  });
  const replaceState = vi.fn((state: unknown) => {
    entries[index] = state;
  });
  const back = vi.fn(() => {
    if (index === 0) return;
    index -= 1;
    window.dispatchEvent(
      new PopStateEvent("popstate", { state: entries[index] }),
    );
  });

  Object.defineProperty(history, "state", {
    configurable: true,
    get: () => entries[index],
  });
  history.pushState = pushState as unknown as typeof history.pushState;
  history.replaceState = replaceState as unknown as typeof history.replaceState;
  history.back = back as unknown as typeof history.back;

  return {
    pushState,
    replaceState,
    back,
    entries: () => entries,
    index: () => index,
    restore() {
      delete (history as unknown as Record<string, unknown>).state;
      if (original.state) {
        Object.defineProperty(History.prototype, "state", original.state);
      }
      history.pushState = original.pushState;
      history.replaceState = original.replaceState;
      history.back = original.back;
    },
  };
}
