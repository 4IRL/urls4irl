import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { fillTemplate } from "../../lib/string-template.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  AppEvents,
  emit as emitAppEvent,
  on,
  type AppEventMap,
} from "../../lib/event-bus.js";
import { getState, subscribe, type AppState } from "../../store/app-store.js";
import { canManageInviteLink } from "../utubs/policy.js";
import { updateUTubOnFindingStaleData } from "../utubs/stale-data.js";
import { withMemberControlFocusFallback } from "./focus-fallback.js";
import { hideAndResetMemberCombobox } from "./member-combobox.js";
import { announceMemberRowAction } from "./notice.js";
import { closeMemberNameFilter } from "./search.js";
import {
  getInviteLink,
  INVITE_LINK_LOCKED_ERROR_CODE,
  type InviteLink,
  type InviteLinkLoadFailure,
} from "./invite-link-client.js";

const log = debug("members");

const TRIGGER_SELECTOR = "#memberBtnInviteLink";
const PANEL_SELECTOR = "#MemberInvitePanel";
const HEADING_SELECTOR = "#MemberInvitePanelHeading";
const BODY_SELECTOR = "#MemberInvitePanelBody";
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
let _openedUTubID: number | null = null;
let _forcedClosedToken: number | null = null;

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

function makeSelectField({
  id,
  label,
  options,
}: {
  id: string;
  label: string;
  options: Array<{
    value: string;
    text: string;
    selected?: boolean;
    disabled?: boolean;
  }>;
}): HTMLElement {
  const field = makeElement({ tag: "div", className: "invitePanelField" });
  const labelElement = makeElement({ tag: "label", text: label });
  labelElement.htmlFor = id;
  const select = makeElement({
    tag: "select",
    id,
    className: "panelSettingsSelect invitePanelSelect",
  });
  for (const option of options) {
    const optionElement = makeElement({ tag: "option", text: option.text });
    optionElement.value = option.value;
    if (option.disabled === true) optionElement.disabled = true;
    select.append(optionElement);
    // Selectedness is set after the option is attached and only when true, so a
    // later option never resets the choice.
    if (option.selected === true) optionElement.selected = true;
  }
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

function setBody({ nodes, busy }: { nodes: Node[]; busy: boolean }): void {
  const body = $(BODY_SELECTOR)[0];
  if (body === undefined) return;
  body.replaceChildren(...nodes);
  const panel = $(PANEL_SELECTOR)[0];
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

  const expiresText = fillTemplate({
    template: strings.INVITE_LINK_PANEL_META_EXPIRES,
    values: { date: formatShortDate(link.expiresAt) },
  });
  // "Created by" is omitted when the creator is unknown.
  const joinedText = fillTemplate({
    template: strings.INVITE_LINK_PANEL_META_JOINED,
    values: { count: String(link.useCount) },
  });
  const metaParts = [
    ...(link.creatorUsername === null
      ? []
      : [
          fillTemplate({
            template: strings.INVITE_LINK_PANEL_META_CREATED_BY,
            values: { user: link.creatorUsername },
          }),
        ]),
    expiresText,
    joinedText,
  ];
  const meta = makeElement({
    tag: "p",
    className: "invitePanelMeta",
    text: metaParts.join(" · "),
  });

  const expiryOptions = [
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
  const usesChoices = usesOptions({
    selected: link.maxUses,
    floor: link.useCount,
  });
  const nodes: Node[] = [
    row,
    meta,
    makeSelectField({
      id: "inviteLinkExpiresSelect",
      label: strings.INVITE_LINK_PANEL_EXPIRES_LABEL,
      options: expiryOptions,
    }),
    makeSelectField({
      id: "inviteLinkUsesSelect",
      label: strings.INVITE_LINK_PANEL_USES_LABEL,
      options: usesChoices,
    }),
  ];
  if (usesChoices.some((choice) => choice.disabled)) {
    nodes.push(
      makeElement({
        tag: "p",
        className: "invitePanelHint",
        text: fillTemplate({
          template:
            link.useCount === 1
              ? strings.INVITE_LINK_PANEL_USES_FLOOR_HINT_ONE
              : strings.INVITE_LINK_PANEL_USES_FLOOR_HINT,
          values: { count: String(link.useCount) },
        }),
      }),
    );
  }
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

function focusEntering({ state }: { state: PanelState }): void {
  $(ENTERING_FOCUS[state])[0]?.focus({ preventScroll: true });
}

// Whether focus is still on the heading or somewhere inside the panel; the
// open and Try-again settles move focus only then.
function focusIsInPanel(): boolean {
  const panel = $(PANEL_SELECTOR)[0];
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

// Bumps the generation (dropping every in-flight response), hides the panel,
// empties the body and clears the open session. Silent: announces nothing.
function teardownPanel(): void {
  _generation += 1;
  _isOpen = false;
  _openedUTubID = null;
  $(PANEL_SELECTOR).addClass("hidden").removeAttr("aria-busy");
  $(BODY_SELECTOR).empty();
  $(TRIGGER_SELECTOR).attr("aria-expanded", "false").removeClass("active");
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
      if (!settle || focusIsInPanel()) focusEntering({ state });
      announceLanding({ link, resyncMessage, state });
    },
    (failure: InviteLinkLoadFailure) => {
      if (isStale({ token, utubID })) return;
      log("invite link load failed", { utubID, kind: failure.kind });
      handleLoadFailure({ failure, utubID });
      if (failure.kind !== "denied" && (!settle || focusIsInPanel())) {
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

function openPanel(): void {
  const { activeUTubID } = getState();
  if (activeUTubID === null || !canManageInviteLink()) return;
  // The panel is the only open Members surface. Another home form (URL create,
  // UTub create) is deliberately left alone: both may be on screen.
  hideAndResetMemberCombobox();
  closeMemberNameFilter();
  // Signalled over the bus, not by importing panel-settings: popover.ts reaches
  // client.ts, which reaches this module through the deck graph (an import cycle).
  emitAppEvent(AppEvents.INVITE_PANEL_OPENED);
  _isOpen = true;
  _openedUTubID = activeUTubID;
  $(PANEL_SELECTOR).removeClass("hidden");
  $(TRIGGER_SELECTOR).attr("aria-expanded", "true").addClass("active");
  emit({ event: UI_EVENTS.UI_INVITE_PANEL_OPEN });
  renderLoading();
  focusEntering({ state: "loading" });
  loadAndRender({ settle: true, resyncMessage: null });
}

// A user-initiated close (trigger or Escape): silent, focus returns to the trigger.
function closePanelByUser(): void {
  if (!_isOpen) return;
  teardownPanel();
  $(TRIGGER_SELECTOR)[0]?.focus({ preventScroll: true });
}

// Another surface took over (add form, filter, gear, another home form): close
// silently and leave focus alone, since it is moving into that surface.
function closePanelForOtherSurface(): void {
  if (!_isOpen) return;
  teardownPanel();
}

// The deck context went away (mobile deck switch, Members collapse): close
// silently, keeping focus on a control that still exists.
function closePanelForDeckLoss(): void {
  if (!_isOpen) return;
  withMemberControlFocusFallback({ write: teardownPanel });
}

const DECK_LOSS_TARGETS: ReadonlyArray<
  AppEventMap["mobile:deck-switched"]["target"]
> = ["url-deck", "utub-deck", "no-utub", "trash"];

function subscribeCrossFeatureExclusion(): () => void {
  const disposers = [
    on(AppEvents.MEMBER_ADD_OPENED, closePanelForOtherSurface),
    on(AppEvents.MEMBER_FILTER_OPENED, closePanelForOtherSurface),
    on(AppEvents.FORM_MODE_CHANGED, ({ openForm }) => {
      if (openForm !== null) closePanelForOtherSurface();
    }),
    on(AppEvents.PANEL_SETTINGS_OPENED, ({ panel }) => {
      if (panel === "members") closePanelForOtherSurface();
    }),
    on(AppEvents.MOBILE_DECK_SWITCHED, ({ target }) => {
      if (DECK_LOSS_TARGETS.includes(target)) closePanelForDeckLoss();
    }),
    on(AppEvents.DECK_COLLAPSE_CHANGED, ({ deck, collapsed }) => {
      if (deck === "members" && collapsed) closePanelForDeckLoss();
    }),
  ];
  return () => disposers.forEach((dispose) => dispose());
}

function togglePanel(): void {
  if (_isOpen) {
    closePanelByUser();
    return;
  }
  openPanel();
}

function handlePanelKeydown(event: JQuery.KeyDownEvent): void {
  if (event.key !== "Escape") return;
  // No select exception: an Escape that closes a native dropdown never reaches
  // this handler. Consumed here so document-level Escape handlers never see it.
  event.preventDefault();
  event.stopPropagation();
  closePanelByUser();
}

// The gate flipped to false while the panel was open: close, with focus kept on
// a control that exists, and announce only when the UTub is still the one the
// panel opened for (a UTub switch or deselect is not a loss of rights).
function forceClosePanel(): void {
  const announce = getState().activeUTubID === _openedUTubID;
  _forcedClosedToken = _generation;
  withMemberControlFocusFallback({ write: teardownPanel });
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
 * Closes and clears the panel silently (UTub switch, deselect or rebuild):
 * body emptied, in-flight responses dropped, `aria-expanded="false"`. Also
 * clears the forced-close mark.
 */
export function resetInviteLinkPanel(): void {
  _forcedClosedToken = null;
  withMemberControlFocusFallback({ write: teardownPanel });
}

/**
 * Binds the trigger and the panel's Escape handler and subscribes the gate:
 * the trigger follows `canManageInviteLink`, and a flip to false closes an open
 * panel. Returns the unsubscribe function.
 */
export function initInviteLinkPanel(): () => void {
  $(TRIGGER_SELECTOR).off(".invitePanel").on("click.invitePanel", togglePanel);
  $(PANEL_SELECTOR)
    .off(".invitePanel")
    .on("keydown.invitePanel", handlePanelKeydown);
  syncInviteLinkTrigger();
  const unsubscribeBus = subscribeCrossFeatureExclusion();
  const unsubscribeStore = subscribe((changedKeys) => {
    if (!RELEVANT_KEYS.some((key) => changedKeys.includes(key))) return;
    withMemberControlFocusFallback({ write: syncInviteLinkTrigger });
    if (_isOpen && !canManageInviteLink()) forceClosePanel();
  });
  return () => {
    unsubscribeBus();
    unsubscribeStore();
  };
}
