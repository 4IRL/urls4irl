import { isValidUTubID, updateUTubDeckCount } from "../utils.js";

const $ = window.jQuery;

describe("isValidUTubID", () => {
  describe("returns true for valid positive integer strings", () => {
    it("accepts '1'", () => {
      expect(isValidUTubID("1")).toBe(true);
    });

    it("accepts '42'", () => {
      expect(isValidUTubID("42")).toBe(true);
    });

    it("accepts '999'", () => {
      expect(isValidUTubID("999")).toBe(true);
    });
  });

  describe("returns false for non-positive values", () => {
    it("rejects '0'", () => {
      expect(isValidUTubID("0")).toBe(false);
    });

    it("rejects '-1'", () => {
      expect(isValidUTubID("-1")).toBe(false);
    });

    it("rejects '-100'", () => {
      expect(isValidUTubID("-100")).toBe(false);
    });
  });

  describe("returns false for non-integer formats", () => {
    it("rejects float '1.5'", () => {
      expect(isValidUTubID("1.5")).toBe(false);
    });

    it("rejects '01' (leading zero)", () => {
      expect(isValidUTubID("01")).toBe(false);
    });

    it("rejects '1a' (trailing non-digits)", () => {
      expect(isValidUTubID("1a")).toBe(false);
    });
  });

  describe("returns false for non-numeric strings", () => {
    it("rejects 'abc'", () => {
      expect(isValidUTubID("abc")).toBe(false);
    });

    it("rejects empty string", () => {
      expect(isValidUTubID("")).toBe(false);
    });

    it("rejects null", () => {
      expect(isValidUTubID(null)).toBe(false);
    });
  });
});

describe("updateUTubDeckCount", () => {
  it("renders the inline total of UTubs, including filter-hidden ones", () => {
    document.body.innerHTML = `
      <span id="UTubDeckCount"></span>
      <div id="listUTubs">
        <div class="UTubSelector" utubid="1"></div>
        <div class="UTubSelector" utubid="2"></div>
        <div class="UTubSelector hidden" utubid="3"></div>
      </div>
    `;

    updateUTubDeckCount();

    expect($("#UTubDeckCount").text()).toBe("(3)");
  });

  it("renders (0) when there are no UTubs", () => {
    document.body.innerHTML = `
      <span id="UTubDeckCount"></span>
      <div id="listUTubs"></div>
    `;

    updateUTubDeckCount();

    expect($("#UTubDeckCount").text()).toBe("(0)");
  });
});
