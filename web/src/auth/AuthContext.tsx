import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, getToken, setToken, setUnauthorizedHandler } from "../api/client";
import type { Role, User } from "../api/types";

type AuthState =
  | { kind: "loading" }
  | { kind: "signedOut"; reason?: "expired" }
  | { kind: "signedIn"; user: User; devMode: boolean };

interface AuthContextValue {
  state: AuthState;
  signIn: (username: string, password: string) => Promise<void>;
  signOut: (reason?: "expired") => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

// Used when the server has sign-in turned off (local development).
const DEV_USER: User = { username: "local", role: "superadmin" };

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ kind: "loading" });
  const queryClient = useQueryClient();

  const signOut = useCallback(
    (reason?: "expired") => {
      setToken(null);
      queryClient.clear();
      setState({ kind: "signedOut", reason });
    },
    [queryClient],
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const cfg = await api.authConfig();
        if (!cfg.login_enabled) {
          if (!cancelled) setState({ kind: "signedIn", user: DEV_USER, devMode: true });
          return;
        }
        if (!getToken()) {
          if (!cancelled) setState({ kind: "signedOut" });
          return;
        }
        const user = await api.me();
        if (!cancelled) setState({ kind: "signedIn", user, devMode: false });
      } catch {
        setToken(null);
        if (!cancelled) setState({ kind: "signedOut" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setState((s) => (s.kind === "signedIn" && !s.devMode ? { kind: "signedOut", reason: "expired" } : s));
      setToken(null);
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const signIn = useCallback(async (username: string, password: string) => {
    const res = await api.login(username, password);
    setToken(res.access_token);
    setState({ kind: "signedIn", user: res.user, devMode: false });
  }, []);

  const value = useMemo(() => ({ state, signIn, signOut }), [state, signIn, signOut]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}

const OPERATOR_ROLES: Role[] = ["operator", "admin", "superadmin"];

export function useCurrentUser(): { user: User; devMode: boolean; canDecide: boolean } {
  const { state } = useAuth();
  if (state.kind !== "signedIn") throw new Error("useCurrentUser requires a signed-in user");
  return { user: state.user, devMode: state.devMode, canDecide: OPERATOR_ROLES.includes(state.user.role) };
}
