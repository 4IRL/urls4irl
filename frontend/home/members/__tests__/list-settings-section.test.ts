import { AppEvents, on } from "../../../lib/event-bus.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import type { MemberSortValue } from "../../../types/preferences.js";
import { announceSettingsStatus } from "../../panel-settings/announce.js";
import { patchMemberListPreferences } from "../../panel-settings/client.js";
import type { MemberListPreferencesSaveResult } from "../../panel-settings/client.js";
import {
  closePanelSettings,
  rerenderSectionIfIdle,
} from "../../panel-settings/index.js";
import { DEBOUNCE_MS, createSaveQueue } from "../../panel-settings/queue.js";
import type { SaveQueue } from "../../panel-settings/queue.js";
import {
  _resetRegistryForTests,
  getSections,
} from "../../panel-settings/registry.js";
import type {
  PanelSection,
  QueueSink,
  SectionContext,
} from "../../panel-settings/types.js";
import { updateUTubOnFindingStaleData } from "../../utubs/stale-data.js";
import { reorderMemberDeck } from "../deck.js";
import { registerMembersListSettingsSection } from "../list-settings-section.js";

vi.mock("../../panel-settings/client.js", () => ({
  resyncSettings: vi.fn(async () => true),
  resyncMemberSettings: vi.fn(async () => true),
  patchMemberListPreferences: vi.fn(),
}));
vi.mock("../../panel-settings/index.js", () => ({
  closePanelSettings: vi.fn(),
  rerenderSectionIfIdle: vi.fn(),
}));
vi.mock("../../panel-settings/announce.js", () => ({
  announceSettingsStatus: vi.fn(),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../deck.js", () => ({
  reorderMemberDeck: vi.fn(() => []),
}));

const SORT = "#members-list-sort";
const DESC_ID = "members-list-sort-desc";
const NOTE_ID = "members-list-sort-note";
const STATUS_ID = "members-list-sort-status";

interface PendingSave {
  patch: Record<string, unknown>;
  resolve(result: MemberListPreferencesSaveResult): void;
}

function ok(memberSort: MemberSortValue): MemberListPreferencesSaveResult {
  return { outcome: "ok", preferences: { memberSort } };
}

function failed(
  outcome: "invalid" | "error" | "forbidden" | "gone",
  timedOut = false,
): MemberListPreferencesSaveResult {
  return { outcome: "failed", result: { outcome }, timedOut };
}

function sortSelect(): HTMLSelectElement {
  return document.querySelector<HTMLSelectElement>(SORT)!;
}

function pickSort(value: string): void {
  const select = sortSelect();
  select.value = value;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

function describedBy(): string[] {
  return (sortSelect().getAttribute("aria-describedby") ?? "")
    .split(" ")
    .filter((token) => token !== "");
}

function storeSort(value: MemberSortValue): void {
  setState({
    preferences: { ...getState().preferences, memberSort: value },
  });
}

async function settle(): Promise<void> {
  await vi.advanceTimersByTimeAsync(0);
}

async function debounce(): Promise<void> {
  await vi.advanceTimersByTimeAsync(DEBOUNCE_MS);
}

describe("Members list settings section", () => {
  let host: HTMLElement;
  let section: PanelSection;
  let unregister: () => void;
  let queue: SaveQueue;
  let sink: { [Key in keyof QueueSink]: ReturnType<typeof vi.fn> } & QueueSink;
  let pending: PendingSave[];
  let ctx: SectionContext;

  // Stands in for the shell: renders the section, and on a failed save
  // re-renders it (restoring focus by id) and appends its status id to the
  // select's aria-describedby.
  function renderSection(): void {
    const focusedId = host.contains(document.activeElement)
      ? (document.activeElement as HTMLElement).id
      : "";
    host.innerHTML = "";
    section.render({ container: host, ctx });
    if (focusedId !== "") document.getElementById(focusedId)?.focus();
  }

  function appendStatus(): void {
    const status = document.createElement("div");
    status.id = STATUS_ID;
    host.append(status);
    sortSelect().setAttribute(
      "aria-describedby",
      `${sortSelect().getAttribute("aria-describedby") ?? ""} ${STATUS_ID}`.trim(),
    );
  }

  function lastNotice(): string | undefined {
    const savedCalls = sink.report.mock.calls
      .map(([args]) => args as { status: string; notice?: string })
      .filter((args) => args.status === "saved");
    return savedCalls[savedCalls.length - 1]?.notice;
  }

  beforeEach(() => {
    vi.useFakeTimers();
    _resetRegistryForTests();
    resetStore();
    vi.clearAllMocks();
    document.body.innerHTML = "";
    host = document.createElement("div");
    document.body.append(host);

    pending = [];
    vi.mocked(patchMemberListPreferences).mockImplementation(
      ({ patch }) =>
        new Promise<MemberListPreferencesSaveResult>((resolve) => {
          pending.push({ patch, resolve });
        }),
    );

    unregister = registerMembersListSettingsSection();
    section = getSections("members")[0];

    sink = {
      report: vi.fn(({ status }: { status: string }) => {
        if (status === "error") {
          renderSection();
          appendStatus();
        }
      }),
      forceReadOnly: vi.fn(),
      announce: vi.fn(),
      resynced: vi.fn(),
      isForcedReadOnly: vi.fn(() => false),
    } as typeof sink;
    queue = createSaveQueue({ sink });
    ctx = {
      settings: null,
      canWrite: true,
      submit: ({ patch, debounce: shouldDebounce }) =>
        queue.enqueue({ section, patch, debounce: shouldDebounce }),
    };
    renderSection();
  });

  afterEach(() => {
    unregister();
    vi.useRealTimers();
    resetStore();
    document.body.innerHTML = "";
  });

  it("registers a global user section on the members panel", () => {
    expect(section).toMatchObject({
      id: "members-list",
      panel: "members",
      scope: "user",
      userKind: "global",
      title: "Your member list",
    });
  });

  it("renders the saved value on open and after switching UTubs, with an accessible name and description", () => {
    expect(sortSelect().value).toBe("name_az");
    expect(sortSelect().options).toHaveLength(3);
    expect(
      document.getElementById(sortSelect().getAttribute("aria-labelledby")!)
        ?.textContent,
    ).toBe("Sort members by");
    expect(document.getElementById(DESC_ID)?.textContent).toBe(
      "In all your UTubs. The owner always stays on top.",
    );

    storeSort("role_then_name");
    setState({ activeUTubID: 7 });
    renderSection();
    expect(sortSelect().value).toBe("role_then_name");
  });

  it("two quick changes end on the last value in the request, the store and the deck", async () => {
    setState({ activeUTubID: 1 });
    pickSort("role_then_name");
    pickSort("recently_joined");
    await settle();
    expect(pending).toHaveLength(0);

    await debounce();
    expect(pending.map((save) => save.patch)).toEqual([
      { memberSort: "recently_joined" },
    ]);

    pending[0].resolve(ok("recently_joined"));
    await settle();

    expect(getState().preferences.memberSort).toBe("recently_joined");
    expect(reorderMemberDeck).toHaveBeenCalledTimes(1);
    expect(reorderMemberDeck).toHaveBeenCalledWith({
      members: getState().members,
      memberSort: "recently_joined",
    });
    expect(lastNotice()).toBe("Sorted by Recently joined");
  });

  it("a normal success announces the spoken label, keeps focus on the select and does not re-render", async () => {
    sortSelect().focus();
    storeSort("role_then_name");
    renderSection();
    sortSelect().focus();
    vi.mocked(rerenderSectionIfIdle).mockClear();
    pickSort("name_az");
    await debounce();
    pending[0].resolve(ok("name_az"));
    await settle();

    expect(lastNotice()).toBe("Sorted by Name A to Z");
    expect(document.activeElement).toBe(sortSelect());
    expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
  });

  it("switching UTub during the debounce still saves, and flushing sends it without waiting", async () => {
    setState({ activeUTubID: 1 });
    pickSort("role_then_name");
    setState({ activeUTubID: 2 });
    await debounce();
    expect(pending).toHaveLength(1);
    expect(pending[0].patch).toEqual({ memberSort: "role_then_name" });
    pending[0].resolve(ok("role_then_name"));
    await settle();

    pickSort("recently_joined");
    queue.flush({ sectionId: "members-list" });
    await settle();
    expect(pending).toHaveLength(2);
    expect(pending[1].patch).toEqual({ memberSort: "recently_joined" });
  });

  it("a read-only context restores the saved value and sends nothing", async () => {
    ctx.canWrite = false;
    pickSort("role_then_name");
    await debounce();
    expect(pending).toHaveLength(0);
    expect(sortSelect().value).toBe("name_az");
  });

  describe("failed saves", () => {
    it.each([
      ["400", failed("invalid")],
      ["500", failed("error")],
      ["403", failed("forbidden")],
      ["404", failed("gone")],
      ["malformed 200", failed("error")],
    ])(
      "%s restores the saved value and leaves the deck unmoved, with no resync",
      async (_label, outcome) => {
        setState({ activeUTubID: 1 });
        sortSelect().focus();
        pickSort("role_then_name");
        await debounce();
        pending[0].resolve(outcome);
        await settle();

        expect(sortSelect().value).toBe("name_az");
        expect(getState().preferences.memberSort).toBe("name_az");
        expect(reorderMemberDeck).not.toHaveBeenCalled();
        expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
        expect(announceSettingsStatus).not.toHaveBeenCalled();
        expect(document.activeElement).toBe(sortSelect());
        expect(describedBy()).toEqual([DESC_ID, STATUS_ID]);
      },
    );

    it("a 429 shows the error with no resync", async () => {
      setState({ activeUTubID: 1 });
      pickSort("role_then_name");
      await debounce();
      // The client maps a handled 429 to timedOut:false (is429Handled in
      // panel-settings/client.ts; pinned in member-list-preferences-client.test.ts),
      // which is the outcome resolved here.
      pending[0].resolve(failed("error", false));
      await settle();

      expect(sink.report).toHaveBeenCalledWith(
        expect.objectContaining({ status: "error" }),
      );
      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
    });

    it("save A succeeds while edit B is pending and then fails: the deck follows A", async () => {
      pickSort("role_then_name");
      await debounce();
      pickSort("recently_joined");
      pending[0].resolve(ok("role_then_name"));
      await settle();

      expect(getState().preferences.memberSort).toBe("role_then_name");
      expect(reorderMemberDeck).not.toHaveBeenCalled();
      expect(lastNotice()).toBeUndefined();

      await debounce();
      expect(pending).toHaveLength(2);
      pending[1].resolve(failed("error"));
      await settle();

      expect(reorderMemberDeck).toHaveBeenCalledTimes(1);
      expect(reorderMemberDeck).toHaveBeenCalledWith({
        members: getState().members,
        memberSort: "role_then_name",
      });
      expect(sortSelect().value).toBe("role_then_name");
    });
  });

  describe("timed-out saves", () => {
    function resyncSets(value: MemberSortValue | null): void {
      vi.mocked(updateUTubOnFindingStaleData).mockImplementation(async () => {
        if (value !== null) storeSort(value);
      });
    }

    it("a timed-out save that landed ends on the saved value and announces it", async () => {
      setState({ activeUTubID: 1 });
      resyncSets("role_then_name");
      pickSort("role_then_name");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(updateUTubOnFindingStaleData).toHaveBeenCalledWith({ utubID: 1 });
      expect(sortSelect().value).toBe("role_then_name");
      expect(announceSettingsStatus).toHaveBeenCalledTimes(1);
      expect(announceSettingsStatus).toHaveBeenCalledWith({
        message: "Sorted by Role, then name",
      });
    });

    it("a timed-out B whose resync returns A ends with select and deck on A and announces A", async () => {
      setState({ activeUTubID: 1 });
      resyncSets("role_then_name");
      pickSort("recently_joined");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(sortSelect().value).toBe("role_then_name");
      expect(announceSettingsStatus).toHaveBeenCalledWith({
        message: "Sorted by Role, then name",
      });
    });

    it("a landed timeout whose resync returns the unchanged value does not announce", async () => {
      setState({ activeUTubID: 1 });
      resyncSets(null);
      pickSort("role_then_name");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(sortSelect().value).toBe("name_az");
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("a resync that errors does not announce and leaves the select on the saved value", async () => {
      setState({ activeUTubID: 1 });
      vi.mocked(updateUTubOnFindingStaleData).mockRejectedValue(
        new Error("offline"),
      );
      pickSort("role_then_name");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(sortSelect().value).toBe("name_az");
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("a resync that completes while a newer edit is outstanding does not announce", async () => {
      setState({ activeUTubID: 1 });
      vi.mocked(updateUTubOnFindingStaleData).mockImplementation(async () => {
        storeSort("recently_joined");
        pickSort("name_az");
      });
      pickSort("role_then_name");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });

    it("with no active UTub no resync runs", async () => {
      pickSort("role_then_name");
      await debounce();
      pending[0].resolve(failed("error", true));
      await settle();

      expect(updateUTubOnFindingStaleData).not.toHaveBeenCalled();
      expect(announceSettingsStatus).not.toHaveBeenCalled();
      expect(sortSelect().value).toBe("name_az");
    });

    it("save A succeeds as superseded, then B times out with the resync returning A: select and deck end on A", async () => {
      setState({ activeUTubID: 1 });
      resyncSets(null);
      pickSort("role_then_name");
      await debounce();
      pickSort("recently_joined");
      pending[0].resolve(ok("role_then_name"));
      await settle();
      expect(reorderMemberDeck).not.toHaveBeenCalled();

      await debounce();
      pending[1].resolve(failed("error", true));
      await settle();

      expect(sortSelect().value).toBe("role_then_name");
      expect(reorderMemberDeck).toHaveBeenCalledTimes(1);
      expect(reorderMemberDeck).toHaveBeenCalledWith({
        members: getState().members,
        memberSort: "role_then_name",
      });
      expect(announceSettingsStatus).not.toHaveBeenCalled();
    });
  });

  describe("store changes from refreshes", () => {
    it("a changed memberSort re-renders an idle open section", () => {
      storeSort("role_then_name");
      expect(rerenderSectionIfIdle).toHaveBeenCalledWith({
        sectionId: "members-list",
      });
      expect(rerenderSectionIfIdle).toHaveBeenCalledTimes(1);
      expect(announceSettingsStatus).not.toHaveBeenCalled();
      expect(sink.report).not.toHaveBeenCalled();

      setState({ activeUTubName: "unrelated" });
      expect(rerenderSectionIfIdle).toHaveBeenCalledTimes(1);
    });

    it("a refresh while an edit is pending keeps the select and its pending value", () => {
      pickSort("recently_joined");
      storeSort("role_then_name");
      expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
      expect(sortSelect().value).toBe("recently_joined");
    });

    it("the section's own save does not re-render it", async () => {
      pickSort("role_then_name");
      await debounce();
      pending[0].resolve(ok("role_then_name"));
      await settle();
      expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
    });

    it("unregister removes the section and the store subscription", () => {
      unregister();
      unregister = () => {};
      expect(getSections("members")).toHaveLength(0);
      storeSort("role_then_name");
      expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
    });
  });

  describe("aria-describedby", () => {
    it("lists only the description for another sort", () => {
      expect(describedBy()).toEqual([DESC_ID]);
      expect(document.getElementById(NOTE_ID)?.hidden).toBe(true);
    });

    it("lists the note right after the description when Recently joined is picked while the PATCH is pending", async () => {
      pickSort("recently_joined");
      await debounce();
      expect(pending).toHaveLength(1);
      expect(describedBy()).toEqual([DESC_ID, NOTE_ID]);
      expect(document.getElementById(NOTE_ID)?.hidden).toBe(false);
      expect(document.getElementById(NOTE_ID)?.textContent).toBe(
        "Members who joined before join dates were recorded are listed by name.",
      );

      pickSort("name_az");
      expect(describedBy()).toEqual([DESC_ID]);
      expect(document.getElementById(NOTE_ID)?.hidden).toBe(true);
    });

    it("lists [desc, status] after that save fails (saved value was not Recently joined)", async () => {
      pickSort("recently_joined");
      await debounce();
      pending[0].resolve(failed("error"));
      await settle();
      expect(describedBy()).toEqual([DESC_ID, STATUS_ID]);
    });

    it("lists [desc, note, status] after a failed save whose saved value is Recently joined, picked away first", async () => {
      storeSort("recently_joined");
      renderSection();
      expect(describedBy()).toEqual([DESC_ID, NOTE_ID]);

      pickSort("role_then_name");
      expect(describedBy()).toEqual([DESC_ID]);
      await debounce();
      pending[0].resolve(failed("error"));
      await settle();

      expect(describedBy()).toEqual([DESC_ID, NOTE_ID, STATUS_ID]);
    });

    it("inserts the note before an already-appended status id on the toggle path", () => {
      appendStatus();
      expect(describedBy()).toEqual([DESC_ID, STATUS_ID]);
      pickSort("recently_joined");
      expect(describedBy()).toEqual([DESC_ID, NOTE_ID, STATUS_ID]);
      pickSort("name_az");
      expect(describedBy()).toEqual([DESC_ID, STATUS_ID]);
    });

    it("every token resolves to an element in the section", async () => {
      storeSort("recently_joined");
      renderSection();
      appendStatus();
      for (const token of describedBy()) {
        expect(host.querySelector(`#${token}`)).not.toBeNull();
      }
    });
  });

  describe("Transfer ownership action", () => {
    const OWNER = { id: 1, username: "owner", memberRole: "creator" };
    const OTHER = { id: 2, username: "devin", memberRole: "member" };
    const TRANSFER_ROW = "#members-transfer-row";
    const TRANSFER_BTN = "#members-transfer-owner";

    function seed({
      owner,
      members,
    }: {
      owner: boolean;
      members: (typeof OWNER)[];
    }): void {
      setState({
        isCurrentUserOwner: owner,
        utubOwnerID: OWNER.id,
        members: members.map((member) => ({ ...member, joinedAt: null })),
      });
      renderSection();
    }

    function row(): HTMLElement {
      return document.querySelector<HTMLElement>(TRANSFER_ROW)!;
    }

    function button(): HTMLButtonElement {
      return document.querySelector<HTMLButtonElement>(TRANSFER_BTN)!;
    }

    it("shows a named button to the owner when another member exists", () => {
      seed({ owner: true, members: [OWNER, OTHER] });
      expect(row().hidden).toBe(false);
      expect(button().type).toBe("button");
      expect(button().textContent).toBe("Transfer ownership");
    });

    it("labels the row with an Ownership sub-header inside it", () => {
      seed({ owner: true, members: [OWNER, OTHER] });
      const heading = document.getElementById("members-transfer-heading")!;
      expect(heading.textContent).toBe("Ownership");
      expect(row().contains(heading)).toBe(true);
      expect(row().getAttribute("role")).toBe("group");
      expect(row().getAttribute("aria-labelledby")).toBe(heading.id);
    });

    it("hides the sub-header with the row for a non-owner or sole member", () => {
      seed({ owner: false, members: [OWNER, OTHER] });
      expect(row().hidden).toBe(true);
      expect(
        row().contains(document.getElementById("members-transfer-heading")),
      ).toBe(true);
      seed({ owner: true, members: [OWNER] });
      expect(row().hidden).toBe(true);
    });

    it("hides it for a non-owner viewer", () => {
      seed({ owner: false, members: [OWNER, OTHER] });
      expect(row().hidden).toBe(true);
    });

    it("hides it for a sole-owner UTub", () => {
      seed({ owner: true, members: [OWNER] });
      expect(row().hidden).toBe(true);
    });

    it("closes the gear first, then requests the picker with the gear as opener", () => {
      seed({ owner: true, members: [OWNER, OTHER] });
      const order: string[] = [];
      vi.mocked(closePanelSettings).mockImplementation(() => {
        order.push("close");
      });
      const stop = on(AppEvents.TRANSFER_PICKER_REQUESTED, ({ opener }) => {
        order.push(`emit:${opener}`);
      });

      button().click();
      stop();

      expect(order).toEqual(["close", "emit:#memberBtnSettings"]);
    });

    it("does nothing, and is marked aria-disabled, while the member-add combobox is open", () => {
      document.body.insertAdjacentHTML(
        "beforeend",
        '<div id="MemberDeck" class="member-add-open"></div>',
      );
      seed({ owner: true, members: [OWNER, OTHER] });
      const handler = vi.fn();
      const stop = on(AppEvents.TRANSFER_PICKER_REQUESTED, handler);

      button().click();
      stop();
      document.getElementById("MemberDeck")?.remove();

      expect(button().getAttribute("aria-disabled")).toBe("true");
      expect(handler).not.toHaveBeenCalled();
      expect(closePanelSettings).not.toHaveBeenCalled();
    });

    it("does nothing when the click arrives after the owner lost the right", () => {
      seed({ owner: true, members: [OWNER, OTHER] });
      setState({ isCurrentUserOwner: false });
      // Visibility already followed the store; a stale click is still refused.
      const handler = vi.fn();
      const stop = on(AppEvents.TRANSFER_PICKER_REQUESTED, handler);

      button().click();
      stop();

      expect(handler).not.toHaveBeenCalled();
      expect(closePanelSettings).not.toHaveBeenCalled();
    });

    it("follows ownership and membership changes live without re-rendering", () => {
      seed({ owner: true, members: [OWNER] });
      expect(row().hidden).toBe(true);
      vi.mocked(rerenderSectionIfIdle).mockClear();

      setState({
        members: [OWNER, OTHER].map((member) => ({
          ...member,
          joinedAt: null,
        })),
      });
      expect(row().hidden).toBe(false);

      setState({ isCurrentUserOwner: false });
      expect(row().hidden).toBe(true);

      expect(rerenderSectionIfIdle).not.toHaveBeenCalled();
    });

    it("keeps a pending sort edit when the action's visibility changes", async () => {
      seed({ owner: true, members: [OWNER, OTHER] });
      pickSort("role_then_name");

      setState({
        members: [OWNER].map((member) => ({ ...member, joinedAt: null })),
      });

      expect(row().hidden).toBe(true);
      expect(sortSelect().value).toBe("role_then_name");
      await debounce();
    });

    it("moves focus to the sort select when the focused action hides", () => {
      seed({ owner: true, members: [OWNER, OTHER] });
      button().focus();
      expect(document.activeElement).toBe(button());

      setState({
        members: [OWNER].map((member) => ({ ...member, joinedAt: null })),
      });

      expect(document.activeElement).toBe(sortSelect());
    });
  });
});
