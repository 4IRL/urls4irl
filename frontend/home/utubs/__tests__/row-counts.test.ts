import { getState, resetStore, setState } from "../../../store/app-store.js";
import { makeUtubSummaryItem } from "../../../__tests__/helpers/utub-summary.js";
import { makeUTubRowCounts } from "../selectors.js";
import {
  applyRowCountDelta,
  makeUTubRowCountsLabel,
  setRowCountsFromStore,
} from "../row-counts.js";

const $ = window.jQuery;

function seedRow({
  id,
  urlCount,
  memberCount,
}: {
  id: number;
  urlCount: number;
  memberCount: number;
}): void {
  document.body.innerHTML = `<div id="listUTubs"><span class="UTubSelector" utubid="${id}"></span></div>`;
  $(".UTubSelector").append(makeUTubRowCounts({ urlCount, memberCount }));
  setState({
    utubs: [makeUtubSummaryItem({ id, urlCount, memberCount })],
  });
}

function rowNumbers(): string[] {
  return $(".UTubRowCountNum")
    .map((_, element) => $(element).text())
    .get();
}

beforeEach(() => {
  resetStore();
});

describe("applyRowCountDelta", () => {
  it("a URL insert adds one and updates the number and hidden label", () => {
    seedRow({ id: 5, urlCount: 2, memberCount: 3 });

    applyRowCountDelta({ utubID: 5, urlDelta: 1, memberDelta: 0 });

    expect(getState().utubs[0].urlCount).toBe(3);
    expect(rowNumbers()).toEqual(["3", "3"]);
    expect($(".UTubRowCounts .visually-hidden").text()).toBe(
      makeUTubRowCountsLabel({ urlCount: 3, memberCount: 3 }),
    );
  });

  it("a single URL delete subtracts one", () => {
    seedRow({ id: 5, urlCount: 2, memberCount: 3 });
    applyRowCountDelta({ utubID: 5, urlDelta: -1, memberDelta: 0 });
    expect(rowNumbers()).toEqual(["1", "3"]);
  });

  it("a member add and remove move the member count", () => {
    seedRow({ id: 5, urlCount: 2, memberCount: 3 });
    applyRowCountDelta({ utubID: 5, urlDelta: 0, memberDelta: 1 });
    expect(rowNumbers()).toEqual(["2", "4"]);
    applyRowCountDelta({ utubID: 5, urlDelta: 0, memberDelta: -1 });
    expect(rowNumbers()).toEqual(["2", "3"]);
    expect(getState().utubs[0].memberCount).toBe(3);
  });

  it("a bulk delete subtracts the number deleted", () => {
    seedRow({ id: 5, urlCount: 5, memberCount: 1 });
    applyRowCountDelta({ utubID: 5, urlDelta: -3, memberDelta: 0 });
    expect(rowNumbers()).toEqual(["2", "1"]);
  });

  it("restore then delete composes: N live URLs end at N, not N-1", () => {
    seedRow({ id: 5, urlCount: 4, memberCount: 1 });
    // The restore adds a URL that store.urls does not hold yet.
    applyRowCountDelta({ utubID: 5, urlDelta: 1, memberDelta: 0 });
    expect(rowNumbers()[0]).toBe("5");
    applyRowCountDelta({ utubID: 5, urlDelta: -1, memberDelta: 0 });
    expect(rowNumbers()[0]).toBe("4");
  });

  it("never goes below zero", () => {
    seedRow({ id: 5, urlCount: 0, memberCount: 1 });
    applyRowCountDelta({ utubID: 5, urlDelta: -1, memberDelta: 0 });
    expect(rowNumbers()[0]).toBe("0");
  });

  it("leaves other rows and unknown ids untouched", () => {
    seedRow({ id: 5, urlCount: 2, memberCount: 3 });
    applyRowCountDelta({ utubID: 99, urlDelta: 1, memberDelta: 1 });
    expect(rowNumbers()).toEqual(["2", "3"]);
    expect(getState().utubs[0].urlCount).toBe(2);
  });
});

describe("setRowCountsFromStore", () => {
  it("corrects a stale summary count from the loaded urls and members", () => {
    seedRow({ id: 5, urlCount: 9, memberCount: 9 });
    setState({
      urls: [{ utubUrlID: 1 }, { utubUrlID: 2 }] as never,
      members: [{ id: 1 }] as never,
    });

    setRowCountsFromStore({ utubID: 5 });

    expect(rowNumbers()).toEqual(["2", "1"]);
    expect(getState().utubs[0].urlCount).toBe(2);
    expect(getState().utubs[0].memberCount).toBe(1);
  });

  it("does not reorder the list", () => {
    document.body.innerHTML = `<div id="listUTubs"><span class="UTubSelector" utubid="2"></span><span class="UTubSelector" utubid="1"></span></div>`;
    setState({
      utubs: [makeUtubSummaryItem({ id: 2 }), makeUtubSummaryItem({ id: 1 })],
    });

    setRowCountsFromStore({ utubID: 1 });

    expect(getState().utubs.map((utub) => utub.id)).toEqual([2, 1]);
    expect(
      $(".UTubSelector")
        .map((_, element) => $(element).attr("utubid"))
        .get(),
    ).toEqual(["2", "1"]);
  });
});
