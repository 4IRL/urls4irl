import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { SHOW_LOADING_ICON_AFTER_MS } from "../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { getState, setState } from "../../store/app-store.js";
import { createMemberBadge } from "./members.js";
import { setMemberDeckForUTub } from "./deck.js";
import { reapplyMemberFilter } from "./search.js";
import {
  reapplyMemberDeckSiblingControlSuppression,
  RENDER_KEY,
  STAGED_GET_KEY,
  STAGED_REMOVE_KEY,
} from "./member-combobox.js";

import type { StagedMemberChip } from "./member-combobox.js";
import type { MemberModifiedResponse } from "../../types/member.js";

// Per-chip batch add (Step 6). This module is a NEW organizational split — there
// is no `combobox-submit.ts` in the codebase to mirror. The request/success/fail
// SHAPE follows submitStagedTags/submitStagedTagsSuccess/submitStagedTagsFail
// (frontend/home/urls/tags/combobox.ts:1004,1059,1098), which live inside
// combobox.ts itself. Unlike that single-batch-endpoint precedent, member add
// fires N INDEPENDENT POSTs (one per chip) so chips resolve at different times
// (mock State 2), tracked via Promise.allSettled — never $.when, which would
// short-circuit on the first rejection and suppress feedback for chips still in
// flight.

// How a single chip's own POST settled. The wrapper Promise ALWAYS resolves with
// one of these (never rejects), so Promise.allSettled waits on every chip
// regardless of that chip's outcome.
type ChipOutcome = "fulfilled" | "rejected" | "skipped_429";

type ChipSettleResult = {
  chip: StagedMemberChip;
  outcome: ChipOutcome;
  // Present only for a 200: the added member, appended once after settle.
  member?: MemberModifiedResponse["member"];
  // Present only for a 400: the failure reason, carried by the chip's title
  // tooltip and reused in the batched aria-live summary.
  errorText?: string;
};

/**
 * Fires one independent POST per staged chip, each resolving on its own with the
 * delayed loading-ring idiom and correct `source` dim. The batch's target UTub
 * is captured up front (`batchUtubID`) so a UTub switch mid-flight cannot
 * misdirect the once-after-settle deck sync. After every chip settles the deck
 * is synced ONCE (from the resolved results array, not the individual `.done`
 * closures) and the batched aria-live summary is announced once.
 */
export async function submitStagedMembers({
  utubID,
  wrap,
}: {
  utubID: number;
  wrap: JQuery;
}): Promise<void> {
  // The batch's target UTub, fixed at submit start regardless of any UTub switch
  // while the N requests are in flight.
  const batchUtubID = utubID;

  const getStaged = wrap.data(STAGED_GET_KEY) as
    | (() => StagedMemberChip[])
    | undefined;
  const stagedChips = getStaged ? getStaged() : [];
  if (stagedChips.length === 0) return;

  // Guard against a double-submit while the batch is in flight; the post-settle
  // re-render re-evaluates the enabled/label state from what remains staged.
  wrap.find(".memberAddComboboxSubmitBtn").prop("disabled", true);

  // Each chip's wrapper Promise ALWAYS resolves (never rejects); allSettled is
  // required over $.when so every chip is waited on regardless of its outcome.
  const promises: Promise<ChipSettleResult>[] = stagedChips.map((chip) =>
    submitOneChip({ chip, utubID: batchUtubID, wrap }),
  );

  const settled = await Promise.allSettled(promises);
  // Wrapper promises never reject, so every entry is fulfilled with our result.
  const results: ChipSettleResult[] = settled.map(
    (entry) => (entry as PromiseFulfilledResult<ChipSettleResult>).value,
  );

  // Same activeUTubID relevance check cross-utub-search.ts:577 uses.
  const stillOnBatchUTub = getState().activeUTubID === batchUtubID;

  applyPostSettleSideEffects({ results, batchUtubID, wrap, stillOnBatchUTub });
}

/**
 * Issues one chip's POST and returns a Promise that ALWAYS resolves with the
 * chip's settle result (captured from within its own `.done`/`.fail`). Shows the
 * per-chip delayed loading ring gated by SHOW_LOADING_ICON_AFTER_MS so fast adds
 * never flicker. Real-time per-chip visual feedback (ring / green ✓ / red ✗)
 * touches only this chip's own staged-strip DOM — never the target UTub's deck.
 */
function submitOneChip({
  chip,
  utubID,
  wrap,
}: {
  chip: StagedMemberChip;
  utubID: number;
  wrap: JQuery;
}): Promise<ChipSettleResult> {
  const chipEl = findChipElement(wrap, chip.username);
  const ring = chipEl.find(".memberAddStagedChipRing");

  return new Promise<ChipSettleResult>((resolve) => {
    const loadingTimeoutID = setTimeout(() => {
      ring.addClass("dual-loading-ring");
    }, SHOW_LOADING_ICON_AFTER_MS);

    // Outsider chips POST the exact typed casing (source='exact_username');
    // co-member chips POST the canonical username (source='search_result'). Both
    // are already captured on the staged chip.
    const request = ajaxCall("post", APP_CONFIG.routes.createMember(utubID), {
      username: chip.username,
      source: chip.source,
    });

    request.done((response: MemberModifiedResponse) => {
      // ajaxCall's .done only fires on a 2xx; the backend returns 200 with the
      // added member. Always settle the wrapper (a non-settling branch here
      // would hang Promise.allSettled). The store push + deck badge for this
      // member run once after all chips settle, gated by the SAME UTub-relevance
      // check, so the store and the deck DOM can never diverge (see
      // applyPostSettleSideEffects).
      clearTimeout(loadingTimeoutID);
      ring.removeClass("dual-loading-ring");
      markChipAdded(chipEl);
      resolve({ chip, outcome: "fulfilled", member: response.member });
    });

    request.fail((xhr: JQuery.jqXHR) => {
      clearTimeout(loadingTimeoutID);
      ring.removeClass("dual-loading-ring");

      if (is429Handled(xhr)) {
        // The wrapper must still settle or Promise.allSettled would hang — the
        // chip's own UI stays visually pending while the global 429 UI fires,
        // and it is excluded from the aggregate summary below.
        resolve({ chip, outcome: "skipped_429" });
        return;
      }

      // 400 → red ✗ marker on this chip + reason in its title tooltip (siblings
      // unaffected). Anything else (403 HTML / unknown) → the existing redirect.
      const errorText = markChipFailed(chipEl, xhr);
      if (errorText === null) {
        redirectOnFatalFailure(xhr);
      }
      resolve({ chip, outcome: "rejected", errorText: errorText ?? undefined });
    });
  });
}

/**
 * Runs the once-after-all-settle side effects from the RESOLVED RESULTS ARRAY.
 * When the creator is still on the batch's UTub, appends a deck badge for every
 * fulfilled chip and syncs the deck ONCE; otherwise skips all deck-DOM mutations
 * (the deck may already be torn down) and surfaces completion via a non-deck
 * aria-live path. Then clears only the succeeded chips (stay-open flow), leaving
 * failed chips (red ✗ + reason tooltip) staged for retry, and refocuses the input.
 */
function applyPostSettleSideEffects({
  results,
  batchUtubID,
  wrap,
  stillOnBatchUTub,
}: {
  results: ChipSettleResult[];
  batchUtubID: number;
  wrap: JQuery;
  stillOnBatchUTub: boolean;
}): void {
  const summary = buildSummaryMessage(results);
  const fulfilled = results.filter((result) => result.outcome === "fulfilled");

  if (stillOnBatchUTub) {
    // Dedupe by id against members already in the store: when the creator
    // switched away and back to the SAME UTub mid-batch, the UTub-select flow
    // re-fetched `members` fresh (already including an earlier-completing chip's
    // member). Without this guard, this stale batch would append that member —
    // store entry + duplicate #listMembers badge — a second time.
    const existingMemberIds = new Set(
      getState().members.map((member) => member.id),
    );
    const addedMembers = fulfilled
      .map((result) => result.member)
      .filter((member): member is NonNullable<typeof member> => Boolean(member))
      .filter((member) => !existingMemberIds.has(member.id))
      .map((member) => ({
        ...member,
        memberRole: APP_CONFIG.constants.MEMBER_ROLES.MEMBER,
      }));
    if (addedMembers.length > 0) {
      // Store push + deck badge append are unified under this single
      // UTub-relevance check so getState().members and the deck DOM stay in sync
      // (never one without the other).
      setState({ members: [...getState().members, ...addedMembers] });
      const isOwner = getState().isCurrentUserOwner;
      const listMembers = $("#listMembers");
      addedMembers.forEach((member) => {
        listMembers.append(
          createMemberBadge(member.id, member.username, isOwner, batchUtubID),
        );
      });
      // Deck subheader count + filter re-stripe run ONCE total, after the appends.
      setMemberDeckForUTub(true);
      reapplyMemberFilter();
      // The just-appended member badges carry their own active
      // `.memberOtherBtnDelete` remove buttons; the combobox stays open (stay-open
      // flow), so re-suppress them too — otherwise a creator could open a removal
      // modal for a freshly-added member mid-stage and strand staged state.
      reapplyMemberDeckSiblingControlSuppression();
    }
    // Announce the batched summary ONCE to the combobox's OWN aria-live region
    // (never the filter's #MemberSearchAnnouncement).
    if (summary) wrap.find(".memberAddComboboxMsg").text(summary);
  } else if (summary) {
    // Creator switched UTubs while the batch was in flight: the combobox this
    // batch was staged against may already be torn down (resetMemberDeck). No
    // general toast utility exists in this codebase, so completion is surfaced
    // via the persistent, non-deck, home-level #MobilePanelAnnouncement
    // aria-live region, which survives the deck teardown.
    $("#MobilePanelAnnouncement").text(summary);
  }

  // Post-settle stay-open lifecycle: drop only the succeeded chips (DOM +
  // backing staged state); leave failed chips in place (red ✗ + reason tooltip)
  // so the creator can retry without re-typing. The combobox never auto-closes.
  const succeededUsernames = fulfilled.map((result) => result.chip.username);
  succeededUsernames.forEach((username) => {
    findChipElement(wrap, username).remove();
  });
  const removeStaged = wrap.data(STAGED_REMOVE_KEY) as
    | ((usernames: string[]) => void)
    | undefined;
  if (removeStaged) removeStaged(succeededUsernames);

  // Re-render refreshes the listbox exclusions + the "Add N" enabled/label state
  // for whatever remains staged.
  const render = wrap.data(RENDER_KEY) as (() => void) | undefined;
  if (render) render();

  // Explicit post-settle refocus target (WCAG 2.4.3).
  wrap.find(".memberAddComboboxInput").trigger("focus");
}

/**
 * Builds a brief count-based summary of the batch outcome (e.g. "3 members
 * added, 2 members couldn't be added"). Each chip already shows its own green
 * ✓ / red ✗ (failed chips also carry the reason in a `title` tooltip), so the
 * summary only recaps counts rather than enumerating every username. Singular
 * vs plural is chosen per count. 429-skipped chips are excluded from the counts
 * — their global 429 UI already communicated the outcome. Returns "" when both
 * counts are 0 so the caller's `if (summary)` guard suppresses an empty
 * announcement.
 */
function buildSummaryMessage(results: ChipSettleResult[]): string {
  const addedCount = results.filter(
    (result) => result.outcome === "fulfilled",
  ).length;
  const failedCount = results.filter(
    (result) => result.outcome === "rejected",
  ).length;

  const parts: string[] = [];
  if (addedCount > 0) {
    parts.push(
      addedCount === 1
        ? APP_CONFIG.strings.MEMBER_ADD_SUMMARY_ADDED_ONE
        : APP_CONFIG.strings.MEMBER_ADD_SUMMARY_ADDED.replace(
            "{{ count }}",
            () => String(addedCount),
          ),
    );
  }
  if (failedCount > 0) {
    parts.push(
      failedCount === 1
        ? APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED_ONE
        : APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED.replace(
            "{{ count }}",
            () => String(failedCount),
          ),
    );
  }
  return parts.join(", ");
}

/** Locates a staged chip's DOM element by its (unique, case-sensitive) username. */
function findChipElement(wrap: JQuery, username: string): JQuery {
  return wrap
    .find(".memberAddStagedChip")
    .filter(
      (_index, element) => $(element).attr("data-staged-username") === username,
    );
}

// Status-marker icons as inline <svg> path data (Bootstrap Icons: check-circle-fill
// / exclamation-triangle-fill). This project has NO bootstrap-icons FONT — every
// `bi` icon in the codebase is inline SVG, and a bare `<i class="bi …">` renders
// nothing — so the marker must be inline SVG. `fill="currentColor"` makes each
// inherit its red/green from the chip's outcome CSS class; `aria-hidden` because
// the outcome is conveyed by the aria-live summary + the chip's title tooltip.
const STATUS_ICON_ADDED =
  '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="bi bi-check-circle-fill" viewBox="0 0 16 16" aria-hidden="true">' +
  '<path d="M16 8A8 8 0 1 1 0 8a8 8 0 0 1 16 0zm-3.97-3.03a.75.75 0 0 0-1.08.022L7.477 9.417 5.384 7.323a.75.75 0 0 0-1.06 1.06L6.97 11.03a.75.75 0 0 0 1.079-.02l3.992-4.99a.75.75 0 0 0-.01-1.05z"/></svg>';
const STATUS_ICON_FAILED =
  '<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" class="bi bi-exclamation-triangle-fill" viewBox="0 0 16 16" aria-hidden="true">' +
  '<path d="M8.982 1.566a1.13 1.13 0 0 0-1.96 0L.165 13.233c-.457.778.091 1.767.98 1.767h13.713c.889 0 1.438-.99.98-1.767zM8 5c.535 0 .954.462.9.995l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 5.995A.905.905 0 0 1 8 5m.002 6a1 1 0 1 1 0 2 1 1 0 0 1 0-2"/></svg>';

/**
 * Renders a status-marker SVG into the chip's (decorative, aria-hidden) status
 * slot, replacing any prior marker. Inline SVG — not an icon-font `<i>` — because
 * this project ships no bootstrap-icons font (see the icon consts above).
 */
function setChipStatusIcon(chipEl: JQuery, svgMarkup: string): void {
  chipEl.find(".memberAddStagedChipStatus").html(svgMarkup);
}

/** Marks a chip added: green check-circle status icon + success skin. */
function markChipAdded(chipEl: JQuery): void {
  chipEl
    .removeClass("memberAddStagedChipFailed")
    .addClass("memberAddStagedChipAdded");
  chipEl.removeAttr("title");
  setChipStatusIcon(chipEl, STATUS_ICON_ADDED);
}

/**
 * Marks a chip failed on a 400: a red WARNING icon (bi-exclamation-triangle-fill,
 * deliberately not an ✗ — that collided with the `×` remove button) next to the
 * username + the failed skin, with the failure *reason* carried by the chip's
 * `title` tooltip (never rendered inline beside the username — that text overflowed
 * off-screen; the visible reason lives in the batched summary line under the strip
 * instead). Returns the message text (for the summary), or `null` for any non-400
 * (403 HTML / unknown) so the caller redirects. USER_NOT_EXIST arrives as
 * `errors.username`; MEMBER_ALREADY_IN_UTUB as `message`.
 */
function markChipFailed(chipEl: JQuery, xhr: JQuery.jqXHR): string | null {
  if (!("responseJSON" in xhr) || xhr.status !== 400) {
    return null;
  }
  const responseJSON = xhr.responseJSON as {
    errors?: { username?: string[] };
    message?: string;
  };
  let message = "";
  if (responseJSON.errors?.username?.length) {
    message = responseJSON.errors.username[0];
  } else if (responseJSON.message) {
    message = responseJSON.message;
  }
  chipEl
    .removeClass("memberAddStagedChipAdded")
    .addClass("memberAddStagedChipFailed");
  setChipStatusIcon(chipEl, STATUS_ICON_FAILED);
  if (message) chipEl.attr("title", message);
  return message;
}

/** Existing redirect path for a fatal (non-400) failure — mirrors submitStagedTagsFail. */
function redirectOnFatalFailure(xhr: JQuery.jqXHR): void {
  if (
    !("responseJSON" in xhr) &&
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    $("body").html(xhr.responseText);
    return;
  }
  window.location.assign(APP_CONFIG.routes.errorPage);
}
