import { describe, expect, it } from "vitest";

import { fieldText, fieldToInput, inputToField, isEmptyField } from "./fields";

describe("fieldText", () => {
  it("renders a list one entry per line, never comma-joined", () => {
    expect(fieldText(["Daría error, no boxes", "13", "19"])).toBe(
      "- Daría error, no boxes\n- 13\n- 19",
    );
  });

  it("leaves a string exactly as it is, indentation included", () => {
    expect(fieldText("def f():\n    return 1")).toBe("def f():\n    return 1");
  });

  it("renders absence as the empty string", () => {
    expect(fieldText(null)).toBe("");
    expect(fieldText(undefined)).toBe("");
    expect(fieldText([])).toBe("");
  });

  it("drops blank entries instead of drawing empty bullets", () => {
    expect(fieldText(["a", "", "  ", "b"])).toBe("- a\n- b");
  });

  it("renders an object as key/value lines", () => {
    expect(fieldText({ a: 1, b: null, c: "x" })).toBe("- a: 1\n- c: x");
  });

  it("keeps scalars readable", () => {
    expect(fieldText(3)).toBe("3");
    expect(fieldText(false)).toBe("false");
  });
});

describe("isEmptyField", () => {
  it("counts an empty list as nothing to show", () => {
    expect(isEmptyField([])).toBe(true);
    expect(isEmptyField(["a"])).toBe(false);
  });

  it("keeps a zero and a false, which are values", () => {
    expect(isEmptyField(0)).toBe(false);
    expect(isEmptyField(false)).toBe(false);
  });

  it("counts null, undefined and the empty string as nothing", () => {
    expect(isEmptyField(null)).toBe(true);
    expect(isEmptyField(undefined)).toBe(true);
    expect(isEmptyField("")).toBe(true);
  });
});

describe("the editor round-trip", () => {
  it("gives a list back as a list, not as the string of a list", () => {
    const options = ["Daría error, no boxes", "13", "19"];
    expect(inputToField(fieldToInput(options), true)).toEqual(options);
  });

  it("shows a list without bullets, so saving does not swallow them", () => {
    expect(fieldToInput(["a", "b"])).toBe("a\nb");
  });

  it("leaves a string untouched through the round-trip", () => {
    const code = "def f():\n    return 1";
    expect(inputToField(fieldToInput(code), false)).toBe(code);
  });

  it("turns an emptied text field into null and an emptied list into a list", () => {
    expect(inputToField("", false)).toBeNull();
    expect(inputToField("", true)).toEqual([]);
  });

  it("drops the blank lines a person leaves between options", () => {
    expect(inputToField("a\n\n  b  \n", true)).toEqual(["a", "b"]);
  });
});
