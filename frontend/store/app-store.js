function createInitialState() {
  return {
    utubs: [],
    activeUTubID: null,
    activeUTubName: null,
    activeUTubDescription: null,
    isCurrentUserOwner: false,
    currentUserID: null,
    utubOwnerID: null,
    selectedURLCardID: null,
    selectedTagIDs: [],
    urls: [],
    tags: [],
    members: [],
  };
}

let _state = createInitialState();

/** Returns a shallow copy of the current state. */
export function getState() {
  return { ..._state };
}

/** Merges partial into state. */
export function setState(partial) {
  Object.assign(_state, partial);
}

/** Resets to initial state (for tests). */
export function resetStore() {
  _state = createInitialState();
}
