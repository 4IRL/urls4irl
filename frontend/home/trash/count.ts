import { $ } from "../../lib/globals.js";
import { debug } from "../../lib/debug.js";
import { getState, setState } from "../../store/app-store.js";
import { getAllUTubs } from "../utubs/utils.js";

const log = debug("trash:count");

const TRASH_COUNT_DATA_ID = "trash-count-data";
const TRASH_COUNT_ID = "TrashSelectorCount";

/** Seeds the store's `trashCount` from the server-rendered #trash-count-data tag. */
export function loadInitialTrashCount(): void {
  const countScript = document.getElementById(TRASH_COUNT_DATA_ID);
  if (countScript === null) {
    log("trash-count-data element missing — count stays 0");
    return;
  }
  const parsed = Number(JSON.parse(countScript.textContent ?? "0"));
  setState({ trashCount: Number.isFinite(parsed) ? parsed : 0 });
}

/**
 * Writes `(n)` into the Trash entry. The entry's accessible name comes from its
 * content ("Trash (n)"), so no hardcoded aria-label string is needed.
 */
export function renderTrashCount(): void {
  $(`#${TRASH_COUNT_ID}`).text(`(${getState().trashCount})`);
}

/**
 * Re-reads the authoritative count from `GET /utubs`. A failed fetch keeps the
 * count already shown.
 */
export function refreshTrashCount(): Promise<void> {
  return new Promise((resolve) => {
    getAllUTubs()
      .done((response) => {
        setState({ trashCount: response.trashCount });
        renderTrashCount();
      })
      .fail((xhr: JQuery.jqXHR) => {
        log("refreshTrashCount failed — keeping the old count", {
          status: xhr.status,
        });
      })
      .always(() => resolve());
  });
}
