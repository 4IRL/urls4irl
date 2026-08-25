import {
  filterCoMemberSuggestions,
  hasExactCoMemberMatch,
} from "../member-combobox-state.js";
import { resetStore, setState } from "../../../store/app-store.js";
import type { MemberCandidate } from "../../../types/member.js";

const BOB: MemberCandidate = { id: 1, username: "Bob", sharedUtubCount: 2 };
const BOBBY: MemberCandidate = { id: 2, username: "Bobby", sharedUtubCount: 1 };
const ALICE: MemberCandidate = { id: 3, username: "Alice", sharedUtubCount: 3 };

function seedCandidates(candidates: MemberCandidate[]): void {
  setState({ coMemberCandidates: candidates });
}

describe("member-combobox-state", () => {
  beforeEach(() => {
    resetStore();
  });

  describe("filterCoMemberSuggestions", () => {
    it("returns substring matches over candidate usernames", () => {
      seedCandidates([BOB, BOBBY, ALICE]);

      const results = filterCoMemberSuggestions({
        query: "bob",
        currentMemberUsernames: [],
        stagedUsernames: [],
      });

      expect(results.map((candidate) => candidate.id)).toEqual([
        BOB.id,
        BOBBY.id,
      ]);
    });

    it("matches case-insensitively", () => {
      seedCandidates([BOB, BOBBY, ALICE]);

      const results = filterCoMemberSuggestions({
        query: "BOB",
        currentMemberUsernames: [],
        stagedUsernames: [],
      });

      expect(results.map((candidate) => candidate.id)).toEqual([
        BOB.id,
        BOBBY.id,
      ]);
    });

    it("excludes candidates already a current member of the UTub", () => {
      seedCandidates([BOB, BOBBY, ALICE]);

      const results = filterCoMemberSuggestions({
        query: "bob",
        currentMemberUsernames: ["Bob"],
        stagedUsernames: [],
      });

      expect(results.map((candidate) => candidate.id)).toEqual([BOBBY.id]);
    });

    it("excludes candidates already staged as chips", () => {
      seedCandidates([BOB, BOBBY, ALICE]);

      const results = filterCoMemberSuggestions({
        query: "bob",
        currentMemberUsernames: [],
        stagedUsernames: ["Bobby"],
      });

      expect(results.map((candidate) => candidate.id)).toEqual([BOB.id]);
    });

    it("returns no suggestions for an empty query (filter-only)", () => {
      seedCandidates([BOB, BOBBY]);

      const results = filterCoMemberSuggestions({
        query: "",
        currentMemberUsernames: [],
        stagedUsernames: [],
      });

      expect(results).toEqual([]);
    });

    it("returns no suggestions for a whitespace-only query (filter-only)", () => {
      seedCandidates([BOB, BOBBY]);

      const results = filterCoMemberSuggestions({
        query: "   ",
        currentMemberUsernames: [],
        stagedUsernames: [],
      });

      expect(results).toEqual([]);
    });
  });

  describe("hasExactCoMemberMatch", () => {
    it("is true when the query exactly matches a candidate username", () => {
      seedCandidates([BOB, BOBBY]);

      expect(hasExactCoMemberMatch({ query: "Bob" })).toBe(true);
    });

    it("is case-sensitive (Bob !== bob)", () => {
      seedCandidates([BOB, BOBBY]);

      expect(hasExactCoMemberMatch({ query: "bob" })).toBe(false);
    });

    it("returns false when the query only partially matches", () => {
      seedCandidates([BOB, BOBBY]);

      expect(hasExactCoMemberMatch({ query: "Bo" })).toBe(false);
    });

    it("returns false for an empty/whitespace query", () => {
      seedCandidates([BOB]);

      expect(hasExactCoMemberMatch({ query: "   " })).toBe(false);
    });
  });
});
