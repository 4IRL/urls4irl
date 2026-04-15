import type { components } from "./api.d.ts";

export type MemberItem = components["schemas"]["UserSchema"];
export type MemberModifiedResponse = components["schemas"]["SuccessEnvelope"] &
  components["schemas"]["MemberModifiedResponseSchema"];
export type AddMemberRequest = components["schemas"]["AddMemberRequest"];
