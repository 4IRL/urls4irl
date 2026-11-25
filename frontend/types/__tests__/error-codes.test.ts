import {
  EmailValidationErrorCodes,
  URLErrorCodes,
  UTubMembersErrorCodes,
  UTubTagErrorCodes,
} from "../error-codes.js";
import type { UTubTagErrorCode } from "../error-codes.js";
import type { Schema } from "../api-helpers.js";

describe("generated error codes", () => {
  it("keeps same-named members distinct per enum", () => {
    expect(UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED).toBe(7);
    expect(URLErrorCodes.UTUB_IS_LOCKED).toBe(8);
    expect(UTubTagErrorCodes.UTUB_IS_LOCKED).toBe(3);
  });

  it("emits the zero value", () => {
    expect(EmailValidationErrorCodes.UNKNOWN_EXCEPTION).toBe(0);
  });

  it("types members as literals, not number", () => {
    expectTypeOf<UTubTagErrorCode>().toEqualTypeOf<1 | 2 | 3 | 4 | 5>();
  });

  it("rejects comparing a narrowed union with a member outside it", () => {
    const loginCode = 1 as NonNullable<
      Schema<"ErrorResponse_LoginErrorCodes">["errorCode"]
    >;
    const outside = UTubMembersErrorCodes.MEMBER_ADD_NOT_ALLOWED;
    // @ts-expect-error TS2367: 7 is not in the login union (1 | 2 | 3)
    const isOutside = loginCode === outside;
    expect(isOutside).toBe(false);
  });
});
