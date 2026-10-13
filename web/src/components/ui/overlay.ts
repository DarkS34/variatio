import { createContext, useContext } from "react";

/**
 * Where an overlay that covers the screen is mounted: `document.body`, unless an ancestor
 * names another element.
 *
 * One caller names another: the landing's demo (`landing/demo/`), which draws the real
 * application inside a frame of the page. Its dialogs and its concept picker go into the
 * frame and cover the frame, as they cover the window in the application. Floating things
 * placed against an anchor (hints, a unit's menu) keep `document.body`: they are positioned
 * in the window's coordinates.
 */
export const OverlayRoot = createContext<HTMLElement | null>(null);

/** The element a full-screen overlay is portalled into. */
export function useOverlayRoot(): HTMLElement {
  return useContext(OverlayRoot) ?? document.body;
}
