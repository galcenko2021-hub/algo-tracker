import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client";
import { api } from "../api/endpoints";
import type { User } from "../api/types";
import { AuthContext, type AuthContextValue, type AuthStatus } from "../lib/auth-context";

export default function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<User | null>(null);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    setStatus("anonymous");
    queryClient.clear();
  }, [queryClient]);

  const loadUser = useCallback(async () => {
    setUser(await api.me());
    setStatus("authenticated");
  }, []);

  // Restore the session after a page reload using the httpOnly refresh cookie.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const token = await refreshSession();
      if (cancelled) return;
      if (!token) return setStatus("anonymous");
      try {
        await loadUser();
      } catch {
        if (!cancelled) clearSession();
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [loadUser, clearSession]);

  useEffect(() => {
    setSessionExpiredHandler(clearSession);
    return () => setSessionExpiredHandler(null);
  }, [clearSession]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      user,
      async login(email, password) {
        const token = await api.login(email, password);
        setAccessToken(token.access_token);
        await loadUser();
      },
      async register(email, password) {
        await api.register(email, password);
        const token = await api.login(email, password);
        setAccessToken(token.access_token);
        await loadUser();
      },
      async logout() {
        try {
          await api.logout();
        } finally {
          clearSession();
        }
      },
      refreshUser: loadUser,
    }),
    [status, user, loadUser, clearSession],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
