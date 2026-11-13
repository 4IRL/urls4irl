import { applyTagPolicyAttrs, initTagPolicyAttrs } from "../policy-attrs.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { learnPolicyOff } from "../../utubs/policy.js";
import { resolveUtubSettings } from "../../../types/settings.js";

const $ = window.jQuery;

function tagSettings({ tag, del }: { tag: boolean; del: boolean }) {
  return resolveUtubSettings({
    tags: { members_can_tag: tag, members_can_delete_tags: del },
  } as never);
}

function attrs(selector: string): [string | undefined, string | undefined] {
  return [
    $(selector).attr("data-can-tag"),
    $(selector).attr("data-can-delete-tags"),
  ];
}

describe("initTagPolicyAttrs", () => {
  let unsubscribe: () => void;

  beforeEach(() => {
    document.body.innerHTML = `<div id="TagDeck"></div><div id="URLDeck"></div>`;
    resetStore();
    setState({
      activeUTubID: 1,
      settings: tagSettings({ tag: true, del: true }),
    });
    unsubscribe = initTagPolicyAttrs();
  });

  afterEach(() => unsubscribe());

  it("sets the attributes on both decks for a permitted plain member", () => {
    expect(attrs("#TagDeck")).toEqual(["true", "true"]);
    expect(attrs("#URLDeck")).toEqual(["true", "true"]);
  });

  it("reads false for a plain member with Tagging off, delete included", () => {
    setState({ settings: tagSettings({ tag: false, del: true }) });
    expect(attrs("#TagDeck")).toEqual(["false", "false"]);
    expect(attrs("#URLDeck")).toEqual(["false", "false"]);
  });

  it("reads delete false alone when only Delete is off", () => {
    setState({ settings: tagSettings({ tag: true, del: false }) });
    expect(attrs("#TagDeck")).toEqual(["true", "false"]);
  });

  it("stays true for owners and co-owners with everything off", () => {
    setState({
      settings: tagSettings({ tag: false, del: false }),
      isCoCreator: true,
    });
    expect(attrs("#URLDeck")).toEqual(["true", "true"]);
    setState({ isCoCreator: false, isCurrentUserOwner: true });
    expect(attrs("#URLDeck")).toEqual(["true", "true"]);
  });

  it("fails closed for a plain member with no settings loaded", () => {
    setState({ settings: null });
    expect(attrs("#TagDeck")).toEqual(["false", "false"]);
  });

  it("re-applies when a refused request teaches a key is off", () => {
    learnPolicyOff({ utubID: 1, key: "tags.members_can_delete_tags" });
    expect(attrs("#TagDeck")).toEqual(["true", "false"]);
    learnPolicyOff({ utubID: 1, key: "tags.members_can_tag" });
    expect(attrs("#TagDeck")).toEqual(["false", "false"]);
    expect(getState().policyLearnedVersion).toBe(2);
  });

  it("re-applies on a role change", () => {
    setState({ settings: tagSettings({ tag: false, del: false }) });
    setState({ isCoCreator: true });
    expect(attrs("#URLDeck")).toEqual(["true", "true"]);
  });

  it("re-applies on a UTub switch alone", () => {
    $("#TagDeck").attr("data-can-tag", "stale");
    setState({ activeUTubID: 2 });
    // The store drops the old UTub's settings on a switch, so the plain
    // member's attributes fail closed until the new payload lands.
    expect(getState().settings).toBeNull();
    expect(attrs("#TagDeck")).toEqual(["false", "false"]);
    setState({ settings: tagSettings({ tag: true, del: true }) });
    expect(attrs("#TagDeck")).toEqual(["true", "true"]);
  });

  it("ignores unrelated store changes", () => {
    $("#TagDeck").attr("data-can-tag", "stale");
    setState({ selectedTagIDs: [1] });
    expect(attrs("#TagDeck")[0]).toBe("stale");
  });

  it("does not throw when the decks are absent", () => {
    document.body.innerHTML = "";
    expect(() => applyTagPolicyAttrs()).not.toThrow();
  });

  it("stops re-applying after unsubscribe", () => {
    setState({ settings: tagSettings({ tag: false, del: false }) });
    setState({ isCoCreator: true });
    unsubscribe();
    setState({ isCoCreator: false });
    expect(attrs("#URLDeck")).toEqual(["true", "true"]);
    applyTagPolicyAttrs();
    expect(attrs("#URLDeck")).toEqual(["false", "false"]);
  });
});
