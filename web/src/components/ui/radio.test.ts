import { createElement, type KeyboardEvent } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { useRadioGroup } from "./radio";

type Group = ReturnType<typeof useRadioGroup<string>>;

/** Render a group of three as the server would, and hand back what the hook returned. */
function render(chosen: string | null, choose: (value: string) => void = () => undefined) {
  let group: Group | null = null;
  const html = renderToStaticMarkup(
    createElement(() => {
      group = useRadioGroup(["off", "all", "selected"], chosen, choose);
      return createElement(
        "div",
        { role: "radiogroup" },
        ["off", "all", "selected"].map((value) =>
          createElement(
            "button",
            { key: value, role: "radio", tabIndex: group!.radio(value).tabIndex },
            value,
          ),
        ),
      );
    }),
  );
  return { html, group: group! };
}

/** A stand-in for a radio in the page: it can be focused, and disabled or not. */
function node(disabled = false) {
  return { matches: () => disabled, focus: vi.fn() } as unknown as HTMLElement & {
    focus: ReturnType<typeof vi.fn>;
  };
}

function press(group: Group, key: string, target: HTMLElement) {
  const event = { key, target, preventDefault: vi.fn() };
  group.group.onKeyDown(event as unknown as KeyboardEvent<HTMLElement>);
  return event.preventDefault;
}

describe("useRadioGroup", () => {
  it("puts the chosen radio alone in the tab order", () => {
    expect(render("all").html).toMatch(
      /tabindex="-1"[^>]*>off<.*tabindex="0"[^>]*>all<.*tabindex="-1"[^>]*>selected</,
    );
  });

  it("puts the first one there when none is chosen", () => {
    expect(render(null).html).toMatch(/tabindex="0"[^>]*>off<.*tabindex="-1"[^>]*>all</);
  });

  it("moves the choice and the focus with the arrows, wrapping at the ends", () => {
    const choose = vi.fn();
    const { group } = render("off", choose);
    const radios = { off: node(), all: node(), selected: node() };
    for (const [value, element] of Object.entries(radios)) group.radio(value).ref(element);

    expect(press(group, "ArrowRight", radios.off)).toHaveBeenCalled();
    expect(choose).toHaveBeenLastCalledWith("all");
    expect(radios.all.focus).toHaveBeenCalled();

    press(group, "ArrowLeft", radios.off);
    expect(choose).toHaveBeenLastCalledWith("selected");
    press(group, "ArrowDown", radios.selected);
    expect(choose).toHaveBeenLastCalledWith("off");
    press(group, "End", radios.off);
    expect(choose).toHaveBeenLastCalledWith("selected");
    press(group, "Home", radios.selected);
    expect(choose).toHaveBeenLastCalledWith("off");
  });

  it("leaves every other key, and a disabled radio, alone", () => {
    const choose = vi.fn();
    const { group } = render("off", choose);
    const radios = { off: node(), all: node(true), selected: node() };
    for (const [value, element] of Object.entries(radios)) group.radio(value).ref(element);

    expect(press(group, "Enter", radios.off)).not.toHaveBeenCalled();
    press(group, "ArrowRight", radios.off);
    expect(choose).not.toHaveBeenCalled();
    expect(radios.all.focus).not.toHaveBeenCalled();
  });
});
