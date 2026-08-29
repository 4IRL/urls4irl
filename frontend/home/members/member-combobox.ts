import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { emit } from "../../lib/metrics-client.js";
import { clearOpenForm, setOpenForm } from "../../lib/modal-tracking.js";
import { enableTabbableChildElements } from "../../lib/jquery-plugins.js";
import { getState, setState } from "../../store/app-store.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
} from "../../types/metrics-dim-values.js";
import {
  filterCoMemberSuggestions,
  hasExactCoMemberMatch,
} from "./member-combobox-state.js";
import { loadCoMemberCandidates } from "./co-member-fetch.js";
import { submitStagedMembers } from "./member-combobox-submit.js";
import { closeMemberNameFilter } from "./search.js";
import { isMobile } from "../mobile.js";

import type { MemberCandidate } from "../../types/member.js";

// The two closed-set `source` dimension values a staged chip can POST with
// (Step 6). A co-member pick stages "search_result"; the outsider fallback row
// stages "exact_username". Mirrors the backend MEMBER_ADD_SOURCE_VALUES.
export type MemberChipSource = "search_result" | "exact_username";

// A staged chip: the username to POST (canonical for co-members, exact typed
// casing for outsiders) plus which `source` dim it carries into Step 6's batch.
export type StagedMemberChip = {
  username: string;
  source: MemberChipSource;
};

// Closure keys exposed on the wrap via `wrap.data(...)` so the outer lifecycle
// (which only has the wrap DOM, not the closure `refs`) can read/clear the
// staged state and force a re-render — mirrors the tag combobox's STAGED_*_KEY.
export const STAGED_GET_KEY = "memberAddComboboxGetStaged";
export const STAGED_RESET_KEY = "memberAddComboboxResetStaged";
// Removes specific staged chips from the backing state array by username
// (case-sensitive). Step 6's batch submit calls this to drop only the succeeded
// chips after the batch settles, leaving failed chips staged for retry.
export const STAGED_REMOVE_KEY = "memberAddComboboxRemoveStaged";
export const RENDER_KEY = "memberAddComboboxRender";

const MEMBER_FILTER_DEBOUNCE_MS = 200;
const MEMBER_OPTION_ID_PREFIX = "memberAddOption";

let memberComboboxIdCounter = 0;

type MemberComboboxRefs = {
  utubID: number;
  wrap: JQuery;
  combobox: JQuery;
  input: JQuery;
  listbox: JQuery;
  message: JQuery;
  submitBtn: JQuery;
  listboxId: string;
  stagedChips: StagedMemberChip[];
  debounceTimer: ReturnType<typeof setTimeout> | null;
  // True while a batch submit is in flight — guards BOTH the button-click and
  // Enter-key submit paths against a double-submit (the button's disabled prop
  // alone would not stop the Enter path).
  submitting: boolean;
};

/**
 * DOM-only builder for the add-member combobox. Returns the
 * `.memberAddComboboxWrap` node **hidden**; no focus, no lifecycle side effects.
 * Every element also carries its `.urlTag*` counterpart class so the tag
 * combobox's styling shell (tags.css) applies verbatim. The open-time lifecycle
 * lives in `showMemberCombobox`.
 */
export function createMemberComboboxBlock(utubID: number): JQuery<HTMLElement> {
  const listboxId = `${MEMBER_OPTION_ID_PREFIX}Listbox-${++memberComboboxIdCounter}`;
  const inputId = `${listboxId}-input`;

  const wrap = $(document.createElement("div")).addClass(
    "memberAddComboboxWrap urlTagComboboxWrap hidden flex-column gap-5p",
  );

  // One accessible name: a visible <label for=…> ("Add member"), no competing
  // aria-label on the input (a <label for=> wins over aria-label for SR).
  const label = $(document.createElement("label"))
    .addClass("memberAddComboboxLabel urlTagComboboxLabel")
    .attr({ for: inputId })
    .text(APP_CONFIG.strings.MEMBER_ADD_LABEL);

  const combobox = $(document.createElement("div")).addClass(
    "memberAddCombobox urlTagCombobox flex-row flex-start",
  );

  const input = $(document.createElement("input"))
    .addClass("memberAddComboboxInput urlTagComboboxInput")
    .attr({
      type: "text",
      id: inputId,
      role: "combobox",
      "aria-expanded": "false",
      "aria-controls": listboxId,
      "aria-autocomplete": "list",
      placeholder: APP_CONFIG.strings.MEMBER_ADD_PLACEHOLDER,
    })
    // 16px prevents iOS Safari from zooming when the input gains focus.
    .css("font-size", "16px");

  combobox.append(input);

  const listbox = $(document.createElement("div"))
    .addClass("memberAddListbox urlTagListbox hidden")
    .attr({ role: "listbox", id: listboxId });

  // The combobox's OWN aria-live status region (distinct from the member
  // filter's #MemberSearchAnnouncement). Step 6 writes per-chip transition text
  // here after the batch settles.
  const message = $(document.createElement("div"))
    .addClass("memberAddComboboxMsg urlTagComboboxMsg")
    .attr({ "aria-live": "polite", "aria-atomic": "true" });

  // The "Add N" batch-submit control. Built here but its click is wired in
  // Step 6 (member-combobox-submit.ts); it stays disabled until ≥1 chip stages.
  const submitBtn = $(document.createElement("button"))
    .addClass("memberAddComboboxSubmitBtn urlTagComboboxSubmitBtn")
    .attr({ type: "button" })
    .prop("disabled", true)
    .text(APP_CONFIG.strings.MEMBER_ADD_SUBMIT);

  const actions = $(document.createElement("div")).addClass(
    "memberAddComboboxActions urlTagComboboxActions flex-row gap-5p",
  );
  actions.append(submitBtn);

  const footer = $(document.createElement("div"))
    .addClass("memberAddComboboxFooter urlTagComboboxFooter")
    .append(message)
    .append(actions);

  wrap.append(label).append(combobox).append(listbox).append(footer);

  const refs: MemberComboboxRefs = {
    utubID,
    wrap,
    combobox,
    input,
    listbox,
    message,
    submitBtn,
    listboxId,
    stagedChips: [],
    debounceTimer: null,
    submitting: false,
  };

  // Defensive copies so callers cannot mutate the backing array.
  wrap.data(STAGED_GET_KEY, () =>
    refs.stagedChips.map((chip) => ({ ...chip })),
  );
  wrap.data(STAGED_RESET_KEY, () => {
    if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
    refs.debounceTimer = null;
    refs.stagedChips = [];
  });
  wrap.data(STAGED_REMOVE_KEY, (usernames: string[]) => {
    const drop = new Set(usernames);
    refs.stagedChips = refs.stagedChips.filter(
      (chip) => !drop.has(chip.username),
    );
  });
  wrap.data(RENDER_KEY, () => renderMemberListbox(refs));

  bindMemberComboboxBehavior(refs);

  return wrap;
}

/**
 * Wires focus/blur, the 200ms-debounced input, and keydown handlers to the
 * combobox. The batch-submit button's click is intentionally NOT wired here —
 * Step 6 (member-combobox-submit.ts) owns that.
 */
function bindMemberComboboxBehavior(refs: MemberComboboxRefs): void {
  const { input, combobox, submitBtn } = refs;

  input.on("focus.memberAddCombobox", () => combobox.addClass("focused"));
  input.on("blur.memberAddCombobox", () => {
    combobox.removeClass("focused");
    if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
  });

  input.on("input.memberAddCombobox", () => {
    if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
    refs.debounceTimer = setTimeout(() => {
      renderMemberListbox(refs);
    }, MEMBER_FILTER_DEBOUNCE_MS);
  });

  input.on("keydown.memberAddCombobox", (keydownEvent: JQuery.TriggeredEvent) =>
    handleInputKeydown(refs, keydownEvent),
  );

  // Wire the "Add N" batch submit (built disabled in createMemberComboboxBlock).
  submitBtn.on("click.memberAddCombobox", () =>
    triggerBatchSubmit(refs, FORM_SUBMIT_TRIGGER.BUTTON_CLICK),
  );
}

/**
 * Fires the per-chip batch add for the currently-staged chips. A no-op when
 * nothing is staged. Emits the form-submit metric (per the form-abandonment
 * metric) before delegating to member-combobox-submit.ts, which owns the N
 * independent POSTs + async per-chip feedback.
 */
function triggerBatchSubmit(
  refs: MemberComboboxRefs,
  trigger: (typeof FORM_SUBMIT_TRIGGER)[keyof typeof FORM_SUBMIT_TRIGGER],
): void {
  // In-flight guard covers both the button click and the Enter-key path; staged
  // chips are not cleared until the batch settles, so without this a second
  // Enter would re-fire the same POSTs.
  if (refs.submitting) return;
  if (refs.stagedChips.length === 0) return;
  emit({
    event: UI_EVENTS.UI_FORM_SUBMIT,
    form: HOME_FORM.MEMBER_INVITE,
    trigger,
  });
  refs.submitting = true;
  void submitStagedMembers({ utubID: refs.utubID, wrap: refs.wrap }).finally(
    () => {
      refs.submitting = false;
    },
  );
}

function getActiveOption(refs: MemberComboboxRefs): JQuery {
  const activeId = refs.input.attr("aria-activedescendant");
  if (!activeId) return $();
  return refs.listbox.find(`#${activeId}`);
}

/**
 * Rebuilds the listbox: the loading hint (until the fetch settles), the
 * co-member suggestion rows (each with a mint role diamond + "shares N UTubs"
 * count pill), the dashed-amber outsider fallback row, and the empty-state /
 * already-a-member hint rows.
 */
function renderMemberListbox(refs: MemberComboboxRefs): void {
  const { input, listbox } = refs;
  const query = (input.val() as string) ?? "";
  const trimmedQuery = query.trim();

  listbox.empty();
  input.removeAttr("aria-activedescendant");

  // Fetch not settled yet: show only a neutral loading hint (no suggestions,
  // no outsider row) so "haven't loaded" is visibly distinct from "loaded and
  // empty".
  if (!getState().coMemberCandidatesLoaded) {
    listbox.append(buildHintRow(APP_CONFIG.strings.MEMBER_ADD_LOADING_HINT));
    listbox.removeClass("hidden");
    input.attr("aria-expanded", "true");
    updateMemberSubmitState(refs);
    return;
  }

  const currentMemberUsernames = getState().members.map(
    (member) => member.username,
  );
  const stagedUsernames = refs.stagedChips.map((chip) => chip.username);
  const suggestions = filterCoMemberSuggestions({
    query: trimmedQuery,
    currentMemberUsernames,
    stagedUsernames,
  });

  let optionIndex = 0;
  suggestions.forEach((candidate) => {
    listbox.append(buildMemberSuggestionOption(refs, candidate, optionIndex++));
  });

  // The outsider fallback is offered when the typed text matches no co-member
  // exactly (case-sensitive) AND is not already a current member — that second
  // guard suppresses the dead-end row whose exact-username add would 400 with
  // MEMBER_ALREADY_IN_UTUB (hasExactCoMemberMatch only checks candidates).
  const matchesCurrentMember = getState().members.some(
    (member) => member.username === trimmedQuery,
  );
  const hasExactCandidate = hasExactCoMemberMatch({ query: trimmedQuery });
  // Suppress the outsider row when the exact typed username is already staged as
  // an outsider chip: re-typing it would otherwise show a clickable row whose add
  // silently no-ops (stageMemberUsername dedupes case-sensitively). Mirrors the
  // staged-username exclusion filterCoMemberSuggestions already applies.
  const matchesStagedChip = refs.stagedChips.some(
    (chip) => chip.username === trimmedQuery,
  );
  const showOutsider =
    trimmedQuery.length >= 1 &&
    !hasExactCandidate &&
    !matchesCurrentMember &&
    !matchesStagedChip;

  if (showOutsider) {
    listbox.append(buildOutsiderOption(refs, trimmedQuery, optionIndex++));
  } else if (
    trimmedQuery.length >= 1 &&
    matchesCurrentMember &&
    !hasExactCandidate
  ) {
    // Outsider suppressed specifically because the typed text case-sensitively
    // matches an existing current member — explain why for this keystroke.
    listbox.append(
      buildHintRow(
        // Callback replacement so `$`-sequences in the typed text are inserted
        // literally, not interpreted as replacement patterns.
        APP_CONFIG.strings.MEMBER_ADD_ALREADY_MEMBER_HINT.replace(
          "{{ username }}",
          () => trimmedQuery,
        ),
      ),
    );
  }

  // Loaded successfully but the requester has zero co-members: prompt them to
  // type a username (the outsider path still works once they do).
  const hasCoMembers = getState().coMemberCandidates.length > 0;
  if (!hasCoMembers && trimmedQuery.length === 0) {
    listbox.append(
      buildHintRow(APP_CONFIG.strings.MEMBER_ADD_NO_COMEMBERS_HINT),
    );
    listbox.removeClass("hidden");
    input.attr("aria-expanded", "true");
    updateMemberSubmitState(refs);
    return;
  }

  const hasRows = listbox.children().length > 0;
  listbox.toggleClass("hidden", !hasRows);
  input.attr("aria-expanded", hasRows ? "true" : "false");

  if (hasRows) {
    // Auto-activate only the outsider action row (never an arbitrary
    // suggestion), mirroring the tag combobox's auto-activated create-new row.
    const outsiderOption = listbox.find(".memberAddOptionOutsider");
    if (outsiderOption.length > 0) {
      activateOption(refs, outsiderOption);
    }
  }

  updateMemberSubmitState(refs);
}

function buildMemberSuggestionOption(
  refs: MemberComboboxRefs,
  candidate: MemberCandidate,
  index: number,
): JQuery {
  const optionId = `${refs.listboxId}-opt-${index}`;
  const option = $(document.createElement("div"))
    .addClass("memberAddOption urlTagOption")
    .attr({ role: "option", id: optionId, "aria-selected": "false" })
    .data("memberUsername", candidate.username)
    .data("memberSource", "search_result");

  const roleDiamond = $(document.createElement("span"))
    .addClass("memberAddOptionRole")
    .attr({ "aria-hidden": "true" })
    .text("◆");
  const labelSpan = $(document.createElement("span"))
    .addClass("memberAddOptionLabel urlTagOptionLabel")
    .text(candidate.username);
  const main = $(document.createElement("span"))
    .addClass("memberAddOptionMain flex-row align-center gap-5p")
    .append(roleDiamond)
    .append(labelSpan);

  const sharedCount = candidate.sharedUtubCount;
  const countText =
    sharedCount === 1
      ? APP_CONFIG.strings.MEMBER_ADD_SHARES_COUNT_ONE
      : APP_CONFIG.strings.MEMBER_ADD_SHARES_COUNT.replace(
          "{n}",
          String(sharedCount),
        );
  const countPill = $(document.createElement("span"))
    .addClass("memberAddOptionCount urlTagOptionCount")
    .text(countText);

  option.append(main).append(countPill);
  option.on("click.memberAddCombobox", () =>
    stageMemberUsername({
      refs,
      username: candidate.username,
      source: "search_result",
    }),
  );
  return option;
}

function buildOutsiderOption(
  refs: MemberComboboxRefs,
  query: string,
  index: number,
): JQuery {
  const optionId = `${refs.listboxId}-opt-${index}`;
  const option = $(document.createElement("div"))
    .addClass("memberAddOption memberAddOptionOutsider urlTagOption")
    .attr({ role: "option", id: optionId, "aria-selected": "false" })
    .data("memberUsername", query)
    .data("memberSource", "exact_username");

  option.append(
    $(document.createElement("span"))
      .addClass("memberAddOptionIcon urlTagOptionCreateIcon")
      .attr({ "aria-hidden": "true" })
      .text("+"),
  );
  option.append(
    $(document.createElement("span"))
      .addClass("memberAddOptionLabel urlTagOptionLabel")
      .text(
        // Callback replacement so `$`-sequences in the typed text are inserted
        // literally, not interpreted as replacement patterns.
        APP_CONFIG.strings.MEMBER_ADD_OUTSIDER_LABEL.replace(
          "{{ username }}",
          () => query,
        ),
      ),
  );

  option.on("click.memberAddCombobox", () =>
    stageMemberUsername({ refs, username: query, source: "exact_username" }),
  );
  return option;
}

function buildHintRow(text: string): JQuery {
  return $(document.createElement("div"))
    .addClass("memberAddListboxHint urlTagListboxHint")
    .attr({ role: "presentation" })
    .text(text);
}

function activateOption(refs: MemberComboboxRefs, option: JQuery): void {
  refs.listbox
    .find(".memberAddOption")
    .removeClass("active")
    .attr("aria-selected", "false");
  if (option.length === 0) {
    refs.input.removeAttr("aria-activedescendant");
    return;
  }
  option.addClass("active").attr("aria-selected", "true");
  refs.input.attr("aria-activedescendant", option.attr("id") as string);
}

function moveActiveOption(refs: MemberComboboxRefs, direction: 1 | -1): void {
  const options = refs.listbox.find(".memberAddOption");
  if (options.length === 0) return;

  const active = getActiveOption(refs);
  let nextIndex: number;
  if (active.length === 0) {
    nextIndex = direction === 1 ? 0 : options.length - 1;
  } else {
    const currentIndex = options.index(active);
    nextIndex = (currentIndex + direction + options.length) % options.length;
  }
  activateOption(refs, options.eq(nextIndex));
}

/**
 * Stages a username as a chip. A co-member pick passes the candidate's
 * canonical username; the outsider row passes the exact typed casing. De-dupes
 * **case-sensitively** (usernames are case-sensitive on the backend) and never
 * stages anyone already a current member.
 */
function stageMemberUsername({
  refs,
  username,
  source,
}: {
  refs: MemberComboboxRefs;
  username: string;
  source: MemberChipSource;
}): void {
  const trimmed = username.trim();
  if (trimmed.length === 0) return;
  if (getState().members.some((member) => member.username === trimmed)) return;
  if (refs.stagedChips.some((chip) => chip.username === trimmed)) return;

  const chip: StagedMemberChip = { username: trimmed, source };
  refs.stagedChips.push(chip);
  refs.combobox
    .find(".memberAddComboboxInput")
    .before(buildMemberStagedChip(refs, chip));

  refs.input.val("");
  renderMemberListbox(refs);
}

function buildMemberStagedChip(
  refs: MemberComboboxRefs,
  chip: StagedMemberChip,
): JQuery {
  const isOutsider = chip.source === "exact_username";
  const chipEl = $(document.createElement("span"))
    .addClass("memberAddStagedChip urlTagStagedChip flex-row align-center")
    .attr({
      "data-staged-username": chip.username,
      "data-staged-source": chip.source,
    });
  if (isOutsider) chipEl.addClass("memberAddStagedChipOutsider");

  chipEl.append(
    $(document.createElement("span"))
      .addClass("memberAddStagedChipText urlTagStagedChipText")
      .text(chip.username),
  );

  // Outsider chips carry a "NEW" marker (mock State 2) alongside the amber skin.
  if (isOutsider) {
    chipEl.append(
      $(document.createElement("span"))
        .addClass("memberAddStagedChipNew")
        .text("NEW"),
    );
  }

  // Per-chip async-feedback slots for Step 6's batch submit, both empty/inert at
  // rest: a delayed loading-ring placeholder (gets `.dual-loading-ring` while
  // that chip's POST is in flight) and a status marker that becomes a green
  // check-circle icon on success or a red warning-triangle icon on failure (a
  // warning, NOT an ✗, so it never reads as the `×` remove button beside it). The
  // failure *reason* is not rendered beside the chip (it overflowed off-screen);
  // it is carried by the chip's `title` tooltip and the batched summary line under
  // the strip instead.
  chipEl.append(
    $(document.createElement("span"))
      .addClass("memberAddStagedChipRing")
      .attr({ "aria-hidden": "true" }),
  );
  chipEl.append(
    $(document.createElement("span"))
      .addClass("memberAddStagedChipStatus")
      .attr({ "aria-hidden": "true" }),
  );

  const removeButton = $(document.createElement("button"))
    .addClass(
      "memberAddStagedChipRemove urlTagStagedChipRemove flex-row align-center pointerable tabbable",
    )
    .attr({ type: "button", "aria-label": `Remove member ${chip.username}` })
    .text("×");
  removeButton.on("click.memberAddCombobox", () =>
    removeMemberStagedChip(refs, chipEl, chip.username),
  );

  chipEl.append(removeButton);
  return chipEl;
}

/**
 * Removes a staged chip and its backing state, returning focus to the input
 * (WCAG 2.4.3 focus order).
 */
function removeMemberStagedChip(
  refs: MemberComboboxRefs,
  chip: JQuery,
  username: string,
): void {
  refs.stagedChips = refs.stagedChips.filter(
    (staged) => staged.username !== username,
  );
  chip.remove();
  renderMemberListbox(refs);
  refs.input.trigger("focus");
}

/**
 * Enables the "Add N" submit when ≥1 chip is staged and relabels it with the
 * staged count (mock: "Add 1" / "Add 2"); reverts to the disabled base "Add"
 * label at zero staged.
 */
function updateMemberSubmitState(refs: MemberComboboxRefs): void {
  const count = refs.stagedChips.length;
  refs.submitBtn.prop("disabled", count === 0);
  refs.submitBtn.text(
    count === 0
      ? APP_CONFIG.strings.MEMBER_ADD_SUBMIT
      : APP_CONFIG.strings.MEMBER_ADD_SUBMIT_COUNT.replace(
          "{n}",
          String(count),
        ),
  );
}

function closeDropdown(refs: MemberComboboxRefs): void {
  if (refs.debounceTimer) clearTimeout(refs.debounceTimer);
  refs.debounceTimer = null;
  refs.listbox.empty().addClass("hidden");
  refs.input.attr("aria-expanded", "false").removeAttr("aria-activedescendant");
}

/**
 * Keydown dispatch for the combobox input. All handlers bound to `keydown`
 * (never `keyup`) so ESC is not subject to a stale-event race and the combobox
 * beats deck-level listeners.
 */
function handleInputKeydown(
  refs: MemberComboboxRefs,
  keydownEvent: JQuery.TriggeredEvent,
): void {
  const query = ((refs.input.val() as string) ?? "").trim();
  const activeOption = getActiveOption(refs);

  switch (keydownEvent.key) {
    case KEYS.ARROW_DOWN:
      keydownEvent.preventDefault();
      moveActiveOption(refs, 1);
      break;
    case KEYS.ARROW_UP:
      keydownEvent.preventDefault();
      moveActiveOption(refs, -1);
      break;
    case KEYS.ENTER: {
      keydownEvent.preventDefault();
      const canSubmit =
        query.length === 0 &&
        refs.stagedChips.length > 0 &&
        activeOption.length === 0;
      if (canSubmit) {
        // Enter with only staged chips (empty input, no active option) fires the
        // "Add N" batch submit — Step 6.
        triggerBatchSubmit(refs, FORM_SUBMIT_TRIGGER.ENTER_KEY);
        break;
      }
      stageActiveOrQuery(refs, query, activeOption);
      break;
    }
    case KEYS.TAB:
      if (activeOption.length > 0) {
        keydownEvent.preventDefault();
        stageActiveOrQuery(refs, query, activeOption);
      }
      break;
    case KEYS.BACKSPACE:
      if (query.length === 0 && refs.stagedChips.length > 0) {
        keydownEvent.preventDefault();
        const lastChip = refs.combobox.find(".memberAddStagedChip").last();
        const lastUsername = lastChip.attr("data-staged-username") as string;
        removeMemberStagedChip(refs, lastChip, lastUsername);
      }
      break;
    case KEYS.ESCAPE:
      if (!refs.listbox.hasClass("hidden")) {
        // First Escape: close only the dropdown; do not bubble to the deck /
        // removal modal.
        keydownEvent.stopPropagation();
        keydownEvent.preventDefault();
        closeDropdown(refs);
      } else {
        // Second Escape (dropdown already closed): cancel the whole combobox and
        // return focus to the opener button.
        cancelMemberCombobox(FORM_CANCEL_TRIGGER.ESCAPE_KEY);
        $("#memberBtnCreate").trigger("focus");
      }
      break;
    default:
    /* no-op */
  }
}

function stageActiveOrQuery(
  refs: MemberComboboxRefs,
  query: string,
  activeOption: JQuery,
): void {
  if (activeOption.length > 0) {
    stageMemberUsername({
      refs,
      username: activeOption.data("memberUsername") as string,
      source: activeOption.data("memberSource") as MemberChipSource,
    });
  } else if (query.length > 0) {
    // No active option: treat the typed text as an exact-username (outsider)
    // stage — the exact typed casing is POSTed with source="exact_username".
    stageMemberUsername({ refs, username: query, source: "exact_username" });
  }
}

/**
 * Suppress the deck's OTHER member controls while the add-member combobox is open
 * (which is also the only state in which chips can be staged) — the per-row
 * `.memberOtherBtnDelete` remove buttons and the name-filter funnel — so opening
 * a removal modal can't strand staged/in-flight combobox state and the filter
 * can't fight the combobox for the deck's search-row real estate. Same intent as
 * the tag combobox suppressing the URL card's sibling controls while tags are
 * staged, but here the controls are DISABLED (kept visible-but-inert) rather than
 * hidden, so the deck layout doesn't shift while the combobox is open.
 * The `.member-add-open` state class on #MemberDeck ALSO gates any remove buttons
 * on badges appended by a successful batch add while the combobox stays open
 * (Step 6's stay-open flow) via CSS — `reapplyMemberDeckSiblingControlSuppression`
 * re-disables those freshly-appended buttons for tab-order/keyboard too.
 */
function disableMemberDeckSiblingControls(): void {
  $("#MemberDeck").addClass("member-add-open");
  $("#memberNameFilterBtn")
    .prop("disabled", true)
    .attr("aria-disabled", "true");
  $(".memberOtherBtnDelete")
    .prop("disabled", true)
    .attr("aria-disabled", "true");
}

/**
 * Re-applies the sibling-control suppression to controls added AFTER the combobox
 * opened — specifically the `.memberOtherBtnDelete` remove buttons on member
 * badges appended by a successful batch add while the combobox is still open. A
 * no-op unless the combobox is currently open (the `.member-add-open` gate).
 */
export function reapplyMemberDeckSiblingControlSuppression(): void {
  if ($("#MemberDeck").hasClass("member-add-open")) {
    disableMemberDeckSiblingControls();
  }
}

/** Re-enable the deck's per-row remove buttons + filter funnel. Idempotent. */
function enableMemberDeckSiblingControls(): void {
  $("#MemberDeck").removeClass("member-add-open");
  $("#memberNameFilterBtn").prop("disabled", false).removeAttr("aria-disabled");
  $(".memberOtherBtnDelete")
    .prop("disabled", false)
    .removeAttr("aria-disabled");
}

/**
 * Rebuilds the plus-square opener icon for #memberBtnCreate (restored on close
 * when reverting from the in-place close affordance).
 */
function createAddMemberIcon(): JQuery {
  return $(
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" ' +
      'class="bi bi-plus-square-fill" width="30" height="30" viewBox="0 0 16 16">' +
      '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm6.5 4.5v3h3a.5.5 0 0 1 0 1h-3v3a.5.5 0 0 1-1 0v-3h-3a.5.5 0 0 1 0-1h3v-3a.5.5 0 0 1 1 0"/>' +
      "</svg>",
  );
}

/**
 * The in-place close (cancel) icon that #memberBtnCreate shows while the combobox
 * is open: the app's shared `bi-x-square-fill` cancel glyph (red via `.cancelButton`,
 * same as Create UTub / Create Tag / Update-name+desc). Replaces the previous
 * text "Cancel" — an X reads as "close" regardless of whether members were already
 * added (the stay-open flow), and matches the form-cancel pattern used elsewhere.
 */
function createCloseMemberIcon(): JQuery {
  return $(
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" ' +
      'class="bi bi-x-square-fill cancelButton" width="30" height="30" viewBox="0 0 16 16">' +
      '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/>' +
      "</svg>",
  );
}

/**
 * Open-time lifecycle. Resets the loaded flag, force-closes the member filter
 * (mutual exclusion), sets the open-form token, emits the invite-open metric,
 * mounts a freshly-built combobox into #createMemberWrap, transforms
 * #memberBtnCreate into an in-place Cancel button (never hidden), kicks off the
 * co-member fetch, and focuses the input (isMobile()-branched).
 */
export function showMemberCombobox(utubID: number): void {
  setState({ coMemberCandidatesLoaded: false });
  closeMemberNameFilter();
  setOpenForm(HOME_FORM.MEMBER_INVITE);
  emit({ event: UI_EVENTS.UI_MEMBER_INVITE_OPEN });

  const wrap = createMemberComboboxBlock(utubID);
  const createMemberWrap = $("#createMemberWrap");
  createMemberWrap.empty().append(wrap);
  enableTabbableChildElements(wrap);
  wrap.removeClass("hidden");
  createMemberWrap.showClassFlex();
  $("#displayMemberWrap").hideClass();

  // Suppress the deck's other member controls (per-row remove buttons + the
  // filter funnel) while the combobox is open, so a removal modal can't strand
  // staged state and the filter can't fight the combobox for the search row.
  disableMemberDeckSiblingControls();

  // Show the loading hint immediately; it is swapped for real content when the
  // fetch settles (via the onSettle callback below) or on the next keystroke.
  const render = wrap.data(RENDER_KEY) as (() => void) | undefined;
  if (render) render();

  // #memberBtnCreate transforms in place into the shared close (cancel) X — never
  // hidden; the green "+" opener becomes the red `bi-x-square-fill` close glyph, a
  // clean +/× toggle that matches the form-cancel pattern used elsewhere and reads
  // as "close" even after members were added (stay-open flow). aria-label keeps the
  // accessible action name (WCAG 4.1.2).
  $("#memberBtnCreate")
    .removeClass("green-clickable")
    .empty()
    .append(createCloseMemberIcon())
    .attr("aria-label", "Cancel adding members")
    .offAndOnExact("click", () =>
      cancelMemberCombobox(FORM_CANCEL_TRIGGER.CANCEL_BUTTON),
    );

  // Rely on loadCoMemberCandidates's own abort-and-replace guard (Step 4) for
  // staleness across rapid reopen / UTub switch. Re-render on settle so the
  // loading hint self-corrects, but only if this combobox is still mounted (a
  // cancel / UTub switch may have torn it down before the fetch resolved).
  loadCoMemberCandidates(utubID, () => {
    if (render && wrap.parent().length > 0) render();
  });

  if (isMobile()) {
    wrap.find(".memberAddComboboxInput").trigger("focus");
  } else {
    setTimeout(() => {
      wrap.find(".memberAddComboboxInput").trigger("focus");
    }, 100);
  }
}

/**
 * User-initiated cancel of the add-member combobox (Cancel button / second
 * Escape). Emits the form-abandonment metric (per the design doc) BEFORE tearing
 * down — kept distinct from `hideAndResetMemberCombobox`, which also runs on the
 * non-user teardown path (`resetMemberDeck` on a UTub switch) where no cancel
 * metric should fire.
 */
function cancelMemberCombobox(
  trigger: (typeof FORM_CANCEL_TRIGGER)[keyof typeof FORM_CANCEL_TRIGGER],
): void {
  emit({
    event: UI_EVENTS.UI_FORM_CANCEL,
    form: HOME_FORM.MEMBER_INVITE,
    trigger,
  });
  hideAndResetMemberCombobox();
}

/**
 * Close + reset lifecycle. Tears down the mounted combobox (staged chips +
 * timer + DOM), reverts #memberBtnCreate to the plus opener, restores the member
 * display (owner-gated), clears the co-member store slice + loaded flag, and
 * clears the open-form token. Also invoked from `resetMemberDeck` on every UTub
 * switch / no-UTub path, so it must be a safe no-op when nothing is open.
 */
export function hideAndResetMemberCombobox(): void {
  const createMemberWrap = $("#createMemberWrap");
  const wrap = createMemberWrap.find(".memberAddComboboxWrap");
  const wasOpen = wrap.length > 0;

  if (wasOpen) {
    const resetStaged = wrap.data(STAGED_RESET_KEY) as (() => void) | undefined;
    if (resetStaged) resetStaged();
  }
  createMemberWrap.empty().hideClass();

  // Re-enable the deck's per-row remove buttons + filter funnel now the combobox
  // is closed (idempotent — safe even when nothing was open).
  enableMemberDeckSiblingControls();

  // Revert #memberBtnCreate from its close-X state back to the green plus opener.
  const memberBtnCreate = $("#memberBtnCreate");
  memberBtnCreate
    .addClass("green-clickable")
    .empty()
    .attr("aria-label", APP_CONFIG.strings.MEMBER_ADD_LABEL)
    .append(createAddMemberIcon());

  // Restore the display + opener only when a UTub is actually selected — mirrors
  // the old createMemberHideInput guard so the no-UTub cleanup path does not
  // re-show the add button after the deck was reset.
  const activeUTubID = getState().activeUTubID;
  if (activeUTubID !== null) {
    memberBtnCreate.offAndOnExact("click", () =>
      showMemberCombobox(activeUTubID),
    );
    $("#displayMemberWrap").showClassFlex();
    // The UTub owner and co-owners may add members (DD-1).
    if (!(getState().isCurrentUserOwner || getState().isCoCreator)) {
      memberBtnCreate.hideClass();
    }
  }

  setState({ coMemberCandidates: [], coMemberCandidatesLoaded: false });
  if (wasOpen) clearOpenForm();
}

/**
 * Reverse mutual-exclusion handler: when the member name-filter opens, tear down
 * an OPEN add-member combobox so the two #MemberDeck "search" inputs never
 * co-occupy focus/state. Guarded to a cheap no-op when no combobox is open, so a
 * plain funnel click never needlessly clears the co-member candidate cache or
 * rebuilds the #memberBtnCreate opener.
 */
export function handleMemberFilterOpened(): void {
  if ($("#createMemberWrap").find(".memberAddComboboxWrap").length > 0) {
    hideAndResetMemberCombobox();
  }
}

// The filter (search.ts) emits MEMBER_FILTER_OPENED via the event bus rather than
// importing this module, keeping the filter decoupled from this module's (heavy)
// graph. This module-load registration is live before the funnel is interactive
// because members/deck.ts imports member-combobox.ts as part of the home shell.
on(AppEvents.MEMBER_FILTER_OPENED, handleMemberFilterOpened);
