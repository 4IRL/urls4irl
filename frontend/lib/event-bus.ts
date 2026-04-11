export interface UtubSelectedPayload {
  utubID: number;
  utubName: string;
  urls: unknown[];
  tags: unknown[];
  members: unknown[];
  utubOwnerID: number;
  isCurrentUserOwner: boolean;
  currentUserID: number;
}

export interface StaleDataDetectedPayload {
  utubID: number;
  urls: unknown[];
  tags: unknown[];
  members: unknown[];
}

export interface AppEventMap {
  "utub:selected": UtubSelectedPayload;
  "utub:deleted": { utubID: number };
  "tag:filter-changed": { selectedTagIDs: number[] };
  "tag:deleted": { utubTagID: number };
  "stale-data:detected": StaleDataDetectedPayload;
}

export const AppEvents = Object.freeze({
  UTUB_SELECTED: "utub:selected",
  UTUB_DELETED: "utub:deleted",
  TAG_FILTER_CHANGED: "tag:filter-changed",
  TAG_DELETED: "tag:deleted",
  STALE_DATA_DETECTED: "stale-data:detected",
} as const);

const _handlers = new Map<string, Set<(payload: unknown) => void>>();

export function on<K extends keyof AppEventMap>(
  event: K,
  handler: (payload: AppEventMap[K]) => void,
): () => void {
  if (!_handlers.has(event)) _handlers.set(event, new Set());
  _handlers.get(event)!.add(handler as (payload: unknown) => void);
  return () => off(event, handler);
}

export function off<K extends keyof AppEventMap>(
  event: K,
  handler: (payload: AppEventMap[K]) => void,
): void {
  _handlers.get(event)?.delete(handler as (payload: unknown) => void);
}

export function emit<K extends keyof AppEventMap>(
  event: K,
  payload: AppEventMap[K],
): void {
  _handlers.get(event)?.forEach((handler) => handler(payload));
}
