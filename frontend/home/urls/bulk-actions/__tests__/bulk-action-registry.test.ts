import {
  type BulkAction,
  type BulkActionContext,
  getAvailableBulkActions,
  registerBulkAction,
  resetBulkActionRegistryForTest,
} from "../bulk-action-registry.js";

const CONTEXT: BulkActionContext = { selectedURLCardIDs: [1, 2], urls: [] };

function makeFakeAction(overrides: Partial<BulkAction> = {}): BulkAction {
  return {
    id: "fake",
    label: "Fake",
    isAvailable: () => true,
    onActivate: vi.fn(),
    ...overrides,
  };
}

describe("bulk-action-registry", () => {
  beforeEach(() => {
    resetBulkActionRegistryForTest();
  });

  it("returns [] when nothing is registered (Phase 1 default)", () => {
    expect(getAvailableBulkActions(CONTEXT)).toEqual([]);
  });

  it("returns a registered action whose isAvailable(ctx) is true", () => {
    const action = makeFakeAction();
    registerBulkAction(action);
    expect(getAvailableBulkActions(CONTEXT)).toEqual([action]);
  });

  it("omits a registered action whose isAvailable(ctx) is false", () => {
    const available = makeFakeAction({ id: "yes", isAvailable: () => true });
    const unavailable = makeFakeAction({ id: "no", isAvailable: () => false });
    registerBulkAction(available);
    registerBulkAction(unavailable);
    expect(getAvailableBulkActions(CONTEXT)).toEqual([available]);
  });
});
