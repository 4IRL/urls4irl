import { $ } from "../../lib/globals.js";
import { createURLShowInput } from "./cards/create.js";

export function createURLShowInputEventListeners(utubID: number): void {
  /* Bind click functions */
  const urlBtnCreateSelector = "#urlBtnCreate";
  const urlBtnDeckCreateSelector = "#urlBtnDeckCreate";
  const urlBtnCreate = $(urlBtnCreateSelector);
  const urlBtnDeckCreate = $(urlBtnDeckCreateSelector);

  // Add new URL to current UTub
  urlBtnCreate.offAndOnExact("click", function () {
    createURLShowInput(utubID);
  });
  urlBtnDeckCreate.offAndOnExact("click", function () {
    createURLShowInput(utubID);
  });
}
