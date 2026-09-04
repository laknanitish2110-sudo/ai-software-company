"use client";

import { useState, useEffect } from "react";
import { useToast } from "./Toast";
import { saveGitHubToken, checkGitHubToken, pushToGitHub } from "@/lib/api";

interface Props {
  projectId: string;
  problemStatement: string;
  onClose: () => void;
}

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .slice(0, 40)
    .replace(/-+$/, "") || "ai-generated-project";
}

export default function GitHubPush({ projectId, problemStatement, onClose }: Props) {
  const [tokenInput, setTokenInput] = useState("");
  const [githubUser, setGithubUser] = useState<string | null>(null);
  const [hasToken, setHasToken] = useState<boolean | null>(null);
  const [repoName, setRepoName] = useState(slugify(problemStatement));
  const [description, setDescription] = useState(problemStatement.slice(0, 200));
  const [isPrivate, setIsPrivate] = useState(false);
  const [saving, setSaving] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [repoUrl, setRepoUrl] = useState<string | null>(null);
  const [filesPushed, setFilesPushed] = useState(0);
  const { toast } = useToast();

  useEffect(() => {
    checkGitHubToken()
      .then((res) => {
        setHasToken(res.has_token);
        if (res.github_username) setGithubUser(res.github_username);
      })
      .catch(() => setHasToken(false));
  }, []);

  async function handleSaveToken() {
    if (!tokenInput.trim()) return;
    setSaving(true);
    try {
      const res = await saveGitHubToken(tokenInput.trim());
      setGithubUser(res.github_username);
      setHasToken(true);
      setTokenInput("");
      toast("success", "Token saved", `Connected as ${res.github_username}`);
    } catch (e) {
      toast("error", "Invalid token", e instanceof Error ? e.message : "Could not validate token.");
    } finally {
      setSaving(false);
    }
  }

  async function handlePush() {
    if (!repoName.trim()) return;
    setPushing(true);
    try {
      const res = await pushToGitHub(projectId, repoName.trim(), description, isPrivate);
      setRepoUrl(res.repo_url);
      setFilesPushed(res.files_pushed);
      toast("success", "Pushed to GitHub", `${res.files_pushed} files pushed successfully!`);
    } catch (e) {
      toast("error", "Push failed", e instanceof Error ? e.message : "Could not push to GitHub.");
    } finally {
      setPushing(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 100,
        background: "rgba(0,0,0,0.5)", backdropFilter: "blur(4px)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div
        className="card animate-fade-in"
        style={{ width: "100%", maxWidth: 480, padding: 0, overflow: "hidden" }}
      >
        {/* Header */}
        <div style={{
          padding: "16px 20px",
          borderBottom: "1px solid var(--border)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: 20 }}>🐙</span>
            <span style={{ fontWeight: 600, fontSize: 15, color: "var(--text-primary)" }}>Push to GitHub</span>
          </div>
          <button onClick={onClose} style={{
            background: "none", border: "none", cursor: "pointer",
            fontSize: 18, color: "var(--text-muted)", lineHeight: 1,
          }}>×</button>
        </div>

        <div style={{ padding: "20px" }}>
          {/* Success state */}
          {repoUrl ? (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <span style={{ fontSize: 40, display: "block", marginBottom: 12 }}>✅</span>
              <div style={{ fontWeight: 600, fontSize: 16, color: "var(--text-primary)", marginBottom: 4 }}>
                Successfully pushed!
              </div>
              <div style={{ fontSize: 13, color: "var(--text-muted)", marginBottom: 16 }}>
                {filesPushed} files pushed to your repository
              </div>
              <a
                href={repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  display: "inline-block", padding: "10px 20px", borderRadius: 10,
                  background: "linear-gradient(135deg, #635bff, #7a73ff)", color: "white",
                  textDecoration: "none", fontSize: 14, fontWeight: 500,
                }}
              >
                Open Repository ↗
              </a>
            </div>
          ) : hasToken === null ? (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <span className="spinner" style={{ width: 24, height: 24 }} />
            </div>
          ) : !hasToken ? (
            /* Token setup */
            <div>
              <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 12, lineHeight: 1.5 }}>
                Connect your GitHub account with a Personal Access Token.
                The token needs the <strong>repo</strong> scope.
              </div>
              <a
                href="https://github.com/settings/tokens/new?scopes=repo&description=AI+Software+Company"
                target="_blank"
                rel="noopener noreferrer"
                style={{ fontSize: 12, color: "var(--accent)", textDecoration: "none", display: "block", marginBottom: 12 }}
              >
                Generate a token on GitHub ↗
              </a>
              <input
                type="password"
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 8, fontSize: 13,
                  background: "var(--bg-base)", border: "1px solid var(--border)",
                  color: "var(--text-primary)", marginBottom: 12, fontFamily: "monospace",
                }}
                onKeyDown={(e) => e.key === "Enter" && handleSaveToken()}
              />
              <button
                onClick={handleSaveToken}
                disabled={!tokenInput.trim() || saving}
                className="btn-primary w-full py-2.5 text-sm"
              >
                {saving ? "Validating..." : "Save Token"}
              </button>
            </div>
          ) : (
            /* Push form */
            <div>
              <div style={{
                display: "flex", alignItems: "center", gap: 8,
                padding: "8px 12px", borderRadius: 8,
                background: "var(--success-bg)", border: "1px solid var(--success-border)",
                marginBottom: 16, fontSize: 12,
              }}>
                <span style={{ color: "var(--success)" }}>✓</span>
                <span style={{ color: "var(--success)" }}>Connected as <strong>{githubUser}</strong></span>
              </div>

              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>
                Repository name
              </label>
              <input
                type="text"
                value={repoName}
                onChange={(e) => setRepoName(e.target.value.replace(/[^a-zA-Z0-9._-]/g, "-"))}
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 8, fontSize: 13,
                  background: "var(--bg-base)", border: "1px solid var(--border)",
                  color: "var(--text-primary)", marginBottom: 12,
                }}
              />

              <label style={{ fontSize: 12, fontWeight: 500, color: "var(--text-secondary)", display: "block", marginBottom: 4 }}>
                Description
              </label>
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                style={{
                  width: "100%", padding: "10px 14px", borderRadius: 8, fontSize: 13,
                  background: "var(--bg-base)", border: "1px solid var(--border)",
                  color: "var(--text-primary)", marginBottom: 12,
                }}
              />

              <label style={{
                display: "flex", alignItems: "center", gap: 8,
                fontSize: 13, color: "var(--text-secondary)",
                cursor: "pointer", marginBottom: 16,
              }}>
                <input
                  type="checkbox"
                  checked={isPrivate}
                  onChange={(e) => setIsPrivate(e.target.checked)}
                  style={{ accentColor: "var(--accent)" }}
                />
                Private repository
              </label>

              <button
                onClick={handlePush}
                disabled={!repoName.trim() || pushing}
                className="btn-primary w-full py-2.5 text-sm"
              >
                {pushing ? (
                  <span style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
                    <span className="spinner" style={{ width: 14, height: 14 }} />
                    Pushing files...
                  </span>
                ) : (
                  "Push to GitHub"
                )}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
