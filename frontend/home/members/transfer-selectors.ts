// Single source of truth for the dedicated transfer-ownership modal's DOM
// contract (#transferOwnerModal and its pick/confirm sub-views + footer
// controls). Consumed by transfer.ts (modal lifecycle + confirm view + PATCH
// commit) and transfer-picker.ts (open trigger + pick view + selection). Keep
// these in lockstep with the modal markup in the Jinja template.

export const MODAL_SELECTOR = "#transferOwnerModal";
export const PICK_VIEW_SELECTOR = "#transferOwnerPickView";
export const CONFIRM_VIEW_SELECTOR = "#transferOwnerConfirmView";
export const TITLE_SELECTOR = "#transferOwnerModalTitle";
export const FOOTER_MSG_SELECTOR = "#transferOwnerFooterMsg";
export const CANCEL_BTN_SELECTOR = "#transferOwnerCancel";
export const SUBMIT_BTN_SELECTOR = "#transferOwnerSubmit";
