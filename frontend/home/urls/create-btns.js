import { $ } from "../../lib/globals.js";
import { createURLShowInput } from "./cards/create.js";

export function createURLShowInputEventListeners(utubID) {
  /* Bind click functions */
  const urlBtnCreateSelector = "#urlBtnCreate";
  const urlBtnDeckCreateSelector = "#urlBtnDeckCreate";
  const urlBtnCreate = $(urlBtnCreateSelector);
  const urlBtnDeckCreate = $(urlBtnDeckCreateSelector);

  // Add new URL to current UTub
  urlBtnCreate.offAndOnExact("click", function (e) {
    createURLShowInput(utubID);
  });
  urlBtnDeckCreate.offAndOnExact("click", function (e) {
    createURLShowInput(utubID);
  });
}
