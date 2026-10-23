import type { MeOut } from "@/api/types";

/** Where the app is in the session lifecycle; drives the route guards in app/_layout. */
export type SessionState =
  | { status: "loading" }
  | { status: "unavailable" } // tokens exist but the API couldn't be reached
  | { status: "signedOut"; notice: string | null }
  | { status: "signedIn"; me: MeOut };

export type SessionAction =
  | { type: "signedIn"; me: MeOut }
  | { type: "meUpdated"; me: MeOut }
  | { type: "signedOut"; notice?: string | null }
  | { type: "unavailable" }
  | { type: "retrying" };

export const initialSession: SessionState = { status: "loading" };

export function sessionReducer(state: SessionState, action: SessionAction): SessionState {
  switch (action.type) {
    case "signedIn":
      return { status: "signedIn", me: action.me };
    case "meUpdated":
      return state.status === "signedIn" ? { status: "signedIn", me: action.me } : state;
    case "signedOut":
      return { status: "signedOut", notice: action.notice ?? null };
    case "unavailable":
      return { status: "unavailable" };
    case "retrying":
      return { status: "loading" };
  }
}

export type Route = "loading" | "unavailable" | "auth" | "onboarding" | "app";

/** Which route group the user may see. */
export function routeFor(state: SessionState): Route {
  switch (state.status) {
    case "loading":
      return "loading";
    case "unavailable":
      return "unavailable";
    case "signedOut":
      return "auth";
    case "signedIn":
      return state.me.preferences.onboarding_completed ? "app" : "onboarding";
  }
}

/** The first screen of each route group; where an unreachable path lands (app/+not-found). */
export function homeFor(route: Route): "/welcome" | "/subject" | "/" | null {
  switch (route) {
    case "auth":
      return "/welcome";
    case "onboarding":
      return "/subject";
    case "app":
      return "/";
    default:
      return null;
  }
}
