import { beforeEach, describe, expect, it, vi } from "vitest";

import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import {
  INVITE_LINK_TIMEOUT_MS,
  createInviteLink,
  getInviteLink,
  replaceInviteLink,
  revokeInviteLink,
  updateInviteLink,
} from "../invite-link-client.js";

const LINK = { inviteLink: { token: "abc" } };

function stubDone(response: unknown): void {
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      done: (callback: unknown) => (callback as (r: unknown) => void)(response),
    }),
  );
}

function stubFail(xhr: Record<string, unknown>): void {
  vi.mocked(ajaxCall).mockReturnValue(
    createMockJqXHRChainable({
      fail: (callback: unknown) => (callback as (x: unknown) => void)(xhr),
    }),
  );
}

function makeXhr({
  status,
  contentType = "application/json",
  json,
  text = "",
}: {
  status: number;
  contentType?: string;
  json?: unknown;
  text?: string;
}): Record<string, unknown> {
  return {
    status,
    responseJSON: json,
    responseText: text,
    getResponseHeader: () => contentType,
  };
}

describe("invite-link-client request shapes", () => {
  beforeEach(() => {
    vi.mocked(ajaxCall).mockReset();
    vi.mocked(is429Handled).mockReset();
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  it("createInviteLink POSTs both settings", async () => {
    stubDone(LINK);
    await createInviteLink({ utubID: 1, expiresInDays: 7, maxUses: null });
    expect(ajaxCall).toHaveBeenCalledWith(
      "post",
      "/utubs/1/invite-link",
      { expires_in_days: 7, max_uses: null },
      INVITE_LINK_TIMEOUT_MS,
    );
  });

  it("replaceInviteLink POSTs both settings to the replace route", async () => {
    stubDone(LINK);
    await replaceInviteLink({ utubID: 1, expiresInDays: 30, maxUses: 5 });
    expect(ajaxCall).toHaveBeenCalledWith(
      "post",
      "/utubs/1/invite-link/replace",
      { expires_in_days: 30, max_uses: 5 },
      INVITE_LINK_TIMEOUT_MS,
    );
  });

  it("updateInviteLink PATCHes exactly the given body", async () => {
    stubDone(LINK);
    await updateInviteLink({ utubID: 1, body: { max_uses: 3 } });
    expect(ajaxCall).toHaveBeenCalledWith(
      "patch",
      "/utubs/1/invite-link",
      { max_uses: 3 },
      INVITE_LINK_TIMEOUT_MS,
    );
  });

  it("revokeInviteLink DELETEs with no body and resolves true", async () => {
    stubDone({});
    await expect(revokeInviteLink({ utubID: 1 })).resolves.toBe(true);
    expect(ajaxCall).toHaveBeenCalledWith(
      "delete",
      "/utubs/1/invite-link",
      null,
      INVITE_LINK_TIMEOUT_MS,
    );
  });

  it("getInviteLink GETs with no body", async () => {
    stubDone({ inviteLink: null });
    await expect(getInviteLink({ utubID: 1 })).resolves.toBeNull();
    expect(ajaxCall).toHaveBeenCalledWith(
      "get",
      "/utubs/1/invite-link",
      null,
      INVITE_LINK_TIMEOUT_MS,
    );
  });
});

describe("invite-link-client getInviteLink failure mapping", () => {
  beforeEach(() => {
    vi.mocked(ajaxCall).mockReset();
    vi.mocked(is429Handled).mockReset();
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  it.each([403, 404])(
    "maps %i to denied with the errorCode",
    async (status) => {
      stubFail(makeXhr({ status, json: { errorCode: 3 } }));
      await expect(getInviteLink({ utubID: 1 })).rejects.toEqual({
        kind: "denied",
        errorCode: 3,
      });
    },
  );

  it("maps a denied response without a code to errorCode null", async () => {
    stubFail(makeXhr({ status: 403 }));
    await expect(getInviteLink({ utubID: 1 })).rejects.toEqual({
      kind: "denied",
      errorCode: null,
    });
  });

  it("maps a handled 429 to rate_limited", async () => {
    vi.mocked(is429Handled).mockReturnValue(true);
    stubFail(makeXhr({ status: 429 }));
    await expect(getInviteLink({ utubID: 1 })).rejects.toEqual({
      kind: "rate_limited",
    });
  });

  it("maps a 500 to failed", async () => {
    stubFail(makeXhr({ status: 500 }));
    await expect(getInviteLink({ utubID: 1 })).rejects.toEqual({
      kind: "failed",
    });
  });

  it.each([["<html>"], [null], [{}]])(
    "maps a 200 without inviteLink (%j) to failed",
    async (response) => {
      stubDone(response);
      await expect(getInviteLink({ utubID: 1 })).rejects.toEqual({
        kind: "failed",
      });
    },
  );
});

describe("invite-link-client mutation failure mapping", () => {
  beforeEach(() => {
    vi.mocked(ajaxCall).mockReset();
    vi.mocked(is429Handled).mockReset();
    vi.mocked(is429Handled).mockReturnValue(false);
  });

  it("maps a handled 429 to rate_limited", async () => {
    vi.mocked(is429Handled).mockReturnValue(true);
    stubFail(makeXhr({ status: 429 }));
    await expect(revokeInviteLink({ utubID: 1 })).rejects.toEqual({
      kind: "rate_limited",
    });
  });

  it("maps a 403 HTML page to csrf with the html", async () => {
    stubFail(
      makeXhr({
        status: 403,
        contentType: "text/html; charset=utf-8",
        text: "<p>csrf</p>",
      }),
    );
    await expect(
      createInviteLink({ utubID: 1, expiresInDays: 1, maxUses: null }),
    ).rejects.toEqual({ kind: "csrf", html: "<p>csrf</p>" });
  });

  it("maps a JSON 403 to an error with status and errorCode", async () => {
    stubFail(makeXhr({ status: 403, json: { errorCode: 3 } }));
    await expect(revokeInviteLink({ utubID: 1 })).rejects.toEqual({
      kind: "error",
      status: 403,
      errorCode: 3,
    });
  });

  it("maps a timeout (status 0) to an error", async () => {
    stubFail(makeXhr({ status: 0 }));
    await expect(revokeInviteLink({ utubID: 1 })).rejects.toEqual({
      kind: "error",
      status: 0,
      errorCode: null,
    });
  });

  it("maps a 200 without inviteLink or a non-JSON 200 to error status 200", async () => {
    stubDone({});
    await expect(
      updateInviteLink({ utubID: 1, body: { expires_in_days: 7 } }),
    ).rejects.toEqual({ kind: "error", status: 200, errorCode: null });

    stubDone("<html>login</html>");
    await expect(
      updateInviteLink({ utubID: 1, body: { expires_in_days: 7 } }),
    ).rejects.toEqual({ kind: "error", status: 200, errorCode: null });
  });
});
