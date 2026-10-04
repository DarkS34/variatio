import { describe, expect, it, vi } from "vitest";

// The registry reads the account's functions through the session, whose module reaches the
// API client and the tab's `sessionStorage`; `sectionsFor` takes them as an argument.
vi.mock("@/state/auth", () => ({ useFeatures: () => ({ evaluation: true, tutor: true }) }));

import { GUIDE_SECTIONS, sectionsFor, type GuideSection } from "./sections";

const slugs = (features: { evaluation: boolean; tutor: boolean }) =>
  sectionsFor(features).map((section) => section.slug);

describe("sectionsFor", () => {
  it("lists every section, in the registry's order, with both functions open", () => {
    expect(slugs({ evaluation: true, tutor: true })).toEqual(
      GUIDE_SECTIONS.map((section) => section.slug),
    );
  });

  it("leaves out the section of each function closed to the account, and nothing else", () => {
    const all = GUIDE_SECTIONS.map((section) => section.slug);
    expect(slugs({ evaluation: false, tutor: true })).toEqual(
      all.filter((slug) => slug !== "evaluate"),
    );
    expect(slugs({ evaluation: true, tutor: false })).toEqual(
      all.filter((slug) => slug !== "tutor"),
    );
    expect(slugs({ evaluation: false, tutor: false })).toEqual(
      all.filter((slug) => slug !== "evaluate" && slug !== "tutor"),
    );
  });

  it("ties each function's section to that function and no other", () => {
    const registry: readonly GuideSection[] = GUIDE_SECTIONS;
    const feature = (slug: string) => registry.find((section) => section.slug === slug)?.feature;
    expect(feature("evaluate")).toBe("evaluation");
    expect(feature("tutor")).toBe("tutor");
    expect(registry.filter((section) => section.feature !== undefined)).toHaveLength(2);
  });
});
