// Shared jsdom fixture for the invite-link modal tests: the Members deck pieces
// the module touches plus #inviteLinkModal (mirrors modals/inviteLinkModal.html),
// and a synchronous stand-in for Bootstrap's jQuery `.modal()` plugin.

export const INVITE_MODAL_FIXTURE = `
  <div id="MemberDeck">
    <button id="MemberDeckHeaderAndCaret"></button>
    <button id="memberBtnInviteLink" class="hidden" aria-label="Invite link"
      title="Invite link" aria-haspopup="dialog"></button>
    <button id="memberBtnOverflow" class="hidden" aria-label="More member actions"></button>
    <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
  </div>
  <div class="modal fade" id="inviteLinkModal" tabindex="-1" role="dialog"
       aria-labelledby="inviteLinkModalTitle" aria-hidden="true">
    <div class="modal-dialog modal-dialog-centered">
      <div class="modal-content">
        <div class="modal-header">
          <h4 id="inviteLinkModalTitle" class="modal-title" tabindex="-1">Invite link</h4>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>
        <div class="modal-body"><div id="inviteLinkModalBody"></div></div>
      </div>
    </div>
  </div>
  <span id="MobilePanelAnnouncement" aria-live="polite"></span>
`;

type ModalPlugin = (this: JQuery, action: string) => JQuery;

/**
 * Installs a synchronous `.modal("show" | "hide")` that follows Bootstrap's event
 * order: show fires `shown.bs.modal`; hide fires a cancelable `hide.bs.modal`,
 * then `hidden.bs.modal`. The open state is the `show` class, like Bootstrap's.
 */
export function installModalMock(): void {
  const plugin: ModalPlugin = function (this: JQuery, action: string) {
    const isOpen = this.hasClass("show");
    if (action === "show" && !isOpen) {
      this.addClass("show").trigger("show.bs.modal").trigger("shown.bs.modal");
    } else if (action === "hide" && isOpen) {
      const hideEvent = window.jQuery.Event("hide.bs.modal");
      this.trigger(hideEvent);
      if (hideEvent.isDefaultPrevented()) return this;
      this.removeClass("show").trigger("hidden.bs.modal");
    }
    return this;
  };
  (window.jQuery.fn as unknown as Record<string, unknown>).modal = plugin;
}

export function isInviteModalShown(): boolean {
  return window.jQuery("#inviteLinkModal").hasClass("show");
}

/** What Bootstrap does on Escape, a backdrop click or a dismiss button: hide. */
export function dismissInviteModal(): void {
  (
    window.jQuery("#inviteLinkModal") as unknown as {
      modal: (action: string) => void;
    }
  ).modal("hide");
}
