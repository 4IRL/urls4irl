import { initClickableRows } from "../clickable-rows.js";

const $ = window.jQuery;

const ROW_HREF = "/admin/utubs/42";

const CLICKABLE_ROW_HTML = `
  <table>
    <tbody>
      <tr class="admin-clickable-row" data-row-href="${ROW_HREF}">
        <td>
          <a id="RowIdLink" class="admin-db-row-link" href="${ROW_HREF}">42</a>
        </td>
        <td id="PlainCell">Some UTub Name</td>
        <td><button id="RowButton" type="button">Do</button></td>
      </tr>
    </tbody>
  </table>
`;

let assignMock: ReturnType<typeof vi.fn>;

describe("clickable-rows whole-row navigation controller", () => {
  beforeEach(() => {
    document.body.innerHTML = CLICKABLE_ROW_HTML;
    assignMock = vi.fn();
    Object.defineProperty(window, "location", {
      value: { assign: assignMock },
      writable: true,
    });
    initClickableRows();
  });

  it("navigates to the row's data-row-href when a plain cell is clicked", () => {
    $("#PlainCell").trigger("click");

    expect(assignMock).toHaveBeenCalledTimes(1);
    expect(assignMock).toHaveBeenCalledWith(ROW_HREF);
  });

  it("does not navigate when an inner link is clicked", () => {
    $("#RowIdLink").trigger("click");

    expect(assignMock).not.toHaveBeenCalled();
  });

  it("does not navigate when an inner button is clicked", () => {
    $("#RowButton").trigger("click");

    expect(assignMock).not.toHaveBeenCalled();
  });

  it("does not navigate when there is an active text selection", () => {
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "highlighted text",
    } as unknown as Selection);

    $("#PlainCell").trigger("click");

    expect(assignMock).not.toHaveBeenCalled();
  });

  it("navigates for a clickable row swapped in AFTER init (search-driven page)", () => {
    // No active text selection (a prior test may have stubbed getSelection).
    vi.spyOn(window, "getSelection").mockReturnValue({
      toString: () => "",
    } as unknown as Selection);

    // The User Actions page loads with no results, so initClickableRows runs
    // before any clickable row exists. Delegation must still cover rows that a
    // later search swaps in.
    document.body.innerHTML = "";
    initClickableRows();

    const swappedHref = "/admin/users/7";
    document.body.innerHTML = `
      <table><tbody>
        <tr class="admin-clickable-row" data-row-href="${swappedHref}">
          <td id="SwappedCell">u4i_test7</td>
        </tr>
      </tbody></table>`;

    $("#SwappedCell").trigger("click");

    expect(assignMock).toHaveBeenCalledTimes(1);
    expect(assignMock).toHaveBeenCalledWith(swappedHref);
  });
});
