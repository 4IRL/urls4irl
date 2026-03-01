const _handlers = new Map();

export const AppEvents = Object.freeze({
  UTUB_SELECTED: "utub:selected",
  UTUB_DELETED: "utub:deleted",
  TAG_FILTER_CHANGED: "tag:filter-changed",
  TAG_DELETED: "tag:deleted",
  STALE_DATA_DETECTED: "stale-data:detected",
});

export function on(event, handler) {
  if (!_handlers.has(event)) _handlers.set(event, new Set());
  _handlers.get(event).add(handler);
  return () => off(event, handler);
}

export function off(event, handler) {
  _handlers.get(event)?.delete(handler);
}

export function emit(event, payload) {
  _handlers.get(event)?.forEach((handler) => handler(payload));
}
