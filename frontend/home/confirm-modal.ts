/**
 * The shared `#confirmModal` (title, body, destructive submit, cancel) used by
 * every "Are you sure?" flow that has no modal of its own: Trash purge/empty and
 * short-link revoke. The modal is one DOM node reused by all of them, so each flow
 * binds its handlers under its own `namespace` and they unbind themselves when
 * the modal closes, however it closes.
 */

import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";

const CONFIRM_MODAL = "#confirmModal";
const MODAL_SUBMIT = "#modalSubmit";
const MODAL_DISMISS = "#modalDismiss";
const MODAL_REDIRECT = "#modalRedirect";

export type ConfirmModalNamespace =
  | "trashPurge"
  | "trashEmpty"
  | "shortLinkRevoke";

export function showConfirmModal({
  title,
  body,
  submitLabel,
  namespace,
  onConfirm,
}: {
  title: string;
  body: string;
  submitLabel: string;
  namespace: ConfirmModalNamespace;
  onConfirm: () => void;
}): void {
  $("#confirmModalTitle").text(title);
  $("#confirmModalBody").text(body);

  // #confirmModal is shared: reset the submit class so a prior flow's styling
  // never leaks into this destructive confirm.
  $(MODAL_SUBMIT)
    .removeClass()
    .addClass("btn btn-danger")
    .text(submitLabel)
    .prop("disabled", false)
    .off(`click.${namespace}`)
    .on(`click.${namespace}`, (event: JQuery.TriggeredEvent) => {
      event.preventDefault();
      onConfirm();
    });

  $(MODAL_DISMISS)
    .text(APP_CONFIG.strings.URL_BULK_DELETE_CANCEL)
    .prop("disabled", false)
    .off(`click.${namespace}`)
    .on(`click.${namespace}`, (event: JQuery.TriggeredEvent) => {
      event.preventDefault();
      $(CONFIRM_MODAL).modal("hide");
    });

  // Self-unbinding: the modal is shared, so these handlers must only live for
  // this confirm session, whichever way it closes.
  $(CONFIRM_MODAL)
    .off(`hidden.bs.modal.${namespace}`)
    .on(`hidden.bs.modal.${namespace}`, () => {
      $(CONFIRM_MODAL).off(`hidden.bs.modal.${namespace}`);
      $(MODAL_SUBMIT).off(`click.${namespace}`);
      $(MODAL_DISMISS).off(`click.${namespace}`);
    });

  $(MODAL_REDIRECT).hide();
  $(CONFIRM_MODAL).modal("show");
}

export function hideConfirmModal(): void {
  $(CONFIRM_MODAL).modal("hide");
}
