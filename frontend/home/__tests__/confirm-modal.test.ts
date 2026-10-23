import { showConfirmModal, hideConfirmModal } from "../confirm-modal.js";

const $ = window.jQuery;

describe("confirm-modal", () => {
  let modalMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    document.body.innerHTML = `
      <div id="confirmModal" class="modal">
        <h5 id="confirmModalTitle"></h5>
        <p id="confirmModalBody"></p>
        <button id="modalSubmit" class="btn btn-primary"></button>
        <button id="modalDismiss"></button>
        <a id="modalRedirect"></a>
      </div>`;
    modalMock = vi.fn().mockReturnThis();
    ($.fn as unknown as Record<string, unknown>).modal = modalMock;
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  function show(
    namespace: "trashPurge" | "trashEmpty" | "shortLinkRevoke",
    onConfirm: () => void,
  ): void {
    showConfirmModal({
      title: "Title",
      body: "Body",
      submitLabel: "Go",
      namespace,
      onConfirm,
    });
  }

  it("fills the modal, resets the submit class and shows it", () => {
    show("shortLinkRevoke", vi.fn());

    expect($("#confirmModalTitle").text()).toBe("Title");
    expect($("#confirmModalBody").text()).toBe("Body");
    expect($("#modalSubmit").text()).toBe("Go");
    expect($("#modalSubmit").attr("class")).toBe("btn btn-danger");
    expect(modalMock).toHaveBeenCalledWith("show");
  });

  it("calls onConfirm when the submit button is clicked", () => {
    const onConfirm = vi.fn();
    show("trashPurge", onConfirm);

    $("#modalSubmit").trigger("click");

    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("hides the modal when dismiss is clicked", () => {
    show("trashPurge", vi.fn());

    $("#modalDismiss").trigger("click");

    expect(modalMock).toHaveBeenCalledWith("hide");
  });

  it("self-unbinds its handlers when the modal is hidden", () => {
    const onConfirm = vi.fn();
    show("shortLinkRevoke", onConfirm);

    $("#confirmModal").trigger("hidden.bs.modal");
    $("#modalSubmit").trigger("click");

    expect(onConfirm).not.toHaveBeenCalled();
  });

  it("does not leak one namespace's handlers into another flow", () => {
    const trashConfirm = vi.fn();
    const revokeConfirm = vi.fn();
    show("trashPurge", trashConfirm);
    $("#confirmModal").trigger("hidden.bs.modal");

    show("shortLinkRevoke", revokeConfirm);
    $("#modalSubmit").trigger("click");

    expect(revokeConfirm).toHaveBeenCalledTimes(1);
    expect(trashConfirm).not.toHaveBeenCalled();
  });

  it("hideConfirmModal hides the modal", () => {
    hideConfirmModal();

    expect(modalMock).toHaveBeenCalledWith("hide");
  });
});
