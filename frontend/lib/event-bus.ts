import type { MemberItem } from "../types/member.js";
import type { UtubUrlItem, UtubTag } from "../types/url.js";

export interface UtubSelectedPayload {
  utubID: number;
  utubName: string;
  urls: UtubUrlItem[];
  tags: UtubTag[];
  members: MemberItem[];
  utubOwnerID: number;
  isCurrentUserOwner: boolean;
  currentUserID: number;
}

export interface StaleDataDetectedPayload {
  utubID: number;
  urls: UtubUrlItem[];
  tags: UtubTag[];
  members: MemberItem[];
}

export interface AppEventMap {
  "utub:selected": UtubSelectedPayload;
  "utub:deleted": { utubID: number };
  "url:card-selected": { urlID: number };
  "url:deck-changed": void;
  "tag:filter-changed": { selectedTagIDs: number[] };
  "tag:deleted": { utubTagID: number };
  "stale-data:detected": StaleDataDetectedPayload;
  "url-search:visibility-changed": void;
  "url:tag-filter-applied": void;
  "cross-utub-search:visibility-changed": { active: boolean };
  "mobile:deck-switched": {
    target: "desktop" | "url-deck" | "utub-deck" | "member-deck" | "no-utub";
  };
  "data-export:status-changed": { message: string };
  "url:multiselect-mode-changed": { active: boolean };
  "url:multiselect-changed": { selectedURLCardIDs: number[] };
  "member-filter:opened": void;
  "member-filter:changed": void;
  "member-add:opened": void;
  "transfer-picker:requested": { opener: HTMLElement | string };
}

export const AppEvents = Object.freeze({
  UTUB_SELECTED: "utub:selected",
  UTUB_DELETED: "utub:deleted",
  URL_CARD_SELECTED: "url:card-selected",
  URL_DECK_CHANGED: "url:deck-changed",
  TAG_FILTER_CHANGED: "tag:filter-changed",
  TAG_DELETED: "tag:deleted",
  STALE_DATA_DETECTED: "stale-data:detected",
  URL_SEARCH_VISIBILITY_CHANGED: "url-search:visibility-changed",
  URL_TAG_FILTER_APPLIED: "url:tag-filter-applied",
  CROSS_UTUB_SEARCH_VISIBILITY_CHANGED: "cross-utub-search:visibility-changed",
  MOBILE_DECK_SWITCHED: "mobile:deck-switched",
  DATA_EXPORT_STATUS_CHANGED: "data-export:status-changed",
  URL_MULTISELECT_MODE_CHANGED: "url:multiselect-mode-changed",
  URL_MULTISELECT_CHANGED: "url:multiselect-changed",
  MEMBER_FILTER_OPENED: "member-filter:opened",
  MEMBER_FILTER_CHANGED: "member-filter:changed",
  MEMBER_ADD_OPENED: "member-add:opened",
  TRANSFER_PICKER_REQUESTED: "transfer-picker:requested",
} as const);

const _handlers = new Map<string, Set<(payload: unknown) => void>>();

export function on<K extends keyof AppEventMap>(
  event: K,
  handler: AppEventMap[K] extends void
    ? () => void
    : (payload: AppEventMap[K]) => void,
): () => void {
  if (!_handlers.has(event)) _handlers.set(event, new Set());
  _handlers.get(event)!.add(handler as (payload: unknown) => void);
  return () => off(event, handler);
}

export function off<K extends keyof AppEventMap>(
  event: K,
  handler: AppEventMap[K] extends void
    ? () => void
    : (payload: AppEventMap[K]) => void,
): void {
  _handlers.get(event)?.delete(handler as (payload: unknown) => void);
}

export function emit<K extends keyof AppEventMap>(
  event: K,
  ...args: AppEventMap[K] extends void ? [] : [AppEventMap[K]]
): void {
  _handlers.get(event)?.forEach((handler) => handler(args[0]));
}
