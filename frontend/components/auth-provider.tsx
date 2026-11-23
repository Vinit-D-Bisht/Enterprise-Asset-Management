"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setAccessToken } from "@/lib/api";
import type { User } from "@/lib/types";

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  reloadUser: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: Readonly<{ children: React.ReactNode }>) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  const reloadUser = useCallback(async () => {
    const current = await api.get<User>("/auth/me");
    setUser(current);
  }, []);

  useEffect(() => {
    let active = true;
    const expired = () => {
      setUser(null);
      setAccessToken(null);
    };
    window.addEventListener("eamms:session-expired", expired);
    void (async () => {
      try {
        if (await api.refreshSession()) {
          const current = await api.get<User>("/auth/me");
          if (active) setUser(current);
        }
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
      window.removeEventListener("eamms:session-expired", expired);
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    await reloadUser();
  }, [reloadUser]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, loading, login, logout, reloadUser }), [user, loading, login, logout, reloadUser]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
