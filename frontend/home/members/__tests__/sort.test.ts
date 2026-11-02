import parityFixture from "../../../../tests/fixtures/member_sort_parity.json";

import type { MemberItem } from "../../../types/member.js";
import type { MemberSortValue } from "../../../types/preferences.js";

import { compareMembers } from "../sort.js";

const ALL_SORTS: MemberSortValue[] = [
  "name_az",
  "role_then_name",
  "recently_joined",
];

type FixtureMember = {
  id: number;
  username: string;
  role: string;
  joinedAt: string | null;
};

type ParityFixture = {
  inputs: { case: string; members: FixtureMember[] }[];
  expected: Record<MemberSortValue, Record<string, number[]>>;
};

function toMember(member: FixtureMember): MemberItem {
  return {
    id: member.id,
    username: member.username,
    memberRole: member.role,
    joinedAt: member.joinedAt,
  };
}

function member(overrides: Partial<MemberItem> & { id: number }): MemberItem {
  return {
    username: `user${overrides.id}`,
    memberRole: "member",
    joinedAt: null,
    ...overrides,
  };
}

describe("compareMembers against the shared parity fixture", () => {
  const fixture = parityFixture as unknown as ParityFixture;

  describe.each(ALL_SORTS)("%s", (memberSort) => {
    it.each(fixture.inputs.map((input) => input.case))(
      "orders the %s case as the server does",
      (caseName) => {
        const input = fixture.inputs.find((entry) => entry.case === caseName)!;
        const sorted = input.members
          .map(toMember)
          .sort(compareMembers({ memberSort }));
        expect(sorted.map((entry) => entry.id)).toEqual(
          fixture.expected[memberSort][caseName],
        );
      },
    );
  });

  it("covers every input case for every sort", () => {
    for (const memberSort of ALL_SORTS) {
      expect(Object.keys(fixture.expected[memberSort]).sort()).toEqual(
        fixture.inputs.map((input) => input.case).sort(),
      );
    }
  });
});

describe("compareMembers edge rules", () => {
  it("keeps the owner first even with the oldest name and join date", () => {
    const members = [
      member({ id: 2, username: "aaa", joinedAt: "2026-05-01T00:00:00.000Z" }),
      member({
        id: 1,
        username: "zzz",
        memberRole: "creator",
        joinedAt: "2020-01-01T00:00:00.000Z",
      }),
    ];
    for (const memberSort of ALL_SORTS) {
      const sorted = [...members].sort(compareMembers({ memberSort }));
      expect(sorted.map((entry) => entry.id)).toEqual([1, 2]);
    }
  });

  it("falls back to name order for an unknown sort", () => {
    const members = [
      member({ id: 1, username: "bob" }),
      member({ id: 2, username: "amy" }),
    ];
    const sorted = [...members].sort(
      compareMembers({ memberSort: "bogus" as MemberSortValue }),
    );
    expect(sorted.map((entry) => entry.id)).toEqual([2, 1]);
  });

  it("sorts an unknown role after members under role_then_name", () => {
    const members = [
      member({ id: 1, username: "aaa", memberRole: "mystery" }),
      member({ id: 2, username: "zzz", memberRole: "member" }),
      member({ id: 3, username: "mmm", memberRole: "cocreator" }),
    ];
    const sorted = [...members].sort(
      compareMembers({ memberSort: "role_then_name" }),
    );
    expect(sorted.map((entry) => entry.id)).toEqual([3, 2, 1]);
  });

  it("treats an unparseable join date as dateless", () => {
    const members = [
      member({ id: 1, username: "aaa", joinedAt: "not a date" }),
      member({ id: 2, username: "zzz", joinedAt: "2026-01-01T00:00:00.000Z" }),
    ];
    const sorted = [...members].sort(
      compareMembers({ memberSort: "recently_joined" }),
    );
    expect(sorted.map((entry) => entry.id)).toEqual([2, 1]);
  });
});
