import { useEffect } from "react";

// An invitation and a reset link are bearer secrets: whoever has the string is the account
// until it is redeemed. Left in the address bar it outlives the screen — in the session
// history, in whatever the person pastes when they ask for help, in a screenshot of the
// form they were half-way through. `AcceptInvite` used to drop it only on the way out, so
// a link that expired or errored kept it in the URL for as long as the tab stayed open.
//
// `replaceState` and not `pushState`: the point is that the address with the token in it
// stops existing, not that there is one more entry to go back to. The token is already in
// React state by the time this runs — `AuthGate` reads it once, before either screen
// mounts — so removing it from the URL costs the form nothing.
export function useStripTokenFromUrl() {
  useEffect(() => {
    if (!window.location.search) return;
    const clean = window.location.pathname + window.location.hash;
    window.history.replaceState(window.history.state, "", clean);
  }, []);
}
