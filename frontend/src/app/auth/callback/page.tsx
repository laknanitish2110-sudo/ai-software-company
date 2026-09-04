import { Suspense } from "react";
import OAuthCallbackHandler from "./OAuthCallbackHandler";

export default function OAuthCallbackPage() {
  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <Suspense
        fallback={
          <div style={{ textAlign: "center" }}>
            <div className="spinner" style={{ width: 28, height: 28, margin: "0 auto 16px" }} />
            <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>Completing sign in...</p>
          </div>
        }
      >
        <OAuthCallbackHandler />
      </Suspense>
    </div>
  );
}
