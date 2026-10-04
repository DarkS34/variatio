import { useRef, type KeyboardEvent } from "react";

/** What `useRadioGroup` hands each radio: its place in the tab order and a way to reach it. */
export interface RadioProps {
  ref: (node: HTMLElement | null) => void;
  tabIndex: number;
}

/**
 * The keyboard of a radio group, as WAI-ARIA describes it, for `role="radio"` buttons.
 *
 * ONE stop in the tab order — the chosen radio, or the first when none is chosen — and the
 * arrows choose the next or the previous radio, wrapping at the ends, with the focus going
 * along; Home and End choose the first and the last. Space and Enter stay the buttons' own
 * click. Before it every option was a stop of its own and an arrow did nothing, while a
 * screen reader announced «radio, 1 of 3» and so promised the arrows. `TabStrip` gives its
 * tabs the same keys.
 *
 * Spread `group` on the `role="radiogroup"` element and `radio(value)` on each radio. An
 * arrow towards a disabled radio does nothing, and a group whose radios are all disabled
 * answers no key, since none of them can hold the focus.
 */
export function useRadioGroup<T>(
  values: readonly T[],
  chosen: T | null | undefined,
  choose: (value: T) => void,
): {
  group: { onKeyDown: (event: KeyboardEvent<HTMLElement>) => void };
  radio: (value: T) => RadioProps;
} {
  const nodes = useRef(new Map<T, HTMLElement>());
  const stop = values.some((value) => Object.is(value, chosen)) ? chosen : values[0];

  const go = (index: number) => {
    const value = values[(index + values.length) % values.length];
    const node = nodes.current.get(value);
    if (!node || node.matches(":disabled")) return;
    choose(value);
    node.focus();
  };

  const onKeyDown = (event: KeyboardEvent<HTMLElement>) => {
    const from = values.findIndex((value) => nodes.current.get(value) === event.target);
    if (from < 0) return;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") go(from + 1);
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") go(from - 1);
    else if (event.key === "Home") go(0);
    else if (event.key === "End") go(values.length - 1);
    else return;
    event.preventDefault();
  };

  return {
    group: { onKeyDown },
    radio: (value) => ({
      ref: (node) => {
        if (node) nodes.current.set(value, node);
        else nodes.current.delete(value);
      },
      tabIndex: Object.is(value, stop) ? 0 : -1,
    }),
  };
}
