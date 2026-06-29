import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { filterMembersByName } from "../../logic/member-search.js";
import {
  MEMBER_SEARCH_CLOSE_TARGET,
  MEMBER_SEARCH_OPEN_TARGET,
} from "../../types/metrics-dim-values.js";

// No APP_CONFIG.constants entry exists for username minimum search length; kept as a local module constant.
const MEMBER_FILTER_MIN_LENGTH = 1;

const MEMBER_ROW_SELECTOR = "#UTubOwner .member, #listMembers .member";

type MemberSelectorEntry = { id: number; name: string };

let _memberSearchOpen: boolean = false;

// Takes the already-lowercased term as an argument (simpler than the DOM-read
// UTub pattern; both the input handler and reapplyMemberFilter have `term` in
// scope when they call this).
export function isMemberFilterActive(term: string): boolean {
  return term.length >= MEMBER_FILTER_MIN_LENGTH;
}

// Members render in two containers: the creator/owner in #UTubOwner and the
// remaining members in #listMembers. The filter reads across both so the owner
// row is hidden too when its name does not match the term.
export function readMembersFromDOM(): MemberSelectorEntry[] {
  return $.map($(MEMBER_ROW_SELECTOR).toArray(), (el: HTMLElement) => ({
    id: Number($(el).attr("memberid")),
    name: $(el).find("b").first().text(),
  }));
}

// Re-stripe the VISIBLE member rows with the `.member-stripe` class. The filter
// hides non-matching rows via `.hidden`; a CSS `:nth-child` rule would still
// count those hidden rows and misalign the stripes among the visible subset, so
// the visible rows are re-indexed here instead. The parity is anchored on the
// owner so the alternation stays unbroken across the owner -> members boundary;
// the owner row itself is never striped (always the base card shade).
export function applyAlternatingMemberBackground(): void {
  let visibleIndex = $("#UTubOwner > .member").not(".hidden").length; // 0 or 1
  $("#listMembers > .member")
    .not(".hidden")
    .each((_index, memberElem) => {
      $(memberElem).toggleClass("member-stripe", visibleIndex % 2 === 1);
      visibleIndex++;
    });
}

// Toggle `.hidden` on member rows across both containers by memberid.
export function updatedMemberFilterDisplay(memberIdsToHide: number[]): void {
  if (memberIdsToHide.length === 0) {
    $(MEMBER_ROW_SELECTOR).removeClass("hidden");
    applyAlternatingMemberBackground();
    return;
  }
  const hideSet = new Set(memberIdsToHide);
  const memberRows = $(MEMBER_ROW_SELECTOR);

  memberRows.each(function () {
    const memberID = Number($(this).attr("memberid"));
    if (hideSet.has(memberID)) {
      $(this).addClass("hidden");
    } else {
      $(this).removeClass("hidden");
    }
  });
  applyAlternatingMemberBackground();
}

export function showMemberSearchNoResults(): void {
  $("#MemberSearchNoResults")
    .text(APP_CONFIG.strings.MEMBER_SEARCH_NO_RESULTS)
    .removeClass("hidden");
  $("#MemberSearchAnnouncement").text(
    APP_CONFIG.strings.MEMBER_SEARCH_NO_RESULTS,
  );
}

export function hideMemberSearchNoResults(): void {
  $("#MemberSearchNoResults").addClass("hidden").text("");
  $("#MemberSearchAnnouncement").text("");
}

function applyMemberFilterForTerm(searchTerm: string): void {
  if (!isMemberFilterActive(searchTerm)) {
    updatedMemberFilterDisplay([]);
    hideMemberSearchNoResults();
    return;
  }
  const memberIdsToHide = filterMembersByName(readMembersFromDOM(), searchTerm);
  updatedMemberFilterDisplay(memberIdsToHide);
  const visibleCount = $(MEMBER_ROW_SELECTOR).not(".hidden").length;
  if (visibleCount === 0) {
    showMemberSearchNoResults();
  } else {
    hideMemberSearchNoResults();
    const totalCount = $(MEMBER_ROW_SELECTOR).length;
    const announcement =
      APP_CONFIG.strings.MEMBER_SEARCH_COUNT_TEMPLATE.replace(
        "{{ visible }}",
        String(visibleCount),
      ).replace("{{ total }}", String(totalCount));
    $("#MemberSearchAnnouncement").text(announcement);
  }
}

export function setMemberSelectorSearchEventListener(): void {
  const searchInput = $("#MemberNameSearch");

  searchInput
    .offAndOn("focus.memberSearchInputEsc", function () {
      // A user directly focusing #MemberNameSearch without clicking the funnel
      // will also emit — acceptable, since the input is only revealed after the
      // funnel is activated.
      if (!_memberSearchOpen) {
        _memberSearchOpen = true;
        emit({
          event: UI_EVENTS.UI_MEMBER_SEARCH_OPEN,
          target: MEMBER_SEARCH_OPEN_TARGET.MEMBERS,
        });
      }
      searchInput.offAndOn(
        "keydown.memberSearchInputEsc",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ESCAPE) {
            closeMemberNameFilter();
            searchInput.blur();
            // closeMemberNameFilter() always un-hides #memberNameFilterBtn
            // before returning, so the focus-return target is always ready.
            $("#memberNameFilterBtn").trigger("focus");
          }
        },
      );
    })
    .offAndOn("blur.memberSearchInputEsc", function () {
      _memberSearchOpen = false;
      searchInput.off("keydown.memberSearchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = getInputValue(searchInput).toLowerCase();
      applyMemberFilterForTerm(searchTerm);
    });
}

export function resetMemberFilter(): void {
  if (_memberSearchOpen) {
    emit({
      event: UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
      target: MEMBER_SEARCH_CLOSE_TARGET.MEMBERS,
    });
    _memberSearchOpen = false;
  }
  const searchInput = $("#MemberNameSearch");
  searchInput.val("");
  searchInput.off("keydown.memberSearchInputEsc");
  $(MEMBER_ROW_SELECTOR).removeClass("hidden");
  applyAlternatingMemberBackground();
  hideMemberSearchNoResults();
}

// Re-apply the active filter term after a #listMembers append so newly-added
// rows obey the current filter. Identical logic to the input handler's path.
export function reapplyMemberFilter(): void {
  const searchTerm = (
    getInputValue($("#MemberNameSearch")) ?? ""
  ).toLowerCase();
  applyMemberFilterForTerm(searchTerm);
}

export function openMemberNameFilter(): void {
  $("#MemberDeck").addClass("member-search-open");
  $("#memberNameFilterBtn").addClass("hidden").attr("aria-expanded", "true");
  $("#memberNameFilterBtnClose").removeClass("hidden");
  $("#MemberNameSearch").trigger("focus");
}

// Collapse the filter back to the funnel-only state and clear any active filter.
// The open state is read from the DOM class (not the focus flag) because the X
// button blurs the input first — clearing _memberSearchOpen before this handler
// runs — so a flag-only check would silently drop the close on the X path.
export function closeMemberNameFilter(): void {
  const wasOpen = $("#MemberDeck").hasClass("member-search-open");
  $("#MemberDeck").removeClass("member-search-open");
  $("#memberNameFilterBtnClose").addClass("hidden");
  $("#memberNameFilterBtn")
    .removeClass("hidden")
    .attr("aria-expanded", "false");
  if (wasOpen) {
    emit({
      event: UI_EVENTS.UI_MEMBER_SEARCH_CLOSE,
      target: MEMBER_SEARCH_CLOSE_TARGET.MEMBERS,
    });
    // Suppress resetMemberFilter's own CLOSE emit so the hide is recorded once
    // (the Escape path reaches here with the input still focused / flag set).
    _memberSearchOpen = false;
  }
  resetMemberFilter();
}

export function setMemberNameFilterToggleListeners(): void {
  $("#memberNameFilterBtn").offAndOnExact(
    "click.memberNameFilterShow",
    openMemberNameFilter,
  );
  $("#memberNameFilterBtnClose").offAndOnExact(
    "click.memberNameFilterClose",
    closeMemberNameFilter,
  );
}

// Reveal the funnel toggle for the selected UTub and start collapsed. Does NOT
// remove `.hidden` from #SearchMemberWrap (the CSS gate
// `#MemberDeck:not(.member-search-open) #SearchMemberWrap` is the sole
// visibility controller) and there is no subheader to hide.
export function showMemberFilterBar(): void {
  $("#memberNameFilterBtn").removeClass("hidden");
  closeMemberNameFilter();
}

// Hide the funnel/X toggles and collapse the filter. Does NOT manipulate
// `.hidden` on #SearchMemberWrap — the CSS state-class gate handles its
// visibility.
export function hideMemberFilterBar(): void {
  $("#memberNameFilterBtn").addClass("hidden");
  $("#memberNameFilterBtnClose").addClass("hidden");
  $("#MemberDeck").removeClass("member-search-open");
  resetMemberFilter();
}
