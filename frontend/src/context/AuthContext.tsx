import React, { createContext, useContext, useEffect, useState } from "react";
import { api } from "@/api/client";

export type UserRole = "salesman" | "admin" | "production" | "accountant" | "owner";

export interface AuthUser {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  phone: string | null;
}

interface AuthContextValue {
  user: AuthUser | null;
  token: string | null;
  loading: boolean;
  login: (username: string, password: string) => Promise<AuthUser>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(() => {
    const saved = localStorage.getItem("o2a_user");
    return saved ? (JSON.parse(saved) as AuthUser) : null;
  });
  const [token, setToken] = useState<string | null>(() => localStorage.getItem("o2a_token"));
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const verify = async () => {
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await api.get<AuthUser>("/auth/me");
        setUser(res.data);
        localStorage.setItem("o2a_user", JSON.stringify(res.data));
      } catch {
        localStorage.removeItem("o2a_token");
        localStorage.removeItem("o2a_user");
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    verify();
  }, [token]);

  const login = async (username: string, password: string) => {
    const res = await api.post<{ access_token: string; user: AuthUser }>("/auth/login", {
      username,
      password,
    });
    localStorage.setItem("o2a_token", res.data.access_token);
    localStorage.setItem("o2a_user", JSON.stringify(res.data.user));
    setToken(res.data.access_token);
    setUser(res.data.user);
    return res.data.user;
  };

  const logout = () => {
    api.post("/auth/logout").catch(() => undefined);
    localStorage.removeItem("o2a_token");
    localStorage.removeItem("o2a_user");
    setToken(null);
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, token, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
