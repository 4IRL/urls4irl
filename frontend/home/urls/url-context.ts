import { $ } from "../../lib/globals.js";
import { getState } from "../../store/app-store.js";

// Pure DOM/state readers exposing URL-deck context to metrics emit sites.
// Centralized so dim derivations remain one-line and grep-able from every URL
// emit-call site (corner-access, url-string, access-btn, update-string,
// selection, cards).

export function isURLSearchActive(): boolean {
  return $("#SearchURLWrap").hasClass("visible-flex");
}

export function getActiveTagCount(): number {
  return getState().selectedTagIDs.length;
}
