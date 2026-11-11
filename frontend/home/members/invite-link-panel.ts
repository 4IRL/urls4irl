import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { fillTemplate } from "../../lib/string-template.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { INVITE_LINK_COPY_RESULT } from "../../types/metrics-dim-values.js";
import { AppEvents, emit as emitAppEvent } from "../../lib/event-bus.js";
import { getState, subscribe, type AppState } from "../../store/app-store.js";
import { canManageInviteLink } from "../utubs/policy.js";
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import { withMemberControlFocusFallback } from "./focus-fallback.js";
import { hideAndResetMemberCombobox } from "./member-combobox.js";
import { announceMemberRowAction } from "./notice.js";
import { closeMemberNameFilter } from "./search.js";
import {
  createInviteLink,
  getInviteLink,
  INVITE_LINK_DEAD_UPDATE_ERROR_CODE,
  INVITE_LINK_LIVE_EXISTS_ERROR_CODE,
  INVITE_LINK_LOCKED_ERROR_CODE,
  INVITE_LINK_NOT_FOUND_ERROR_CODE,
  INVITE_LINK_USES_BELOW_JOINED_ERROR_CODE,
  replaceExpiryDays,
  replaceInviteLink,
  revokeInviteLink,
  updateInviteLink,
  type InviteLink,
  type InviteLinkUpdateBody,
  type InviteLinkLoadFailure,
  type InviteLinkMutationFailure,
} from "./invite-link-client.js";

const log = debug("members");

const TRIGGER_SELECTOR = "#memberBtnInviteLink";
const MODAL_SELECTOR = "#inviteLinkModal";
const HEADING_SELECTOR = "#inviteLinkModalTitle";
const BODY_SELECTOR = "#inviteLinkModalBody";
const OVERFLOW_BUTTON_SELECTOR = "#memberBtnOverflow";
// Where focus returns when the modal closes, first focusable wins.
const FOCUS_RETURN_SELECTORS = [
  TRIGGER_SELECTOR,
  OVERFLOW_BUTTON_SELECTOR,
  "#MemberDeckHeaderAndCaret",
] as const;
const MEMBER_DECK_SELECTOR = "#MemberDeck";
const MOBILE_ANNOUNCEMENT_SELECTOR = "#MobilePanelAnnouncement";
const ANNOUNCEMENT_SELECTOR = "#MemberRowActionAnnouncement";

const RELEVANT_KEYS: ReadonlyArray<keyof AppState> = [
  "activeUTubID",
  "isCurrentUserOwner",
  "isCoCreator",
  "isCurrentUTubLocked",
];

const EXPIRY_DAY_CHOICES = [1, 7, 30] as const;
const DEFAULT_EXPIRY_DAYS = 7;
const USES_CHOICES = [null, 1, 5, 10, 25] as const;

type Politeness = "polite" | "assertive";

// The open session. `_generation` is the request generation token: every close,
// reset and forced close bumps it, so a response started before is dropped.
// `_openedUTubID` is written once on open and cleared on every close; its only
// reader is the forced-close announcement decision. `_forcedClosedToken` is the
// pre-bump generation of a forced close, so a late lifecycle success from that
// session stays silent; only `resetInviteLinkPanel` clears it.
let _generation = 0;
let _isOpen = false;
// The modal's fade has finished (`shown.bs.modal`); until then it cannot take focus.
let _shown = false;
// The close button was clicked: it closes even over an open confirm.
let _closeRequested = false;
let _state: PanelState = "loading";
let _openedUTubID: number | null = null;
let _forcedClosedToken: number | null = null;
// `_inFlight` (any request) drives the control lock; `_lifecycleInFlight` (only
// create / replace / revoke) drives Escape. Both are reset by `teardownPanel`.
let _inFlight = false;
let _lifecycleInFlight = false;
// The live link currently rendered (the New link body reads its settings), and
// the open confirm with the footer it replaced and the button that opened it.
let _liveLink: InviteLink | null = null;
let _confirm: {
  kind: "revoke" | "new";
  footerNodes: Node[];
  originId: string;
} | null = null;
// The settings save in flight: which select and the value being saved (the
// select shows it until the response replaces it). Null outside a save.
type SaveField = "expires" | "uses";
let _pending: { field: SaveField; value: string } | null = null;
let _copyRevertTimer: ReturnType<typeof setTimeout> | null = null;
const COPIED_LABEL_MS = 1500;

/** Whether the panel is open. */
export function isInviteLinkPanelOpen(): boolean {
  return _isOpen;
}

/** The generation token a mutation started now would carry. */
export function currentInviteLinkGeneration(): number {
  return _generation;
}

/** The generation of a forced close, or null (read by the lifecycle success announcement). */
export function getForcedClosedToken(): number | null {
  return _forcedClosedToken;
}

// Clears the region, then writes `message` on the next tick so an identical
// consecutive message is re-announced. The decision to announce is made by the
// caller before scheduling and the write is never cancelled, so an announcement
// made as the panel closes still lands. When the Members deck is not displayed
// (a mobile deck switch) the message also goes to the global mobile region.
export function announceInviteLinkPanel({
  message,
  politeness = "polite",
}: {
  message: string;
  politeness?: Politeness;
}): void {
  $(ANNOUNCEMENT_SELECTOR).text("");
  $(MOBILE_ANNOUNCEMENT_SELECTOR).text("");
  setTimeout(() => {
    announceMemberRowAction({ message, politeness });
    const deck = $(MEMBER_DECK_SELECTOR)[0];
    const deckDisplayed =
      deck !== undefined && window.getComputedStyle(deck).display !== "none";
    if (!deckDisplayed) $(MOBILE_ANNOUNCEMENT_SELECTOR).text(message);
  }, 0);
}

function formatShortDate(iso: string): string {
  const date = new Date(iso);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    ...(sameYear ? {} : { year: "numeric" }),
  });
}

function usesLabel({ count }: { count: number }): string {
  return count === 1
    ? APP_CONFIG.strings.INVITE_LINK_PANEL_USES_ONE
    : fillTemplate({
        template: APP_CONFIG.strings.INVITE_LINK_PANEL_USES_MANY,
        values: { count: String(count) },
      });
}

function inviteUrl({ token }: { token: string }): string {
  return `${window.location.origin}/invite/${token}`;
}

function expiryChoiceLabel({
  days,
  fromNow,
}: {
  days: (typeof EXPIRY_DAY_CHOICES)[number];
  fromNow: boolean;
}): string {
  const { strings } = APP_CONFIG;
  if (fromNow) {
    return days === 1
      ? strings.INVITE_LINK_PANEL_EXPIRES_FROM_NOW_1
      : days === 7
        ? strings.INVITE_LINK_PANEL_EXPIRES_FROM_NOW_7
        : strings.INVITE_LINK_PANEL_EXPIRES_FROM_NOW_30;
  }
  return days === 1
    ? strings.INVITE_LINK_PANEL_EXPIRES_IN_1
    : days === 7
      ? strings.INVITE_LINK_PANEL_EXPIRES_IN_7
      : strings.INVITE_LINK_PANEL_EXPIRES_IN_30;
}

function makeElement<Tag extends keyof HTMLElementTagNameMap>({
  tag,
  className,
  text,
  id,
}: {
  tag: Tag;
  className?: string;
  text?: string;
  id?: string;
}): HTMLElementTagNameMap[Tag] {
  const element = document.createElement(tag);
  if (className !== undefined) element.className = className;
  if (text !== undefined) element.textContent = text;
  if (id !== undefined) element.id = id;
  return element;
}

function makeButton({
  id,
  label,
  variant,
}: {
  id: string;
  label: string;
  variant: "primary" | "ghost" | "danger";
}): HTMLButtonElement {
  const button = makeElement({
    tag: "button",
    id,
    text: label,
    className: `invitePanelBtn invitePanelBtn--${variant}`,
  });
  button.type = "button";
  return button;
}

type SelectOption = {
  value: string;
  text: string;
  selected?: boolean;
  disabled?: boolean;
};

function fillSelectOptions({
  select,
  options,
}: {
  select: HTMLSelectElement;
  options: SelectOption[];
}): void {
  select.replaceChildren();
  for (const option of options) {
    const optionElement = makeElement({ tag: "option", text: option.text });
    optionElement.value = option.value;
    if (option.disabled === true) optionElement.disabled = true;
    select.append(optionElement);
    // Selectedness is set after the option is attached and only when true, so a
    // later option never resets the choice.
    if (option.selected === true) optionElement.selected = true;
  }
}

function makeSelectField({
  id,
  label,
  options,
}: {
  id: string;
  label: string;
  options: SelectOption[];
}): HTMLElement {
  const field = makeElement({ tag: "div", className: "invitePanelField" });
  const labelElement = makeElement({ tag: "label", text: label });
  labelElement.htmlFor = id;
  const select = makeElement({
    tag: "select",
    id,
    className: "panelSettingsSelect invitePanelSelect",
  });
  fillSelectOptions({ select, options });
  field.append(labelElement, select);
  return field;
}

function usesOptions({
  selected,
  floor,
}: {
  selected: number | null;
  floor: number;
}): Array<{
  value: string;
  text: string;
  selected: boolean;
  disabled: boolean;
}> {
  const choices: Array<number | null> = [...USES_CHOICES];
  if (selected !== null && !choices.includes(selected)) choices.push(selected);
  return choices.map((choice) => ({
    value: choice === null ? "" : String(choice),
    text:
      choice === null
        ? APP_CONFIG.strings.INVITE_LINK_PANEL_USES_UNLIMITED
        : usesLabel({ count: choice }),
    selected: choice === selected,
    disabled: choice !== null && choice < floor,
  }));
}

function creatorAndJoined({ link }: { link: InviteLink }): string {
  const { strings } = APP_CONFIG;
  const joined = fillTemplate({
    template: strings.INVITE_LINK_PANEL_META_JOINED,
    values: { count: String(link.useCount) },
  });
  if (link.creatorUsername === null) return joined;
  const created = fillTemplate({
    template: strings.INVITE_LINK_PANEL_META_CREATED_BY,
    values: { user: link.creatorUsername },
  });
  return `${created} · ${joined}`;
}

/** The reason line for a dead link. */
export function deadReasonFor({ link }: { link: InviteLink }): string {
  const { strings } = APP_CONFIG;
  switch (link.status) {
    case "expired":
      return fillTemplate({
        template: strings.INVITE_LINK_PANEL_DEAD_EXPIRED,
        values: { date: formatShortDate(link.expiresAt) },
      });
    case "used_up":
      return fillTemplate({
        template: strings.INVITE_LINK_PANEL_DEAD_USED_UP,
        values: { uses: usesLabel({ count: link.maxUses ?? link.useCount }) },
      });
    default:
      return strings.INVITE_LINK_PANEL_DEAD_CREATOR_DEMOTED;
  }
}

function clearCopyRevertTimer(): void {
  if (_copyRevertTimer === null) return;
  clearTimeout(_copyRevertTimer);
  _copyRevertTimer = null;
}

function setBody({ nodes, busy }: { nodes: Node[]; busy: boolean }): void {
  const body = $(BODY_SELECTOR)[0];
  if (body === undefined) return;
  // Any render drops an open confirm and the previous live link.
  _confirm = null;
  _liveLink = null;
  clearCopyRevertTimer();
  body.replaceChildren(...nodes);
  const panel = $(MODAL_SELECTOR)[0];
  if (busy) panel?.setAttribute("aria-busy", "true");
  else panel?.removeAttribute("aria-busy");
}

function renderLoading(): void {
  setBody({
    nodes: [
      makeElement({
        tag: "p",
        className: "invitePanelHint",
        text: APP_CONFIG.strings.INVITE_LINK_PANEL_LOADING,
      }),
    ],
    busy: true,
  });
}

function renderLoadFailed(): void {
  const { strings } = APP_CONFIG;
  const retry = makeButton({
    id: "inviteLinkTryAgainBtn",
    label: strings.INVITE_LINK_PANEL_TRY_AGAIN,
    variant: "ghost",
  });
  retry.addEventListener("click", retryLoad);
  setBody({
    nodes: [
      makeElement({
        tag: "p",
        className: "invitePanelHint",
        text: strings.INVITE_LINK_PANEL_LOAD_FAILED,
      }),
      retry,
    ],
    busy: false,
  });
}

function renderEmpty(): void {
  const { strings } = APP_CONFIG;
  setBody({
    nodes: [
      makeElement({
        tag: "p",
        className: "invitePanelHint",
        text: strings.INVITE_LINK_PANEL_EMPTY_HINT,
      }),
      makeSelectField({
        id: "inviteLinkExpiresSelect",
        label: strings.INVITE_LINK_PANEL_EXPIRES_LABEL,
        options: EXPIRY_DAY_CHOICES.map((days) => ({
          value: String(days),
          text: expiryChoiceLabel({ days, fromNow: false }),
          selected: days === DEFAULT_EXPIRY_DAYS,
        })),
      }),
      makeSelectField({
        id: "inviteLinkUsesSelect",
        label: strings.INVITE_LINK_PANEL_USES_LABEL,
        options: usesOptions({ selected: null, floor: 0 }),
      }),
      makeButton({
        id: "inviteLinkCreateBtn",
        label: strings.INVITE_LINK_PANEL_CREATE_LINK,
        variant: "primary",
      }),
    ],
    busy: false,
  });
}

function liveMetaText({ link }: { link: InviteLink }): string {
  const { strings } = APP_CONFIG;
  // "Created by" is omitted when the creator is unknown.
  return [
    ...(link.creatorUsername === null
      ? []
      : [
          fillTemplate({
            template: strings.INVITE_LINK_PANEL_META_CREATED_BY,
            values: { user: link.creatorUsername },
          }),
        ]),
    fillTemplate({
      template: strings.INVITE_LINK_PANEL_META_EXPIRES,
      values: { date: formatShortDate(link.expiresAt) },
    }),
    fillTemplate({
      template: strings.INVITE_LINK_PANEL_META_JOINED,
      values: { count: String(link.useCount) },
    }),
  ].join(" · ");
}

// The first option shows the current expiry date (selected, disabled); the
// rest reset the expiry from now.
function expiryOptionsFor({ link }: { link: InviteLink }): SelectOption[] {
  return [
    {
      value: "",
      text: formatShortDate(link.expiresAt),
      selected: true,
      disabled: true,
    },
    ...EXPIRY_DAY_CHOICES.map((days) => ({
      value: String(days),
      text: expiryChoiceLabel({ days, fromNow: true }),
      selected: false,
      disabled: false,
    })),
  ];
}

const FLOOR_HINT_ID = "inviteLinkUsesFloorHint";

// The helper under the Uses select, present only when an option is disabled.
function makeFloorHint({ link }: { link: InviteLink }): HTMLElement | null {
  const choices = usesOptions({ selected: link.maxUses, floor: link.useCount });
  if (!choices.some((choice) => choice.disabled)) return null;
  const { strings } = APP_CONFIG;
  return makeElement({
    tag: "p",
    id: FLOOR_HINT_ID,
    className: "invitePanelHint",
    text: fillTemplate({
      template:
        link.useCount === 1
          ? strings.INVITE_LINK_PANEL_USES_FLOOR_HINT_ONE
          : strings.INVITE_LINK_PANEL_USES_FLOOR_HINT,
      values: { count: String(link.useCount) },
    }),
  });
}

function renderLive({ link }: { link: InviteLink }): void {
  const { strings } = APP_CONFIG;
  const row = makeElement({ tag: "div", className: "invitePanelLinkRow" });
  const input = makeElement({
    tag: "input",
    id: "inviteLinkUrlInput",
    className: "invitePanelLinkInput",
  });
  input.type = "text";
  input.readOnly = true;
  input.value = inviteUrl({ token: link.token });
  input.setAttribute("aria-label", strings.INVITE_LINK_PANEL_LINK_LABEL);
  row.append(
    input,
    makeButton({
      id: "inviteLinkCopyBtn",
      label: strings.INVITE_LINK_PANEL_COPY,
      variant: "primary",
    }),
  );

  const meta = makeElement({
    tag: "p",
    className: "invitePanelMeta",
    text: liveMetaText({ link }),
  });
  const nodes: Node[] = [
    row,
    meta,
    makeSelectField({
      id: "inviteLinkExpiresSelect",
      label: strings.INVITE_LINK_PANEL_EXPIRES_LABEL,
      options: expiryOptionsFor({ link }),
    }),
    makeSelectField({
      id: "inviteLinkUsesSelect",
      label: strings.INVITE_LINK_PANEL_USES_LABEL,
      options: usesOptions({ selected: link.maxUses, floor: link.useCount }),
    }),
  ];
  const floorHint = makeFloorHint({ link });
  if (floorHint !== null) nodes.push(floorHint);
  const footer = makeElement({ tag: "div", className: "invitePanelFooter" });
  footer.append(
    makeButton({
      id: "inviteLinkNewBtn",
      label: strings.INVITE_LINK_PANEL_NEW_LINK,
      variant: "ghost",
    }),
    makeButton({
      id: "inviteLinkRevokeBtn",
      label: strings.INVITE_LINK_PANEL_REVOKE,
      variant: "danger",
    }),
  );
  nodes.push(footer);
  setBody({ nodes, busy: false });
  _liveLink = link;
}

function renderDead({ link }: { link: InviteLink }): void {
  setBody({
    nodes: [
      makeElement({
        tag: "p",
        className: "invitePanelHint",
        text: deadReasonFor({ link }),
      }),
      makeElement({
        tag: "p",
        className: "invitePanelMeta",
        text: creatorAndJoined({ link }),
      }),
      makeButton({
        id: "inviteLinkCreateBtn",
        label: APP_CONFIG.strings.INVITE_LINK_PANEL_CREATE_LINK,
        variant: "primary",
      }),
    ],
    busy: false,
  });
}

type PanelState = "loading" | "failed" | "empty" | "live" | "dead";

const ENTERING_FOCUS: Record<PanelState, string> = {
  loading: HEADING_SELECTOR,
  failed: "#inviteLinkTryAgainBtn",
  empty: "#inviteLinkExpiresSelect",
  live: "#inviteLinkUrlInput",
  dead: "#inviteLinkCreateBtn",
};

// Records the state the modal is in; focus moves only once the modal is shown
// (`handleModalShown` replays it), since a hidden element cannot take focus.
function focusEntering({ state }: { state: PanelState }): void {
  _state = state;
  if (!_shown) return;
  $(ENTERING_FOCUS[state])[0]?.focus({ preventScroll: true });
}

// Whether focus is still on the heading or somewhere inside the modal; the
// open and Try-again settles move focus only then.
function focusIsInPanel(): boolean {
  const panel = $(MODAL_SELECTOR)[0];
  const active = document.activeElement;
  return (
    panel !== undefined &&
    active instanceof HTMLElement &&
    panel.contains(active)
  );
}

// Renders the landed link and returns its state.
function renderLink({ link }: { link: InviteLink | null }): PanelState {
  if (link === null) {
    renderEmpty();
    return "empty";
  }
  if (link.status === "live") {
    renderLive({ link });
    return "live";
  }
  renderDead({ link });
  return "dead";
}

function isStale({
  token,
  utubID,
}: {
  token: number;
  utubID: number;
}): boolean {
  return (
    !_isOpen || token !== _generation || getState().activeUTubID !== utubID
  );
}

// Bumps the generation (dropping every in-flight response) and clears the open
// session. Silent: announces nothing, leaves the DOM alone.
function endSession(): void {
  _generation += 1;
  _isOpen = false;
  _shown = false;
  _closeRequested = false;
  _openedUTubID = null;
  _inFlight = false;
  _lifecycleInFlight = false;
  _confirm = null;
  _liveLink = null;
  _pending = null;
  clearCopyRevertTimer();
}

function clearBody(): void {
  $(`${BODY_SELECTOR} [aria-disabled]`).removeAttr("aria-disabled");
  $(MODAL_SELECTOR).removeAttr("aria-busy");
  $(BODY_SELECTOR).empty();
}

function isFocusable(element: Element | null): element is HTMLElement {
  return (
    element instanceof HTMLElement &&
    element.isConnected &&
    element.offsetParent !== null &&
    getComputedStyle(element).visibility !== "hidden"
  );
}

// Focus goes back to the trigger, or to the overflow button when the trigger is
// hidden, else the deck header. It moves only when focus sits in the modal or has
// dropped to the body, so a close never steals focus from a control the user (or
// another surface) already moved to.
function restoreFocus(): void {
  const active = document.activeElement;
  const modal = $(MODAL_SELECTOR)[0];
  const lost =
    active === null ||
    active === document.body ||
    (modal !== undefined && modal.contains(active));
  if (!lost) return;
  for (const selector of FOCUS_RETURN_SELECTORS) {
    const target = $(selector)[0] ?? null;
    if (isFocusable(target)) {
      target.focus({ preventScroll: true });
      return;
    }
  }
}

// A programmatic close (UTub switch, deselect, forced close): ends the session,
// empties the body at once, moves focus out of the modal and hides it. Silent.
function teardownPanel(): void {
  const wasOpen = _isOpen;
  endSession();
  clearBody();
  if (!wasOpen) return;
  restoreFocus();
  $(MODAL_SELECTOR).modal("hide");
}

// Fired when a hide starts: Escape, backdrop, the close button, or our own
// teardown. A hide that starts while a confirm is open (not from the close button
// and not mid-request) steps back out of the confirm instead of closing.
function handleModalHide(event: JQuery.TriggeredEvent): void {
  if (!_isOpen) return;
  if (_confirm !== null && !_lifecycleInFlight && !_closeRequested) {
    event.preventDefault();
    cancelConfirm();
    return;
  }
  endSession();
}

function handleModalHidden(): void {
  _closeRequested = false;
  // A reopen during the fade-out owns the body and the session, but Bootstrap
  // ignored its show() mid-transition: show again now that the hide has finished.
  if (_isOpen) {
    $(MODAL_SELECTOR).modal("show");
    return;
  }
  clearBody();
  restoreFocus();
}

// Bootstrap moves focus to the modal element once the fade ends; land it on the
// entering control for the state the session is in.
function handleModalShown(): void {
  if (!_isOpen) {
    // A teardown during the fade-in had its hide() ignored (mid-transition).
    $(MODAL_SELECTOR).modal("hide");
    return;
  }
  _shown = true;
  focusEntering({ state: _state });
}

function messageForDenied({ errorCode }: { errorCode: number | null }): string {
  return errorCode === INVITE_LINK_LOCKED_ERROR_CODE
    ? APP_CONFIG.strings.UTUB_IS_LOCKED
    : APP_CONFIG.strings.INVITE_LINK_PANEL_MANAGE_LOST;
}

// A 403/404: announce (the single announcement), close silently, then refresh
// the UTub so the gate learns the new role or lock state.
function handleDenied({
  utubID,
  errorCode,
}: {
  utubID: number;
  errorCode: number | null;
}): void {
  const message = messageForDenied({ errorCode });
  withMemberControlFocusFallback({ write: teardownPanel });
  announceInviteLinkPanel({ message, politeness: "assertive" });
  void updateUTubOnFindingStaleData({ utubID });
}

function handleLoadFailure({
  failure,
  utubID,
}: {
  failure: InviteLinkLoadFailure;
  utubID: number;
}): void {
  if (failure.kind === "denied") {
    handleDenied({ utubID, errorCode: failure.errorCode });
    return;
  }
  renderLoadFailed();
}

// Loads the link and paints it. `settle` applies the open-settle guard to focus
// (open and Try again); a resync always applies the entering-focus rule.
function loadAndRender({
  settle,
  resyncMessage,
}: {
  settle: boolean;
  resyncMessage: string | null;
}): void {
  const utubID = _openedUTubID;
  if (utubID === null) return;
  // Each load supersedes any in-flight one so an older response never repaints.
  _generation += 1;
  const token = _generation;
  getInviteLink({ utubID }).then(
    (link) => {
      if (isStale({ token, utubID })) return;
      const state = renderLink({ link });
      if (!settle || !_shown || focusIsInPanel()) focusEntering({ state });
      announceLanding({ link, resyncMessage, state });
    },
    (failure: InviteLinkLoadFailure) => {
      if (isStale({ token, utubID })) return;
      log("invite link load failed", { utubID, kind: failure.kind });
      handleLoadFailure({ failure, utubID });
      if (
        failure.kind !== "denied" &&
        (!settle || !_shown || focusIsInPanel())
      ) {
        focusEntering({ state: "failed" });
      }
    },
  );
}

// One announcement per landing. A resync landing empty or live announces its
// message alone; landing dead it announces "{message} {reason}" in one write,
// and a plain open landing dead announces the reason alone.
function announceLanding({
  link,
  resyncMessage,
  state,
}: {
  link: InviteLink | null;
  resyncMessage: string | null;
  state: PanelState;
}): void {
  const reason =
    state === "dead" && link !== null ? deadReasonFor({ link }) : null;
  const parts = [resyncMessage, reason].filter(
    (part): part is string => part !== null,
  );
  if (parts.length === 0) return;
  announceInviteLinkPanel({ message: parts.join(" ") });
}

function retryLoad(): void {
  if (!_isOpen) return;
  renderLoading();
  focusEntering({ state: "loading" });
  loadAndRender({ settle: true, resyncMessage: null });
}

/**
 * Re-GETs the link and re-renders the panel, applying the entering-focus rule
 * for the state it lands in, then announces `message` (composed with the dead
 * reason when it lands dead). Used by Try-again-like flows and the mutation
 * resyncs; a failed re-GET follows the GET failure rule.
 */
export function resyncInviteLinkPanel({
  message,
}: {
  message: string | null;
}): void {
  if (!_isOpen) return;
  loadAndRender({ settle: false, resyncMessage: message });
}

const LOCKABLE_SELECTOR =
  "#inviteLinkCreateBtn, #inviteLinkNewBtn, #inviteLinkRevokeBtn, #inviteLinkConfirmActionBtn";
const INLINE_ERROR_ID = "inviteLinkInlineError";

type LifecycleKind = "create" | "replace" | "revoke";

// aria-disabled (never native `disabled`) keeps focus on the pressed control.
// Cancel is deliberately not lockable.
function setControlsLocked({ locked }: { locked: boolean }): void {
  const controls = $(LOCKABLE_SELECTOR);
  if (locked) controls.attr("aria-disabled", "true");
  else controls.removeAttr("aria-disabled");
}

const SAVING_ID = "inviteLinkSaving";
const COPY_HINT_ID = "inviteLinkCopyHint";
const EXPIRES_SELECT_ID = "inviteLinkExpiresSelect";
const USES_SELECT_ID = "inviteLinkUsesSelect";

function clearInFlight(): void {
  _inFlight = false;
  _lifecycleInFlight = false;
  _pending = null;
  document.getElementById(SAVING_ID)?.remove();
  $(`${BODY_SELECTOR} select[aria-busy]`).removeAttr("aria-busy");
  setControlsLocked({ locked: false });
}

// Removes the inline error and the invalid state it tied to a select.
function clearInlineError(): void {
  document.getElementById(INLINE_ERROR_ID)?.remove();
  $(`${BODY_SELECTOR} select`)
    .removeAttr("aria-invalid")
    .removeAttr("aria-describedby");
}

function showInlineError({
  message = APP_CONFIG.strings.INVITE_LINK_PANEL_ERROR_GENERIC,
  describes = null,
}: {
  message?: string;
  describes?: HTMLElement | null;
} = {}): void {
  clearInlineError();
  const error = makeElement({
    tag: "p",
    id: INLINE_ERROR_ID,
    className: "invitePanelError",
    text: message,
  });
  $(BODY_SELECTOR)[0]?.append(error);
  if (describes !== null) {
    describes.setAttribute("aria-describedby", INLINE_ERROR_ID);
  }
  announceInviteLinkPanel({ message, politeness: "assertive" });
}

function selectedCreateSettings(): {
  expiresInDays: number;
  maxUses: number | null;
} {
  const expires = $("#inviteLinkExpiresSelect").val();
  const uses = $("#inviteLinkUsesSelect").val();
  return {
    expiresInDays:
      typeof expires === "string" && expires !== ""
        ? Number(expires)
        : DEFAULT_EXPIRY_DAYS,
    maxUses: typeof uses === "string" && uses !== "" ? Number(uses) : null,
  };
}

function sendLifecycle({
  kind,
  utubID,
}: {
  kind: LifecycleKind;
  utubID: number;
}): Promise<InviteLink | true> | null {
  if (kind === "create") {
    return createInviteLink({ utubID, ...selectedCreateSettings() });
  }
  if (kind === "replace") {
    if (_liveLink === null) return null;
    return replaceInviteLink({
      utubID,
      expiresInDays: replaceExpiryDays({
        expiresAt: _liveLink.expiresAt,
        now: Date.now(),
      }),
      maxUses: _liveLink.maxUses,
    });
  }
  return revokeInviteLink({ utubID });
}

function successMessageFor({ kind }: { kind: LifecycleKind }): string {
  const { strings } = APP_CONFIG;
  return kind === "create"
    ? strings.INVITE_LINK_PANEL_CREATED
    : kind === "replace"
      ? strings.INVITE_LINK_PANEL_REPLACED
      : strings.INVITE_LINK_PANEL_REVOKED;
}

// create meets code 4 (a live link exists); replace and revoke meet code 1.
function resyncRuleFor({ kind }: { kind: LifecycleKind }): {
  code: number;
  message: string;
} {
  const { strings } = APP_CONFIG;
  return kind === "create"
    ? {
        code: INVITE_LINK_LIVE_EXISTS_ERROR_CODE,
        message: strings.INVITE_LINK_PANEL_RESYNC_LIVE_EXISTS,
      }
    : {
        code: INVITE_LINK_NOT_FOUND_ERROR_CODE,
        message: strings.INVITE_LINK_PANEL_RESYNC_REVOKED,
      };
}

function onLifecycleSuccess({
  kind,
  link,
  utubID,
  token,
}: {
  kind: LifecycleKind;
  link: InviteLink | true;
  utubID: number;
  token: number;
}): void {
  const stale = isStale({ token, utubID });
  // Same-UTub outcomes are announced even after the panel closed, except a
  // success the forced close already covered.
  if (getState().activeUTubID === utubID && token !== _forcedClosedToken) {
    announceInviteLinkPanel({ message: successMessageFor({ kind }) });
  }
  if (stale) return;
  clearInFlight();
  if (link === true) {
    // Revoke: the empty state, focus on Create link (not the Expires select).
    renderEmpty();
    $("#inviteLinkCreateBtn")[0]?.focus({ preventScroll: true });
    return;
  }
  renderLive({ link });
  $("#inviteLinkCopyBtn")[0]?.focus({ preventScroll: true });
}

function onLifecycleFailure({
  kind,
  failure,
  utubID,
  token,
}: {
  kind: LifecycleKind;
  failure: InviteLinkMutationFailure;
  utubID: number;
  token: number;
}): void {
  const stale = isStale({ token, utubID });
  if (failure.kind === "csrf") {
    $("body").html(failure.html);
    return;
  }
  if (!stale) clearInFlight();
  // A 429 was already announced by the global handler.
  if (failure.kind === "rate_limited") return;

  const sameUTub = getState().activeUTubID === utubID;
  const resync = resyncRuleFor({ kind });
  if (failure.errorCode === resync.code) {
    if (stale) {
      if (sameUTub) {
        announceInviteLinkPanel({
          message: resync.message,
          politeness: "assertive",
        });
      }
      return;
    }
    resyncInviteLinkPanel({ message: resync.message });
    return;
  }
  if (failure.status === 403 || failure.status === 404) {
    if (stale) {
      if (sameUTub) {
        announceInviteLinkPanel({
          message: messageForDenied({ errorCode: failure.errorCode }),
          politeness: "assertive",
        });
        void updateUTubOnFindingStaleData({ utubID });
      }
      return;
    }
    handleDenied({ utubID, errorCode: failure.errorCode });
    return;
  }
  if (stale) {
    if (sameUTub) {
      announceInviteLinkPanel({
        message: APP_CONFIG.strings.INVITE_LINK_PANEL_ERROR_GENERIC,
        politeness: "assertive",
      });
    }
    return;
  }
  showInlineError();
}

// Sends one lifecycle request. One at a time: an aria-disabled control that is
// pressed again, or any press while a request is in flight, does nothing.
function runLifecycle({ kind }: { kind: LifecycleKind }): void {
  if (_inFlight || !_isOpen) return;
  const utubID = _openedUTubID;
  if (utubID === null) return;
  const token = _generation;
  const request = sendLifecycle({ kind, utubID });
  if (request === null) return;
  clearInlineError();
  _inFlight = true;
  _lifecycleInFlight = true;
  setControlsLocked({ locked: true });
  request.then(
    (link) => onLifecycleSuccess({ kind, link, utubID, token }),
    (failure: InviteLinkMutationFailure) => {
      log("invite link mutation failed", { kind, failure: failure.kind });
      onLifecycleFailure({ kind, failure, utubID, token });
    },
  );
}

function selectFor({ field }: { field: SaveField }): HTMLSelectElement | null {
  const element = document.getElementById(
    field === "expires" ? EXPIRES_SELECT_ID : USES_SELECT_ID,
  );
  return element instanceof HTMLSelectElement ? element : null;
}

// What the server last confirmed for a select. The Expires select always shows
// its first option (the current expiry date), whose value is "".
function committedValue({ field }: { field: SaveField }): string {
  if (field === "expires" || _liveLink === null) return "";
  return _liveLink.maxUses === null ? "" : String(_liveLink.maxUses);
}

// Sets the selects back to their committed values. Programmatic: no `change`
// event fires and focus does not move.
function restoreCommitted(): void {
  for (const field of ["expires", "uses"] as const) {
    const select = selectFor({ field });
    if (select !== null) select.value = committedValue({ field });
  }
}

// Repaints the meta, the Expires first option and the Uses options/helper from
// `link` without replacing the controls, so focus stays where it is.
function refreshLiveInPlace({ link }: { link: InviteLink }): void {
  _liveLink = link;
  $(`${BODY_SELECTOR} .invitePanelMeta`).first().text(liveMetaText({ link }));
  const expires = selectFor({ field: "expires" });
  if (expires !== null) {
    fillSelectOptions({ select: expires, options: expiryOptionsFor({ link }) });
  }
  const uses = selectFor({ field: "uses" });
  if (uses === null) return;
  fillSelectOptions({
    select: uses,
    options: usesOptions({ selected: link.maxUses, floor: link.useCount }),
  });
  document.getElementById(FLOOR_HINT_ID)?.remove();
  const hint = makeFloorHint({ link });
  if (hint !== null) uses.parentElement?.after(hint);
}

function usesBelowJoinedMessage({ count }: { count: number }): string {
  const { strings } = APP_CONFIG;
  return fillTemplate({
    template:
      count === 1
        ? strings.INVITE_LINK_PANEL_USES_BELOW_JOINED_ONE
        : strings.INVITE_LINK_PANEL_USES_BELOW_JOINED,
    values: { count: String(count) },
  });
}

function savedMessageFor({
  field,
  link,
}: {
  field: SaveField;
  link: InviteLink;
}): string {
  const { strings } = APP_CONFIG;
  if (field === "expires") {
    return fillTemplate({
      template: strings.INVITE_LINK_PANEL_EXPIRES_SET,
      values: { date: formatShortDate(link.expiresAt) },
    });
  }
  return fillTemplate({
    template: strings.INVITE_LINK_PANEL_USES_SET,
    values: {
      label:
        link.maxUses === null
          ? strings.INVITE_LINK_PANEL_USES_UNLIMITED
          : usesLabel({ count: link.maxUses }),
    },
  });
}

function onSaveSuccess({
  field,
  link,
  utubID,
  token,
}: {
  field: SaveField;
  link: InviteLink;
  utubID: number;
  token: number;
}): void {
  // A dropped save response does nothing at all.
  if (isStale({ token, utubID })) return;
  clearInFlight();
  clearInlineError();
  if (link.status !== "live") {
    // e.g. a pick equal to the joined count used the link up (a 200).
    const state = renderLink({ link });
    focusEntering({ state });
    announceLanding({ link, resyncMessage: null, state });
    return;
  }
  refreshLiveInPlace({ link });
  restoreCommitted();
  announceInviteLinkPanel({ message: savedMessageFor({ field, link }) });
}

// Code 6: restore the committed value, name the minimum, then re-GET once to
// refresh the count in place. A GET that lands null or non-live is a resync.
function restoreForUsesBelowJoined({
  utubID,
  token,
}: {
  utubID: number;
  token: number;
}): void {
  restoreCommitted();
  const uses = selectFor({ field: "uses" });
  if (uses === null || _liveLink === null) return;
  showInlineError({
    message: usesBelowJoinedMessage({ count: _liveLink.useCount }),
    describes: uses,
  });
  uses.setAttribute("aria-invalid", "true");
  getInviteLink({ utubID }).then(
    (link) => {
      if (isStale({ token, utubID }) || _inFlight) return;
      if (link === null || link.status !== "live") {
        clearInlineError();
        const state = renderLink({ link });
        focusEntering({ state });
        announceLanding({
          link,
          resyncMessage:
            link === null
              ? APP_CONFIG.strings.INVITE_LINK_PANEL_RESYNC_REVOKED
              : null,
          state,
        });
        return;
      }
      refreshLiveInPlace({ link });
      restoreCommitted();
      const message = document.getElementById(INLINE_ERROR_ID);
      if (message !== null) {
        message.textContent = usesBelowJoinedMessage({ count: link.useCount });
      }
    },
    () => {
      // A failed refresh is silent: the restored state stays as it is.
    },
  );
}

function onSaveFailure({
  field,
  failure,
  utubID,
  token,
}: {
  field: SaveField;
  failure: InviteLinkMutationFailure;
  utubID: number;
  token: number;
}): void {
  // A dropped save response does nothing: no render, announcement or refresh.
  if (isStale({ token, utubID })) return;
  if (failure.kind === "csrf") {
    $("body").html(failure.html);
    return;
  }
  clearInFlight();
  // A 429 was already announced by the global handler.
  if (failure.kind === "rate_limited") {
    restoreCommitted();
    return;
  }
  if (failure.errorCode === INVITE_LINK_NOT_FOUND_ERROR_CODE) {
    resyncInviteLinkPanel({
      message: APP_CONFIG.strings.INVITE_LINK_PANEL_RESYNC_REVOKED,
    });
    return;
  }
  if (failure.errorCode === INVITE_LINK_DEAD_UPDATE_ERROR_CODE) {
    resyncInviteLinkPanel({
      message: APP_CONFIG.strings.INVITE_LINK_PANEL_RESYNC_DEAD_UPDATE,
    });
    return;
  }
  if (failure.errorCode === INVITE_LINK_USES_BELOW_JOINED_ERROR_CODE) {
    restoreForUsesBelowJoined({ utubID, token });
    return;
  }
  if (failure.status === 403 || failure.status === 404) {
    handleDenied({ utubID, errorCode: failure.errorCode });
    return;
  }
  restoreCommitted();
  showInlineError({ describes: selectFor({ field }) });
}

// Sends one settings save. The select stays enabled and focused; the lifecycle
// controls are locked until the response.
function saveSetting({
  field,
  value,
}: {
  field: SaveField;
  value: string;
}): void {
  const utubID = _openedUTubID;
  const select = selectFor({ field });
  if (utubID === null || select === null) return;
  let body: InviteLinkUpdateBody;
  if (field === "expires") {
    if (value === "") return;
    body = { expires_in_days: Number(value) };
  } else {
    body = { max_uses: value === "" ? null : Number(value) };
  }
  const token = _generation;
  _inFlight = true;
  _pending = { field, value };
  setControlsLocked({ locked: true });
  select.setAttribute("aria-busy", "true");
  select.after(
    makeElement({
      tag: "span",
      id: SAVING_ID,
      className: "invitePanelSaving",
      text: APP_CONFIG.strings.INVITE_LINK_PANEL_SAVING,
    }),
  );
  updateInviteLink({ utubID, body }).then(
    (link) => onSaveSuccess({ field, link, utubID, token }),
    (failure: InviteLinkMutationFailure) => {
      log("invite link save failed", { field, failure: failure.kind });
      onSaveFailure({ field, failure, utubID, token });
    },
  );
}

// One save at a time: a change to the select being saved reverts to the value
// being saved, a change to the other select (or any change during a lifecycle
// request) reverts to the committed value. Neither fires `change`.
function handleSelectChange(event: JQuery.ChangeEvent): void {
  if (_liveLink === null) return; // The empty state's selects never save.
  const select = event.target as HTMLSelectElement;
  const field: SaveField | null =
    select.id === EXPIRES_SELECT_ID
      ? "expires"
      : select.id === USES_SELECT_ID
        ? "uses"
        : null;
  if (field === null) return;
  if (_lifecycleInFlight) {
    select.value = committedValue({ field });
    return;
  }
  if (_inFlight) {
    select.value =
      _pending !== null && _pending.field === field
        ? _pending.value
        : committedValue({ field });
    return;
  }
  saveSetting({ field, value: select.value });
}

function showCopyFallbackHint(): void {
  const hint = makeElement({
    tag: "p",
    id: COPY_HINT_ID,
    className: "invitePanelHint",
    text: APP_CONFIG.strings.INVITE_LINK_PANEL_COPY_FALLBACK,
  });
  $(".invitePanelLinkRow").first().after(hint);
  announceInviteLinkPanel({ message: hint.textContent ?? "" });
}

// Moves focus to the readonly input and selects all of it so Ctrl+C works on
// every browser; a throw while selecting is the `failure` result.
function copyFallback({ input }: { input: HTMLInputElement }): void {
  try {
    input.focus();
    input.select();
    input.setSelectionRange(0, input.value.length);
  } catch {
    emit({
      event: UI_EVENTS.UI_INVITE_LINK_COPY,
      result: INVITE_LINK_COPY_RESULT.FAILURE,
    });
    $("#inviteLinkCopyBtn")[0]?.focus({ preventScroll: true });
    // Announced only: an inline error would clear a code-6 invalid state.
    announceInviteLinkPanel({
      message: APP_CONFIG.strings.INVITE_LINK_PANEL_ERROR_GENERIC,
      politeness: "assertive",
    });
    return;
  }
  emit({
    event: UI_EVENTS.UI_INVITE_LINK_COPY,
    result: INVITE_LINK_COPY_RESULT.FALLBACK,
  });
  showCopyFallbackHint();
}

function onCopySuccess(): void {
  emit({
    event: UI_EVENTS.UI_INVITE_LINK_COPY,
    result: INVITE_LINK_COPY_RESULT.SUCCESS,
  });
}

function handleCopy(): void {
  const input = document.getElementById("inviteLinkUrlInput");
  const copyButton = document.getElementById("inviteLinkCopyBtn");
  const utubID = _openedUTubID;
  if (
    !(input instanceof HTMLInputElement) ||
    copyButton === null ||
    utubID === null
  ) {
    return;
  }
  const token = _generation;
  clearCopyRevertTimer();
  copyButton.textContent = APP_CONFIG.strings.INVITE_LINK_PANEL_COPY;
  document.getElementById(COPY_HINT_ID)?.remove();
  // The write starts synchronously inside the click (Safari's gesture rule).
  let write: Promise<void> | null = null;
  try {
    write = navigator.clipboard?.writeText(input.value) ?? null;
  } catch {
    write = null;
  }
  if (write === null) {
    copyFallback({ input });
    return;
  }
  write.then(
    () => {
      onCopySuccess();
      if (isStale({ token, utubID })) return;
      // The panel may have re-rendered since the press; label the live button.
      const liveButton = document.getElementById("inviteLinkCopyBtn");
      announceInviteLinkPanel({
        message: APP_CONFIG.strings.INVITE_LINK_PANEL_COPY_SUCCESS,
      });
      if (liveButton === null) return;
      clearCopyRevertTimer();
      liveButton.textContent = APP_CONFIG.strings.INVITE_LINK_PANEL_COPIED;
      _copyRevertTimer = setTimeout(() => {
        _copyRevertTimer = null;
        liveButton.textContent = APP_CONFIG.strings.INVITE_LINK_PANEL_COPY;
      }, COPIED_LABEL_MS);
    },
    () => {
      if (isStale({ token, utubID })) {
        // The panel is gone, so there is no input to select: count the failure.
        emit({
          event: UI_EVENTS.UI_INVITE_LINK_COPY,
          result: INVITE_LINK_COPY_RESULT.FAILURE,
        });
        return;
      }
      copyFallback({ input });
    },
  );
}

function openConfirm({ kind }: { kind: "revoke" | "new" }): void {
  const footer = $(".invitePanelFooter")[0];
  if (footer === undefined || _confirm !== null) return;
  const { strings } = APP_CONFIG;
  const question =
    kind === "revoke"
      ? strings.INVITE_LINK_PANEL_CONFIRM_REVOKE_QUESTION
      : strings.INVITE_LINK_PANEL_CONFIRM_NEW_QUESTION;
  const actionLabel =
    kind === "revoke"
      ? strings.INVITE_LINK_PANEL_CONFIRM_REVOKE_ACTION
      : strings.INVITE_LINK_PANEL_CONFIRM_NEW_ACTION;
  const group = makeElement({ tag: "div", className: "invitePanelConfirm" });
  group.setAttribute("role", "group");
  group.setAttribute(
    "aria-label",
    strings.INVITE_LINK_PANEL_CONFIRM_GROUP_LABEL,
  );
  const buttons = makeElement({
    tag: "div",
    className: "invitePanelConfirmButtons",
  });
  const cancel = makeButton({
    id: "inviteLinkConfirmCancelBtn",
    label: strings.INVITE_LINK_PANEL_CANCEL,
    variant: "ghost",
  });
  const action = makeButton({
    id: "inviteLinkConfirmActionBtn",
    label: actionLabel,
    variant: kind === "revoke" ? "danger" : "primary",
  });
  buttons.append(cancel, action);
  group.append(
    makeElement({ tag: "p", className: "invitePanelHint", text: question }),
    buttons,
  );
  const footerNodes = Array.from(footer.childNodes);
  footer.replaceChildren(group);
  _confirm = {
    kind,
    footerNodes,
    originId: kind === "revoke" ? "inviteLinkRevokeBtn" : "inviteLinkNewBtn",
  };
  if (_inFlight) setControlsLocked({ locked: true });
  cancel.focus({ preventScroll: true });
  announceInviteLinkPanel({ message: question });
}

function cancelConfirm(): void {
  if (_confirm === null) return;
  const { footerNodes, originId } = _confirm;
  const footer = $(".invitePanelFooter")[0];
  _confirm = null;
  footer?.replaceChildren(...footerNodes);
  // The restored buttons were detached while the lock was applied.
  if (_inFlight) setControlsLocked({ locked: true });
  document.getElementById(originId)?.focus({ preventScroll: true });
}

function handlePanelClick(event: JQuery.ClickEvent): void {
  const target = (event.target as HTMLElement).closest("button");
  if (target === null) return;
  if (target.classList.contains("btn-close")) {
    _closeRequested = true;
    return;
  }
  if (target.id === "inviteLinkConfirmCancelBtn") {
    // While a lifecycle request is in flight the confirm is not cancelled.
    if (!_lifecycleInFlight) cancelConfirm();
    return;
  }
  if (target.id === "inviteLinkCopyBtn") {
    handleCopy();
    return;
  }
  if (!target.matches(LOCKABLE_SELECTOR)) return;
  if (_inFlight) {
    event.preventDefault();
    return;
  }
  switch (target.id) {
    case "inviteLinkCreateBtn":
      runLifecycle({ kind: "create" });
      return;
    case "inviteLinkNewBtn":
      openConfirm({ kind: "new" });
      return;
    case "inviteLinkRevokeBtn":
      openConfirm({ kind: "revoke" });
      return;
    case "inviteLinkConfirmActionBtn":
      if (_confirm !== null) {
        runLifecycle({
          kind: _confirm.kind === "revoke" ? "revoke" : "replace",
        });
      }
      return;
  }
}

function openPanel(): void {
  const { activeUTubID } = getState();
  if (activeUTubID === null || !canManageInviteLink()) return;
  // The modal is blocking, so it only has to clear the in-place Members surfaces
  // (add form, filter, gear popover or sheet). Another home form (URL create,
  // UTub create) is deliberately left alone.
  hideAndResetMemberCombobox();
  closeMemberNameFilter();
  // Signalled over the bus, not by importing panel-settings: popover.ts reaches
  // client.ts, which reaches this module through the deck graph (an import cycle).
  emitAppEvent(AppEvents.INVITE_PANEL_OPENED);
  _isOpen = true;
  _shown = false;
  _closeRequested = false;
  _openedUTubID = activeUTubID;
  emit({ event: UI_EVENTS.UI_INVITE_PANEL_OPEN });
  renderLoading();
  focusEntering({ state: "loading" });
  $(MODAL_SELECTOR).modal("show");
  loadAndRender({ settle: true, resyncMessage: null });
}

// The gate flipped to false while the modal was open: close, with focus kept on
// a control that exists, and announce only when the UTub is still the one the
// modal opened for (a UTub switch or deselect is not a loss of rights).
function forceClosePanel(): void {
  const announce = getState().activeUTubID === _openedUTubID;
  _forcedClosedToken = _generation;
  teardownPanel();
  if (announce) {
    announceInviteLinkPanel({
      message: APP_CONFIG.strings.INVITE_LINK_PANEL_FORCED_CLOSE,
    });
  }
}

/** Shows the trigger to owners and co-owners of an unlocked UTub, hides it otherwise. */
export function syncInviteLinkTrigger(): void {
  const trigger = $(TRIGGER_SELECTOR);
  if (canManageInviteLink()) trigger.showClassNormal();
  else trigger.hideClass();
}

/**
 * Closes the modal and clears it silently (UTub switch, deselect or rebuild):
 * body emptied, in-flight responses dropped, modal hidden. Also clears the
 * forced-close mark.
 */
export function resetInviteLinkPanel(): void {
  _forcedClosedToken = null;
  teardownPanel();
}

/**
 * Binds the trigger and the modal's handlers and subscribes the gate: the
 * trigger follows `canManageInviteLink`, and a flip to false closes an open
 * modal. Returns the unsubscribe function.
 */
export function initInviteLinkPanel(): () => void {
  $(TRIGGER_SELECTOR).off(".invitePanel").on("click.invitePanel", openPanel);
  $(MODAL_SELECTOR)
    .off(".invitePanel")
    .on("hide.bs.modal.invitePanel", handleModalHide)
    .on("hidden.bs.modal.invitePanel", handleModalHidden)
    .on("shown.bs.modal.invitePanel", handleModalShown)
    .on("click.invitePanel", "button", handlePanelClick)
    .on("change.invitePanel", "select", handleSelectChange);
  syncInviteLinkTrigger();
  const unsubscribeStore = subscribe((changedKeys) => {
    if (!RELEVANT_KEYS.some((key) => changedKeys.includes(key))) return;
    withMemberControlFocusFallback({ write: syncInviteLinkTrigger });
    if (_isOpen && !canManageInviteLink()) forceClosePanel();
  });
  return () => {
    unsubscribeStore();
  };
}
