import { resetStore, setState } from "../../../../store/app-store.js";
import { resolveUtubSettings } from "../../../../types/settings.js";
import { showURLDeckBannerError } from "../../deck.js";
import { handleTaggingRefusal } from "../../../tags/policy-banner.js";
import { STAGED_GET_KEY, STAGED_RESET_KEY } from "../../tags/combobox.js";
import { initCreateURLTagPolicyObserver } from "../create.js";

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  isCoarsePointer: vi.fn(() => false),
}));

vi.mock("../../../tags/sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
}));

vi.mock("../../deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));

const URLS_REASON = "Only the owner and co-owners can tag URLs in this UTub.";
const CREATE_REASON =
  "Only the owner and co-owners can create tags in this UTub.";

function settings(canTag: boolean) {
  return resolveUtubSettings({
    tags: { members_can_tag: canTag, members_can_delete_tags: true },
  } as never);
}

function mountForm(stagedTags: string[]): void {
  document.body.innerHTML = `
    <div id="URLDeckErrorIndicator"></div>
    <div id="createURLWrap">
      <input id="urlTitleCreate" value="My title" />
      <input id="urlStringCreate" value="example.com" />
      <div class="urlTagComboboxWrap"><input class="urlTagComboboxInput" /></div>
    </div>`;
  const wrap = window.jQuery(".urlTagComboboxWrap");
  wrap.data(STAGED_GET_KEY, () => [...stagedTags]);
  wrap.data(STAGED_RESET_KEY, () => stagedTags.splice(0));
}

function picker(): HTMLElement | null {
  return document.querySelector(".urlTagComboboxWrap");
}

describe("Add URL form when tagging turns off", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    vi.mocked(showURLDeckBannerError).mockClear();
    resetStore();
    setState({
      activeUTubID: 1,
      isCurrentUserOwner: false,
      isCoCreator: false,
      settings: settings(true),
    });
    unsubscribe = initCreateURLTagPolicyObserver();
  });

  afterEach(() => unsubscribe());

  it("removes the picker, drops staged tags and shows the reason once without taking focus", () => {
    mountForm(["a", "b"]);
    setState({ settings: settings(false) });
    expect(picker()).toBeNull();
    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(URLS_REASON, {
      takeFocus: false,
    });
    expect(
      (document.getElementById("urlTitleCreate") as HTMLInputElement).value,
    ).toBe("My title");
  });

  it("shows nothing when no tags were staged (the picker still goes)", () => {
    mountForm([]);
    setState({ settings: settings(false) });
    expect(picker()).toBeNull();
    expect(showURLDeckBannerError).not.toHaveBeenCalled();
  });

  it("moves focus to the Add URL input only when it was inside the picker", () => {
    mountForm(["a"]);
    (document.querySelector(".urlTagComboboxInput") as HTMLElement).focus();
    setState({ settings: settings(false) });
    expect(document.activeElement).toBe(
      document.getElementById("urlStringCreate"),
    );

    mountForm(["a"]);
    (document.getElementById("urlTitleCreate") as HTMLElement).focus();
    setState({ settings: settings(true) });
    setState({ settings: settings(false) });
    expect(document.activeElement).toBe(
      document.getElementById("urlTitleCreate"),
    );
  });

  it("a code-18 refusal yields exactly one banner: the observer stays silent for the owned message", () => {
    mountForm(["a"]);
    handleTaggingRefusal({ message: URLS_REASON, utubID: 1 });
    expect(picker()).toBeNull();
    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(URLS_REASON, {
      takeFocus: false,
    });
  });

  it("a deck refusal with staged tags drops them and leaves TAG_URLS_NOT_ALLOWED as the last banner", async () => {
    mountForm(["a"]);
    handleTaggingRefusal({ message: CREATE_REASON, utubID: 1 });
    await vi.waitFor(() => {
      const calls = vi.mocked(showURLDeckBannerError).mock.calls;
      expect(calls[calls.length - 1][0]).toBe(URLS_REASON);
    });
    expect(picker()).toBeNull();
    expect(vi.mocked(showURLDeckBannerError).mock.calls[0][0]).toBe(
      CREATE_REASON,
    );
  });

  it("a deck refusal with no staged tags leaves only the deck text", async () => {
    mountForm([]);
    handleTaggingRefusal({ message: CREATE_REASON, utubID: 1 });
    await Promise.resolve();
    expect(showURLDeckBannerError).toHaveBeenCalledTimes(1);
    expect(showURLDeckBannerError).toHaveBeenCalledWith(CREATE_REASON, {
      takeFocus: false,
    });
  });

  it("does nothing when tagging stays allowed", () => {
    mountForm(["a"]);
    setState({ settings: settings(true) });
    expect(picker()).not.toBeNull();
  });
});
