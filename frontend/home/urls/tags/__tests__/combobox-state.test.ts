import {
  filterTagSuggestions,
  hasExactTagMatch,
  mergeAppliedTagsIntoStore,
} from "../combobox-state.js";
import { getState, resetStore, setState } from "../../../../store/app-store.js";
import type { UtubTag } from "../../../../types/url.js";

const PYTHON_TAG: UtubTag = { id: 1, tagString: "python", tagApplied: 3 };
const WEB_TAG: UtubTag = { id: 2, tagString: "web", tagApplied: 1 };
const PYTEST_TAG: UtubTag = { id: 3, tagString: "pytest", tagApplied: 2 };

function seedTags(tags: UtubTag[]): void {
  setState({ tags });
}

describe("combobox-state", () => {
  beforeEach(() => {
    resetStore();
  });

  describe("filterTagSuggestions", () => {
    it("returns case-insensitive substring matches", () => {
      seedTags([PYTHON_TAG, WEB_TAG, PYTEST_TAG]);

      const results = filterTagSuggestions({
        query: "PY",
        appliedTagIds: [],
        stagedTagStrings: [],
      });

      expect(results.map((tag) => tag.id)).toEqual([
        PYTHON_TAG.id,
        PYTEST_TAG.id,
      ]);
    });

    it("excludes tags already applied to the URL", () => {
      seedTags([PYTHON_TAG, WEB_TAG, PYTEST_TAG]);

      const results = filterTagSuggestions({
        query: "py",
        appliedTagIds: [PYTHON_TAG.id],
        stagedTagStrings: [],
      });

      expect(results.map((tag) => tag.id)).toEqual([PYTEST_TAG.id]);
    });

    it("excludes tags already staged as chips (case-insensitive)", () => {
      seedTags([PYTHON_TAG, WEB_TAG, PYTEST_TAG]);

      const results = filterTagSuggestions({
        query: "py",
        appliedTagIds: [],
        stagedTagStrings: ["PYTHON"],
      });

      expect(results.map((tag) => tag.id)).toEqual([PYTEST_TAG.id]);
    });

    it("returns all non-excluded tags for an empty query", () => {
      seedTags([PYTHON_TAG, WEB_TAG]);

      const results = filterTagSuggestions({
        query: "   ",
        appliedTagIds: [],
        stagedTagStrings: [],
      });

      expect(results.map((tag) => tag.id)).toEqual([PYTHON_TAG.id, WEB_TAG.id]);
    });
  });

  describe("hasExactTagMatch", () => {
    it("suppresses create-new when the query exactly matches a tag", () => {
      seedTags([PYTHON_TAG, WEB_TAG]);

      expect(hasExactTagMatch({ query: "Python" })).toBe(true);
    });

    it("returns false when the query only partially matches", () => {
      seedTags([PYTHON_TAG, WEB_TAG]);

      expect(hasExactTagMatch({ query: "pyth" })).toBe(false);
    });

    it("returns false for an empty/whitespace query", () => {
      seedTags([PYTHON_TAG]);

      expect(hasExactTagMatch({ query: "   " })).toBe(false);
    });
  });

  describe("mergeAppliedTagsIntoStore", () => {
    it("refreshes tagApplied for an existing tag (upsert by id)", () => {
      seedTags([PYTHON_TAG, WEB_TAG]);

      mergeAppliedTagsIntoStore({
        appliedTags: [
          { id: PYTHON_TAG.id, tagString: "python", tagApplied: 4 },
        ],
      });

      const tags = getState().tags;
      expect(tags).toHaveLength(2);
      const python = tags.find((tag) => tag.id === PYTHON_TAG.id);
      expect(python?.tagApplied).toBe(4);
    });

    it("appends a brand-new tag not yet in the store", () => {
      seedTags([PYTHON_TAG]);

      const newTag: UtubTag = { id: 99, tagString: "django", tagApplied: 1 };
      mergeAppliedTagsIntoStore({ appliedTags: [newTag] });

      const tags = getState().tags;
      expect(tags).toHaveLength(2);
      expect(tags.find((tag) => tag.id === 99)).toEqual(newTag);
    });
  });
});
