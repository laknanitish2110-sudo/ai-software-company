"use client";

import { useEffect, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";

export default function OAuthCallbackHandler() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { handleOAuthCallback } = useAuth();
  const processed = useRef(false);

  useEffect(() => {
    if (processed.current) return;
    processed.current = true;

    const token = searchParams.get("token");
    const error = searchParams.get("error");

    if (error) {
      router.replace(`/login?oauth_error=${encodeURIComponent(error)}`);
      return;
    }
    if (!token) {
      router.replace("/login?oauth_error=no_token");
      return;
    }

    handleOAuthCallback(token)
      .then(() => router.replace("/"))
      .catch(() => router.replace("/login?oauth_error=callback_failed"));
  }, [searchParams, router, handleOAuthCallback]);

  return (
    <div style={{ textAlign: "center" }}>
      <div
        className="spinner"
        style={{ width: 28, height: 28, margin: "0 auto 16px" }}
      />
      <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
        Completing sign in...
      </p>
    </div>
  );
}
