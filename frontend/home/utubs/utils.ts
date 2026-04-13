import type { operations } from "../../types/api.d.ts";
import type { UtubSummaryItem } from "../../types/utub.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { getState } from "../../store/app-store.js";
import {
  showUTubLoadingIconAndSetTimeout,
  hideUTubLoadingIconAndClearTimeout,
} from "./deck.js";

type GetUtubsResponse =
  operations["getUtubs"]["responses"][200]["content"]["application/json"];

// Verify UTubID is valid
export function isValidUTubID(utubIdStr: string | null): boolean {
  if (utubIdStr === null) return false;
  const utubId = parseInt(utubIdStr);
  const isANumber = !isNaN(utubId);
  const isPositive = utubId > 0;
  const isValidIntegerFormat = String(utubId) === utubIdStr;

  return isANumber && isPositive && isValidIntegerFormat;
}

export function isUtubIdValidOnPageLoad(utubId: string): boolean {
  return isUtubIdValidFromStateAccess(utubId);
}

export function isUtubIdValidFromStateAccess(utubId: number | string): boolean {
  return $(`.UTubSelector[utubid='${utubId}']`).length === 1;
}

// Function to count number of UTubs current user has access to
export function getNumOfUTubs(): number {
  return $("#listUTubs > .UTubSelector").length;
}

// Streamline extraction of UTub ID
export function getActiveUTubID(): number | null {
  return getState().activeUTubID;
}

// Check if a UTub is selected
export function isUTubSelected(): boolean {
  return getState().activeUTubID !== null;
}

// Streamline the jQuery selector extraction of UTub name.
export function getCurrentUTubName(): string | null {
  return getState().activeUTubName;
}

// Quickly extracts all UTub names and returns an array.
export function getAllAccessibleUTubNames(): string[] {
  return getState().utubs.map((utub: UtubSummaryItem) => utub.name);
}

// Utility route to get all UTub summaries
export function getAllUTubs(): JQuery.Promise<GetUtubsResponse> {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  return $.getJSON(APP_CONFIG.routes.getUTubs).always(function () {
    hideUTubLoadingIconAndClearTimeout(timeoutID);
  });
}

// Hides modal for UTub same name action confirmation
export function sameNameWarningHideModal(): void {
  $("#confirmModal").modal("hide");
}
