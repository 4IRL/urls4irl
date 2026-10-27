import {
  createURLDateAddedBadge,
  refreshDateAddedBadges,
  refreshStackedAdderBadges,
} from "../adder-badge.js";
import { APP_CONFIG } from "../../../../lib/config.js";
import { setState } from "../../../../store/app-store.js";
import { EMPTY_MEMBER_SETTINGS } from "../../../../types/settings.js";
import type { MemberItem } from "../../../../types/member.js";

const $ = window.jQuery;

const ADDER_ID = 7;
const URL_ID = 5;

function makeURL({
  utubUrlID,
  addedByUserID,
}: {
  utubUrlID: number;
  addedByUserID: number;
}) {
  return {
    utubUrlID,
    urlTitle: "Test URL",
    urlString: "https://example.com",
    utubUrlTagIDs: [],
    canDelete: false,
    shortLinkExpiresAt: null,
    canRevokeShortLink: false,
    addedAt: "2024-03-09T12:00:00+00:00",
    addedByUserID,
  };
}

function stackedBadgeHTML(utubUrlID: number): string {
  return `<div class="urlRow" utuburlid="${utubUrlID}"><time class="urlDateAddedBadge urlDateAddedBadgeStacked">stale</time></div>`;
}

describe("refreshStackedAdderBadges", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    setState({ urls: [], members: [] });
  });

  afterEach(() => {
    setState({ urls: [], members: [] });
  });

  it("replaces the stacked badge of a card whose adder is no longer a member", () => {
    setState({
      urls: [makeURL({ utubUrlID: URL_ID, addedByUserID: ADDER_ID })],
      members: [],
    });
    document.body.innerHTML = stackedBadgeHTML(URL_ID);

    refreshStackedAdderBadges(ADDER_ID);

    const badge = $(".urlRow .urlDateAddedBadgeStacked");
    expect(badge.length).toBe(1);
    expect(badge.text()).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} ${APP_CONFIG.strings.URL_ADDED_BY_FORMER_MEMBER} · 2024-03-09`,
    );
  });

  it("only touches cards added by the given user", () => {
    setState({
      urls: [
        makeURL({ utubUrlID: URL_ID, addedByUserID: ADDER_ID }),
        makeURL({ utubUrlID: 6, addedByUserID: 8 }),
      ],
      members: [],
    });
    document.body.innerHTML = stackedBadgeHTML(URL_ID) + stackedBadgeHTML(6);

    refreshStackedAdderBadges(ADDER_ID);

    expect($('.urlRow[utuburlid="6"] .urlDateAddedBadgeStacked').text()).toBe(
      "stale",
    );
  });

  it("is a no-op when the user added no URLs in the store", () => {
    setState({
      urls: [makeURL({ utubUrlID: URL_ID, addedByUserID: 8 })],
      members: [],
    });
    document.body.innerHTML = stackedBadgeHTML(URL_ID);

    expect(() => refreshStackedAdderBadges(ADDER_ID)).not.toThrow();

    expect($(".urlDateAddedBadgeStacked").text()).toBe("stale");
  });

  it("does nothing when the store URL has no matching rendered card", () => {
    setState({
      urls: [makeURL({ utubUrlID: URL_ID, addedByUserID: ADDER_ID })],
      members: [],
    });
    document.body.innerHTML = stackedBadgeHTML(99);

    expect(() => refreshStackedAdderBadges(ADDER_ID)).not.toThrow();

    expect($('.urlRow[utuburlid="99"] .urlDateAddedBadgeStacked').text()).toBe(
      "stale",
    );
    expect($(".urlRow").length).toBe(1);
  });

  it("does nothing when the URL is missing from the store but a card is rendered", () => {
    setState({ urls: [], members: [] });
    document.body.innerHTML = stackedBadgeHTML(URL_ID);

    expect(() => refreshStackedAdderBadges(ADDER_ID)).not.toThrow();

    expect($(".urlDateAddedBadgeStacked").text()).toBe("stale");
  });
});

describe("hide date added", () => {
  const HIDE_DATE_RULE =
    '#URLDeck[data-hide-date="true"] .urlDateAddedBadgeInline { display: none !important; }';

  function hideDateSettings(hideDateAdded: boolean) {
    return {
      urls: { ...EMPTY_MEMBER_SETTINGS.urls, hide_date_added: hideDateAdded },
    };
  }

  function buildStacked() {
    return createURLDateAddedBadge({
      addedAt: "2024-03-09T12:00:00+00:00",
      addedByUserID: ADDER_ID,
      placementClass: "urlDateAddedBadgeStacked",
      withAdder: true,
      members: [{ id: ADDER_ID, username: "alice" } as MemberItem],
    });
  }

  beforeEach(() => {
    document.head.innerHTML = "";
    document.body.innerHTML = "";
    setState({ urls: [], members: [], activeUTubID: null });
  });

  afterEach(() => {
    document.head.innerHTML = "";
    setState({ urls: [], members: [], activeUTubID: null });
  });

  it("keeps the date and attribution without an override", () => {
    setState({ activeUTubID: 1, memberSettings: hideDateSettings(false) });

    const badge = buildStacked();

    expect(badge.text()).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} alice · 2024-03-09`,
    );
    expect(badge.attr("aria-label")).toContain("2024-03-09");
  });

  it("renders 'Added by <name>' with no date in text or aria-label when hidden", () => {
    setState({ activeUTubID: 1, memberSettings: hideDateSettings(true) });

    const badge = buildStacked();

    expect(badge.text()).toBe(`${APP_CONFIG.strings.URL_ADDED_BY} alice`);
    expect(badge.attr("aria-label")).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} alice`,
    );
  });

  it("still renders the date-only badge unchanged (CSS hides the inline one)", () => {
    setState({ activeUTubID: 1, memberSettings: hideDateSettings(true) });

    const badge = createURLDateAddedBadge({
      addedAt: "2024-03-09T12:00:00+00:00",
      addedByUserID: ADDER_ID,
      placementClass: "urlDateAddedBadgeInline",
      withAdder: false,
    });

    expect(badge.text()).toContain("2024-03-09");
  });

  it("hides the inline badge through the deck attribute rule", () => {
    document.head.innerHTML = `<style>${HIDE_DATE_RULE}</style>`;
    document.body.innerHTML =
      '<div id="URLDeck" data-hide-date="true"><time class="urlDateAddedBadgeInline">d</time></div>';

    expect(
      getComputedStyle(document.querySelector(".urlDateAddedBadgeInline")!)
        .display,
    ).toBe("none");
  });

  it("rebuilds every card's stacked badge in place", () => {
    setState({
      urls: [
        makeURL({ utubUrlID: URL_ID, addedByUserID: ADDER_ID }),
        makeURL({ utubUrlID: 6, addedByUserID: 8 }),
      ],
      members: [{ id: ADDER_ID, username: "alice" } as MemberItem],
      activeUTubID: 1,
      memberSettings: hideDateSettings(true),
    });
    document.body.innerHTML = stackedBadgeHTML(URL_ID) + stackedBadgeHTML(6);

    refreshDateAddedBadges();

    expect(
      $(`.urlRow[utuburlid="${URL_ID}"] .urlDateAddedBadgeStacked`).text(),
    ).toBe(`${APP_CONFIG.strings.URL_ADDED_BY} alice`);
    const former = `${APP_CONFIG.strings.URL_ADDED_BY} ${APP_CONFIG.strings.URL_ADDED_BY_FORMER_MEMBER}`;
    const other = $('.urlRow[utuburlid="6"] .urlDateAddedBadgeStacked');
    expect(other.text()).toBe(former);
    expect(other.attr("aria-label")).toBe(former);
  });
});
