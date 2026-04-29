import { applyDeckDiff } from "../apply-deck-diff.js";
import { diffIDLists } from "../deck-diffing.js";

vi.mock("../deck-diffing.js", () => ({
  diffIDLists: vi.fn(),
}));

const $ = window.jQuery;

interface TestItem {
  id: number;
  label: string;
}

describe("applyDeckDiff", () => {
  beforeEach(() => {
    vi.mocked(diffIDLists).mockReset();
    document.body.innerHTML = `<div id="container"></div>`;
  });

  it("removes DOM elements for IDs in toRemove", () => {
    document.body.innerHTML = `
      <div id="container">
        <div data-id="1"></div>
        <div data-id="2"></div>
        <div data-id="3"></div>
      </div>
    `;
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [2],
      toAdd: [],
      toUpdate: [],
    });

    const oldItems: TestItem[] = [
      { id: 1, label: "one" },
      { id: 2, label: "two" },
      { id: 3, label: "three" },
    ];
    const newItems: TestItem[] = [
      { id: 1, label: "one" },
      { id: 3, label: "three" },
    ];

    applyDeckDiff<TestItem>({
      oldItems,
      newItems,
      getID: (item) => item.id,
      removeElement: (id) => $(`[data-id="${id}"]`).remove(),
      addElement: () => {},
    });

    expect(document.querySelector('[data-id="2"]')).toBeNull();
    expect(document.querySelector('[data-id="1"]')).not.toBeNull();
    expect(document.querySelector('[data-id="3"]')).not.toBeNull();
  });

  it("adds DOM elements for IDs in toAdd", () => {
    document.body.innerHTML = `
      <div id="container">
        <div data-id="1"></div>
      </div>
    `;
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [2, 3],
      toUpdate: [],
    });

    const oldItems: TestItem[] = [{ id: 1, label: "one" }];
    const newItems: TestItem[] = [
      { id: 1, label: "one" },
      { id: 2, label: "two" },
      { id: 3, label: "three" },
    ];

    applyDeckDiff<TestItem>({
      oldItems,
      newItems,
      getID: (item) => item.id,
      removeElement: () => {},
      addElement: (item) =>
        $("#container").append(`<div data-id="${item.id}"></div>`),
    });

    expect(document.querySelector('[data-id="2"]')).not.toBeNull();
    expect(document.querySelector('[data-id="3"]')).not.toBeNull();
  });

  it("calls updateElement callback for IDs in toUpdate when provided", () => {
    document.body.innerHTML = `
      <div id="container">
        <div data-id="1"></div>
        <div data-id="2"></div>
      </div>
    `;
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [],
      toUpdate: [1, 2],
    });

    const oldItems: TestItem[] = [
      { id: 1, label: "one" },
      { id: 2, label: "two" },
    ];
    const newItems: TestItem[] = [
      { id: 1, label: "one-new" },
      { id: 2, label: "two-new" },
    ];

    const updateElement = vi.fn();

    applyDeckDiff<TestItem>({
      oldItems,
      newItems,
      getID: (item) => item.id,
      removeElement: () => {},
      addElement: () => {},
      updateElement,
    });

    expect(updateElement).toHaveBeenCalledTimes(2);
    expect(updateElement).toHaveBeenCalledWith(1, { id: 1, label: "one-new" });
    expect(updateElement).toHaveBeenCalledWith(2, { id: 2, label: "two-new" });
  });

  it("skips update when no updateElement callback provided", () => {
    document.body.innerHTML = `
      <div id="container">
        <div data-id="1"></div>
      </div>
    `;
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [],
      toUpdate: [1],
    });

    const oldItems: TestItem[] = [{ id: 1, label: "one" }];
    const newItems: TestItem[] = [{ id: 1, label: "one-new" }];

    expect(() => {
      applyDeckDiff<TestItem>({
        oldItems,
        newItems,
        getID: (item) => item.id,
        removeElement: () => {},
        addElement: () => {},
      });
    }).not.toThrow();

    expect(document.querySelector('[data-id="1"]')).not.toBeNull();
  });

  it("handles empty old and new lists", () => {
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [],
      toUpdate: [],
    });

    const removeElement = vi.fn();
    const addElement = vi.fn();
    const updateElement = vi.fn();

    expect(() => {
      applyDeckDiff<TestItem>({
        oldItems: [],
        newItems: [],
        getID: (item) => item.id,
        removeElement,
        addElement,
        updateElement,
      });
    }).not.toThrow();

    expect(removeElement).not.toHaveBeenCalled();
    expect(addElement).not.toHaveBeenCalled();
    expect(updateElement).not.toHaveBeenCalled();
  });

  it("skips addElement when toAdd ID is not found in newItems", () => {
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [999],
      toUpdate: [],
    });

    const oldItems: TestItem[] = [];
    const newItems: TestItem[] = [{ id: 1, label: "one" }];
    const addElement = vi.fn();

    applyDeckDiff<TestItem>({
      oldItems,
      newItems,
      getID: (item) => item.id,
      removeElement: () => {},
      addElement,
    });

    expect(addElement).not.toHaveBeenCalled();
  });

  it("skips updateElement when toUpdate ID is not found in newItems", () => {
    vi.mocked(diffIDLists).mockReturnValue({
      toRemove: [],
      toAdd: [],
      toUpdate: [999],
    });

    const oldItems: TestItem[] = [{ id: 1, label: "one" }];
    const newItems: TestItem[] = [{ id: 1, label: "one-new" }];
    const updateElement = vi.fn();

    applyDeckDiff<TestItem>({
      oldItems,
      newItems,
      getID: (item) => item.id,
      removeElement: () => {},
      addElement: () => {},
      updateElement,
    });

    expect(updateElement).not.toHaveBeenCalled();
  });
});
