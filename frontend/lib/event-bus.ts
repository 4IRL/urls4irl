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
  "tag:filter-changed": { selectedTagIDs: number[] };
  "tag:deleted": { utubTagID: number };
  "stale-data:detected": StaleDataDetectedPayload;
  "url-search:visibility-changed": void;
  "url:tag-filter-applied": void;
}

export const AppEvents = Object.freeze({
  UTUB_SELECTED: "utub:selected",
  UTUB_DELETED: "utub:deleted",
  TAG_FILTER_CHANGED: "tag:filter-changed",
  TAG_DELETED: "tag:deleted",
  STALE_DATA_DETECTED: "stale-data:detected",
  URL_SEARCH_VISIBILITY_CHANGED: "url-search:visibility-changed",
  URL_TAG_FILTER_APPLIED: "url:tag-filter-applied",
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
