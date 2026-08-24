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
  // Present only for a 400: the inline error text shown beside the chip, reused
  // in the batched aria-live summary.
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
 * never flicker. Real-time per-chip visual feedback (ring / ✓ / inline error)
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

      // 400 → inline error beside this chip (siblings unaffected). Anything else
      // (403 HTML / unknown) → the existing redirect path.
      const errorText = renderChipInlineError(chipEl, xhr);
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
 * failed chips with their inline error for retry, and refocuses the input.
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
    const addedMembers = fulfilled
      .map((result) => result.member)
      .filter((member): member is NonNullable<typeof member> =>
        Boolean(member),
      );
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
  // backing staged state); leave failed chips in place with their inline error
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
 * Joins the per-chip outcomes into a single summary message (e.g.
 * "alice added, bob failed: user does not exist"). 429-skipped chips are
 * excluded — their global 429 UI already communicated the outcome.
 */
function buildSummaryMessage(results: ChipSettleResult[]): string {
  return results
    .filter((result) => result.outcome !== "skipped_429")
    .map((result) => {
      if (result.outcome === "fulfilled") {
        return APP_CONFIG.strings.MEMBER_ADD_STATUS_ADDED.replace(
          "{{ username }}",
          () => result.chip.username,
        );
      }
      return APP_CONFIG.strings.MEMBER_ADD_STATUS_FAILED.replace(
        "{{ username }}",
        () => result.chip.username,
      ).replace("{{ reason }}", () => result.errorText ?? "");
    })
    .join(", ");
}

/** Locates a staged chip's DOM element by its (unique, case-sensitive) username. */
function findChipElement(wrap: JQuery, username: string): JQuery {
  return wrap
    .find(".memberAddStagedChip")
    .filter(
      (_index, element) => $(element).attr("data-staged-username") === username,
    );
}

/** Marks a chip added: ✓ status, cleared inline error, success skin. */
function markChipAdded(chipEl: JQuery): void {
  chipEl.addClass("memberAddStagedChipAdded");
  chipEl.find(".memberAddStagedChipStatus").text("✓");
  chipEl.find(".memberAddStagedChipError").text("").addClass("hidden");
}

/**
 * Renders a chip's inline 400 error beside it and returns the message text.
 * Returns `null` for any non-400 (403 HTML / unknown) so the caller redirects.
 * USER_NOT_EXIST arrives as `errors.username`; MEMBER_ALREADY_IN_UTUB as
 * `message`.
 */
function renderChipInlineError(
  chipEl: JQuery,
  xhr: JQuery.jqXHR,
): string | null {
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
  chipEl.addClass("memberAddStagedChipFailed");
  chipEl.find(".memberAddStagedChipError").text(message).removeClass("hidden");
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
