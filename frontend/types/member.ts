import type { Schema } from "./api-helpers.d.ts";

export type MemberItem = Schema<"UtubMemberSchema">;
export type MemberCandidate = Schema<"CoMemberSchema">;
export type MemberModifiedResponse = Schema<"SuccessEnvelope"> &
  Schema<"MemberModifiedResponseSchema">;
export type AddMemberRequest = Schema<"AddMemberRequest">;
