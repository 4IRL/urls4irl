import { getState, resetStore, setState } from "../../../store/app-store.js";
import {
  EMPTY_MEMBER_SETTINGS,
  type ResolvedMemberSettings,
} from "../../../types/settings.js";
import { applyTagSort } from "../../urls/cards/filtering.js";
import { applyTagCountStyleAttribute } from "../deck.js";
import { initTagDisplaySubscriptions } from "../display-subscriptions.js";

vi.mock("../../urls/cards/filtering.js", () => ({ applyTagSort: vi.fn() }));
vi.mock("../deck.js", () => ({ applyTagCountStyleAttribute: vi.fn() }));

function member(
  tags: Partial<ResolvedMemberSettings["tags"]> = {},
): ResolvedMemberSettings {
  return {
    ...EMPTY_MEMBER_SETTINGS,
    tags: { ...EMPTY_MEMBER_SETTINGS.tags, ...tags },
  };
}

describe("initTagDisplaySubscriptions", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    resetStore();
    vi.clearAllMocks();
    setState({ memberSettings: member() });
    unsubscribe = initTagDisplaySubscriptions();
  });

  afterEach(() => {
    unsubscribe();
    resetStore();
  });

  it("re-sorts once when the default sort changes", () => {
    setState({
      preferences: { ...getState().preferences, tagSort: "newest" },
    });
    expect(applyTagSort).toHaveBeenCalledTimes(1);
    expect(applyTagCountStyleAttribute).not.toHaveBeenCalled();
  });

  it("rewrites the count style once when the default count style changes", () => {
    setState({
      preferences: { ...getState().preferences, tagCountStyle: "hidden" },
    });
    expect(applyTagCountStyleAttribute).toHaveBeenCalledTimes(1);
    expect(applyTagSort).not.toHaveBeenCalled();
  });

  it("re-sorts once when an override of the sort is stored", () => {
    setState({ memberSettings: member({ tag_sort: "oldest" }) });
    expect(applyTagSort).toHaveBeenCalledTimes(1);
  });

  it("does nothing when the resolved values are unchanged", () => {
    setState({
      preferences: { ...getState().preferences, showTagsOnCollapsed: true },
    });
    setState({ memberSettings: member() });
    expect(applyTagSort).not.toHaveBeenCalled();
    expect(applyTagCountStyleAttribute).not.toHaveBeenCalled();
  });

  it("does nothing for a store change outside preferences and memberSettings", () => {
    setState({ activeUTubID: 3 });
    expect(applyTagSort).not.toHaveBeenCalled();
    expect(applyTagCountStyleAttribute).not.toHaveBeenCalled();
  });

  it("does not fire when an override masks a default change", () => {
    setState({ memberSettings: member({ tag_sort: "oldest" }) });
    vi.clearAllMocks();
    setState({
      preferences: { ...getState().preferences, tagSort: "name_az" },
    });
    expect(applyTagSort).not.toHaveBeenCalled();
  });

  it("fires when a UTub switch changes the override", () => {
    setState({ memberSettings: member({ tag_sort: "oldest" }) });
    vi.clearAllMocks();
    setState({ activeUTubID: 9, memberSettings: member() });
    expect(applyTagSort).toHaveBeenCalledTimes(1);
  });

  it("stops reacting after unsubscribe", () => {
    unsubscribe();
    setState({
      preferences: { ...getState().preferences, tagSort: "newest" },
    });
    expect(applyTagSort).not.toHaveBeenCalled();
  });
});
