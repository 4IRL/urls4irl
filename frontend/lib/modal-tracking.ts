import type { HomeForm } from "../types/metrics-dim-values.js";

// Auth-form ids tracked alongside the home forms. These mirror the
// `form: Literal["login", "register"]` dim on the backend `_DimAuthCancel`
// model so a navigation-cancel beacon for an auth form passes server-side
// validation.
export type AuthForm = "login" | "register";

// The full set of ids the open-form registry can hold: every home form plus
// the two auth forms. Each form's open handler passes the SAME id constant it
// uses for its `emit({ event: UI_FORM_CANCEL, form: ... })` payload so the
// navigation-cancel beacon scopes to the correct form.
export type OpenFormId = HomeForm | AuthForm;

// Module-scope registry tracking at most one currently-open form. This is a
// plain module variable (not a window global) so other modules read/write it
// only through the exported functions below — the same isolation pattern used
// by `app-store.ts`.
let _openForm: OpenFormId | null = null;

/** Records which form is currently open. Called by each form's open handler. */
export function setOpenForm(formId: OpenFormId): void {
  _openForm = formId;
}

/** Clears the open-form registry. Called on form submit or cancel. */
export function clearOpenForm(): void {
  _openForm = null;
}

/** Returns the currently-open form id, or `null` when no form is open. */
export function getOpenForm(): OpenFormId | null {
  return _openForm;
}
