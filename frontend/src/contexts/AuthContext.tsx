"use client";

import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";

interface User {
  id: string;
  email: string;
  created_at: string;
  display_name?: string | null;
  avatar_url?: string | null;
  oauth_provider?: string | null;
  email_verified?: boolean;
}

interface AuthContextValue {
  user: User | null;
  token: string | null;
  loading: boolean;
  pendingVerificationEmail: string | null;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => void;
  handleOAuthCallback: (token: string) => Promise<void>;
  verifyEmail: (email: string, code: string) => Promise<void>;
  resendCode: (email: string) => Promise<void>;
  clearPendingVerification: () => void;
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  loading: true,
  pendingVerificationEmail: null,
  login: async () => {},
  register: async () => {},
  logout: () => {},
  handleOAuthCallback: async () => {},
  verifyEmail: async () => {},
  resendCode: async () => {},
  clearPendingVerification: () => {},
});

export function useAuth() {
  return useContext(AuthContext);
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
const TOKEN_KEY = "auth_token";
const USER_KEY = "auth_user";

async function authFetch(url: string, options?: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } catch (err: unknown) {
    if (err instanceof DOMException && err.name === "AbortError") {
      throw new Error("Request timed out");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [pendingVerificationEmail, setPendingVerificationEmail] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    const savedToken = localStorage.getItem(TOKEN_KEY);
    const savedUser = localStorage.getItem(USER_KEY);
    if (savedToken && savedUser) {
      try {
        setToken(savedToken);
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      }
    }
    setLoading(false);
  }, []);

  const saveAuth = useCallback((t: string, u: User) => {
    localStorage.setItem(TOKEN_KEY, t);
    localStorage.setItem(USER_KEY, JSON.stringify(u));
    setToken(t);
    setUser(u);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authFetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Invalid email or password");
    }
    const data = await res.json();
    if (data.requires_verification) {
      setPendingVerificationEmail(email);
      localStorage.setItem(TOKEN_KEY, data.access_token);
      throw new Error("EMAIL_NOT_VERIFIED");
    }
    saveAuth(data.access_token, data.user);
  }, [saveAuth]);

  const register = useCallback(async (email: string, password: string) => {
    const res = await authFetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Registration failed");
    }
    const data = await res.json();
    localStorage.setItem(TOKEN_KEY, data.access_token);
    if (data.requires_verification) {
      setPendingVerificationEmail(email);
      return;
    }
    saveAuth(data.access_token, data.user);
  }, [saveAuth]);

  const verifyEmail = useCallback(async (email: string, code: string) => {
    const res = await authFetch(`${API_BASE}/auth/verify-email`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, code }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Verification failed");
    }
    const data = await res.json();
    if (data.access_token) {
      const meRes = await authFetch(`${API_BASE}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (meRes.ok) {
        const meData = await meRes.json();
        saveAuth(data.access_token, { ...meData.user, email_verified: true });
      }
    }
    setPendingVerificationEmail(null);
  }, [saveAuth]);

  const resendCode = useCallback(async (email: string) => {
    const res = await authFetch(`${API_BASE}/auth/resend-code`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not resend code");
    }
  }, []);

  const clearPendingVerification = useCallback(() => {
    setPendingVerificationEmail(null);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
    setPendingVerificationEmail(null);
    router.push("/login");
  }, [router]);

  const handleOAuthCallback = useCallback(async (oauthToken: string) => {
    localStorage.setItem(TOKEN_KEY, oauthToken);
    setToken(oauthToken);

    const res = await authFetch(`${API_BASE}/auth/me`, {
      headers: { Authorization: `Bearer ${oauthToken}` },
    });
    if (!res.ok) {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      setToken(null);
      setUser(null);
      throw new Error("Failed to fetch user profile");
    }
    const data = await res.json();
    const userData: User = { ...data.user, email_verified: true };
    localStorage.setItem(USER_KEY, JSON.stringify(userData));
    setUser(userData);
  }, []);

  return (
    <AuthContext value={{ user, token, loading, pendingVerificationEmail, login, register, logout, handleOAuthCallback, verifyEmail, resendCode, clearPendingVerification }}>
      {children}
    </AuthContext>
  );
}
