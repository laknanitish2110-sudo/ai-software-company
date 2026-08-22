"use client";

import { useState, useEffect, useMemo } from "react";
import { getFileContents, GeneratedFile } from "@/lib/api";

interface Props {
  projectId: string;
  onClose: () => void;
}

interface TreeNode {
  name: string;
  path: string;
  isDir: boolean;
  children: TreeNode[];
  file?: GeneratedFile;
}

function buildTree(files: GeneratedFile[]): TreeNode[] {
  const root: TreeNode[] = [];

  for (const file of files) {
    const parts = file.path.split("/");
    let current = root;

    for (let i = 0; i < parts.length; i++) {
      const name = parts[i];
      const isLast = i === parts.length - 1;
      const path = parts.slice(0, i + 1).join("/");

      let existing = current.find((n) => n.name === name);
      if (!existing) {
        existing = {
          name,
          path,
          isDir: !isLast,
          children: [],
          file: isLast ? file : undefined,
        };
        current.push(existing);
      }
      current = existing.children;
    }
  }

  const sortNodes = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => {
      if (a.isDir && !b.isDir) return -1;
      if (!a.isDir && b.isDir) return 1;
      return a.name.localeCompare(b.name);
    });
    nodes.forEach((n) => sortNodes(n.children));
  };
  sortNodes(root);
  return root;
}

const FILE_ICONS: Record<string, string> = {
  python: "🐍",
  javascript: "🟨",
  typescript: "🔷",
  tsx: "⚛️",
  jsx: "⚛️",
  html: "🌐",
  css: "🎨",
  json: "📋",
  markdown: "📝",
  yaml: "⚙️",
  toml: "⚙️",
  sql: "🗄️",
  bash: "💲",
  text: "📄",
  dockerfile: "🐳",
};

function FileTreeNode({
  node,
  depth,
  selectedPath,
  onSelect,
  expanded,
  onToggle,
}: {
  node: TreeNode;
  depth: number;
  selectedPath: string;
  onSelect: (file: GeneratedFile) => void;
  expanded: Set<string>;
  onToggle: (path: string) => void;
}) {
  const isOpen = expanded.has(node.path);
  const isSelected = selectedPath === node.path;

  if (node.isDir) {
    return (
      <div>
        <button
          onClick={() => onToggle(node.path)}
          className="w-full text-left flex items-center gap-1.5 py-1 px-2 rounded-md transition-colors"
          style={{
            paddingLeft: 8 + depth * 16,
            color: "var(--text-secondary)",
            fontSize: 13,
            background: "transparent",
            border: "none",
            cursor: "pointer",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "var(--bg-elevated)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "transparent";
          }}
        >
          <span
            style={{
              fontSize: 10,
              color: "var(--text-muted)",
              transition: "transform 0.15s",
              transform: isOpen ? "rotate(90deg)" : "rotate(0deg)",
              display: "inline-block",
            }}
          >
            ▶
          </span>
          <span style={{ fontSize: 14 }}>{isOpen ? "📂" : "📁"}</span>
          <span style={{ fontWeight: 500 }}>{node.name}</span>
        </button>
        {isOpen &&
          node.children.map((child) => (
            <FileTreeNode
              key={child.path}
              node={child}
              depth={depth + 1}
              selectedPath={selectedPath}
              onSelect={onSelect}
              expanded={expanded}
              onToggle={onToggle}
            />
          ))}
      </div>
    );
  }

  const lang = node.file?.language || "text";
  const icon = FILE_ICONS[lang] || "📄";

  return (
    <button
      onClick={() => node.file && onSelect(node.file)}
      className="w-full text-left flex items-center gap-1.5 py-1 px-2 rounded-md transition-all"
      style={{
        paddingLeft: 24 + depth * 16,
        fontSize: 13,
        color: isSelected ? "var(--accent)" : "var(--text-secondary)",
        background: isSelected ? "var(--accent-bg)" : "transparent",
        border: isSelected
          ? "1px solid var(--accent-border)"
          : "1px solid transparent",
        cursor: "pointer",
        fontWeight: isSelected ? 600 : 400,
      }}
      onMouseEnter={(e) => {
        if (!isSelected) e.currentTarget.style.background = "var(--bg-elevated)";
      }}
      onMouseLeave={(e) => {
        if (!isSelected)
          e.currentTarget.style.background = "transparent";
      }}
    >
      <span style={{ fontSize: 13 }}>{icon}</span>
      <span className="truncate">{node.name}</span>
      {node.file && (
        <span
          style={{
            marginLeft: "auto",
            fontSize: 10,
            color: "var(--text-muted)",
            fontFamily: "monospace",
          }}
        >
          {node.file.size > 1024
            ? `${(node.file.size / 1024).toFixed(1)}k`
            : `${node.file.size}b`}
        </span>
      )}
    </button>
  );
}

function highlightLine(line: string, language: string): React.ReactNode {
  if (language === "python" || language === "javascript" || language === "typescript" || language === "tsx" || language === "jsx") {
    const parts: React.ReactNode[] = [];
    let remaining = line;
    let key = 0;

    const comment = language === "python" ? "#" : "//";
    const commentIdx = remaining.indexOf(comment);
    if (commentIdx !== -1) {
      const before = remaining.slice(0, commentIdx);
      const commentText = remaining.slice(commentIdx);
      parts.push(<span key={key++}>{highlightCode(before, language)}</span>);
      parts.push(
        <span key={key++} style={{ color: "#6a737d", fontStyle: "italic" }}>
          {commentText}
        </span>
      );
      return <>{parts}</>;
    }

    return highlightCode(remaining, language);
  }

  if (language === "json") {
    return highlightJSON(line);
  }

  return <span>{line}</span>;
}

function highlightCode(text: string, lang: string): React.ReactNode {
  const keywords =
    lang === "python"
      ? /\b(def|class|import|from|return|if|elif|else|for|while|try|except|finally|with|as|async|await|raise|yield|lambda|not|and|or|in|is|None|True|False|self|pass|break|continue)\b/g
      : /\b(const|let|var|function|return|if|else|for|while|try|catch|finally|class|import|export|from|default|async|await|new|this|typeof|instanceof|null|undefined|true|false|throw|switch|case|break|continue|interface|type|extends|implements)\b/g;

  const stringRegex = /(["'`])(?:(?=(\\?))\2.)*?\1/g;

  const parts: React.ReactNode[] = [];
  let lastIdx = 0;
  const combined = new RegExp(
    `(${stringRegex.source})|(${keywords.source})|(\\b\\d+\\.?\\d*\\b)`,
    "g"
  );

  let match;
  while ((match = combined.exec(text)) !== null) {
    if (match.index > lastIdx) {
      parts.push(
        <span key={lastIdx}>{text.slice(lastIdx, match.index)}</span>
      );
    }

    if (match[1]) {
      parts.push(
        <span key={match.index} style={{ color: "#a8d8a8" }}>
          {match[0]}
        </span>
      );
    } else if (match[3]) {
      parts.push(
        <span key={match.index} style={{ color: "#c792ea", fontWeight: 600 }}>
          {match[0]}
        </span>
      );
    } else {
      parts.push(
        <span key={match.index} style={{ color: "#f5a623" }}>
          {match[0]}
        </span>
      );
    }
    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < text.length) {
    parts.push(<span key={lastIdx}>{text.slice(lastIdx)}</span>);
  }

  return <>{parts}</>;
}

function highlightJSON(line: string): React.ReactNode {
  const parts: React.ReactNode[] = [];
  const regex = /("(?:[^"\\]|\\.)*")\s*(:)?|(\b\d+\.?\d*\b)|\b(true|false|null)\b/g;
  let lastIdx = 0;
  let match;

  while ((match = regex.exec(line)) !== null) {
    if (match.index > lastIdx) {
      parts.push(
        <span key={lastIdx}>{line.slice(lastIdx, match.index)}</span>
      );
    }

    if (match[1] && match[2]) {
      parts.push(
        <span key={match.index} style={{ color: "#8bb8ff" }}>
          {match[1]}
        </span>
      );
      parts.push(
        <span key={match.index + "c"} style={{ color: "#ccc" }}>
          :
        </span>
      );
    } else if (match[1]) {
      parts.push(
        <span key={match.index} style={{ color: "#a8d8a8" }}>
          {match[0]}
        </span>
      );
    } else if (match[3]) {
      parts.push(
        <span key={match.index} style={{ color: "#f5a623" }}>
          {match[0]}
        </span>
      );
    } else if (match[4]) {
      parts.push(
        <span key={match.index} style={{ color: "#c792ea" }}>
          {match[0]}
        </span>
      );
    }
    lastIdx = match.index + match[0].length;
  }

  if (lastIdx < line.length) {
    parts.push(<span key={lastIdx}>{line.slice(lastIdx)}</span>);
  }

  return <>{parts}</>;
}

export default function CodePreview({ projectId, onClose }: Props) {
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [selectedFile, setSelectedFile] = useState<GeneratedFile | null>(null);
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [searchQuery, setSearchQuery] = useState("");

  useEffect(() => {
    getFileContents(projectId).then((data) => {
      setFiles(data.files);
      if (data.files.length > 0) {
        const first =
          data.files.find((f) => f.path.endsWith("main.py")) ||
          data.files.find((f) => f.path.endsWith("README.md")) ||
          data.files[0];
        setSelectedFile(first);
        const dirs = new Set<string>();
        data.files.forEach((f) => {
          const parts = f.path.split("/");
          for (let i = 1; i < parts.length; i++) {
            dirs.add(parts.slice(0, i).join("/"));
          }
        });
        setExpanded(dirs);
      }
      setLoading(false);
    });
  }, [projectId]);

  const tree = useMemo(() => buildTree(files), [files]);

  const filteredFiles = useMemo(() => {
    if (!searchQuery) return files;
    const q = searchQuery.toLowerCase();
    return files.filter(
      (f) =>
        f.path.toLowerCase().includes(q) ||
        f.content.toLowerCase().includes(q)
    );
  }, [files, searchQuery]);

  const totalLines = useMemo(
    () => files.reduce((sum, f) => sum + f.content.split("\n").length, 0),
    [files]
  );

  const toggleExpand = (path: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  if (loading) {
    return (
      <div
        className="fixed inset-0 flex items-center justify-center"
        style={{ background: "rgba(0,0,0,0.6)", zIndex: 100 }}
      >
        <div className="card p-8 text-center">
          <div className="spinner mx-auto mb-3" style={{ width: 24, height: 24 }} />
          <div style={{ color: "var(--text-secondary)" }}>Loading generated files...</div>
        </div>
      </div>
    );
  }

  if (files.length === 0) {
    return (
      <div
        className="fixed inset-0 flex items-center justify-center"
        style={{ background: "rgba(0,0,0,0.6)", zIndex: 100 }}
        onClick={onClose}
      >
        <div className="card p-8 text-center" onClick={(e) => e.stopPropagation()}>
          <div className="text-3xl mb-3">📦</div>
          <div style={{ color: "var(--text-secondary)" }}>
            No generated files yet. Run the pipeline first.
          </div>
          <button onClick={onClose} className="btn-ghost mt-4 text-sm">
            Close
          </button>
        </div>
      </div>
    );
  }

  const lines = selectedFile?.content.split("\n") || [];

  return (
    <div
      className="fixed inset-0 animate-fade-in"
      style={{ background: "rgba(0,0,0,0.7)", zIndex: 100 }}
      onClick={onClose}
    >
      <div
        className="absolute inset-3 lg:inset-6 flex flex-col overflow-hidden"
        style={{
          background: "#0d1117",
          borderRadius: 16,
          border: "1px solid #30363d",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between px-5 py-3"
          style={{
            borderBottom: "1px solid #30363d",
            background: "#161b22",
          }}
        >
          <div className="flex items-center gap-3">
            <span style={{ fontSize: 18 }}>💻</span>
            <span
              style={{
                color: "#e6edf3",
                fontSize: 15,
                fontWeight: 600,
              }}
            >
              Generated Code
            </span>
            <span
              className="status-badge"
              style={{
                background: "rgba(99,91,255,0.15)",
                color: "#a5a0ff",
                border: "1px solid rgba(99,91,255,0.3)",
                fontSize: 11,
              }}
            >
              {files.length} files
            </span>
            <span
              className="status-badge"
              style={{
                background: "rgba(11,191,140,0.12)",
                color: "#0bbf8c",
                border: "1px solid rgba(11,191,140,0.25)",
                fontSize: 11,
              }}
            >
              {totalLines.toLocaleString()} lines
            </span>
          </div>
          <button
            onClick={onClose}
            style={{
              background: "rgba(255,255,255,0.06)",
              border: "1px solid #30363d",
              color: "#8b949e",
              padding: "6px 14px",
              borderRadius: 8,
              cursor: "pointer",
              fontSize: 13,
            }}
          >
            Close ✕
          </button>
        </div>

        {/* Body */}
        <div className="flex flex-1 overflow-hidden">
          {/* File tree sidebar */}
          <div
            className="flex flex-col overflow-hidden"
            style={{
              width: 260,
              minWidth: 260,
              borderRight: "1px solid #30363d",
              background: "#0d1117",
            }}
          >
            {/* Search */}
            <div style={{ padding: "8px 10px", borderBottom: "1px solid #21262d" }}>
              <input
                type="text"
                placeholder="Search files..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={{
                  width: "100%",
                  background: "#161b22",
                  border: "1px solid #30363d",
                  borderRadius: 6,
                  padding: "5px 10px",
                  fontSize: 12,
                  color: "#e6edf3",
                  outline: "none",
                }}
              />
            </div>
            {/* Tree */}
            <div className="flex-1 overflow-y-auto py-1" style={{ scrollbarWidth: "thin", scrollbarColor: "#30363d transparent" }}>
              {searchQuery ? (
                filteredFiles.map((f) => (
                  <button
                    key={f.path}
                    onClick={() => {
                      setSelectedFile(f);
                      setSearchQuery("");
                    }}
                    className="w-full text-left px-3 py-1.5 text-xs truncate"
                    style={{
                      color:
                        selectedFile?.path === f.path
                          ? "#a5a0ff"
                          : "#8b949e",
                      background:
                        selectedFile?.path === f.path
                          ? "rgba(99,91,255,0.1)"
                          : "transparent",
                      border: "none",
                      cursor: "pointer",
                      fontFamily: "monospace",
                    }}
                  >
                    {f.path}
                  </button>
                ))
              ) : (
                tree.map((node) => (
                  <FileTreeNode
                    key={node.path}
                    node={node}
                    depth={0}
                    selectedPath={selectedFile?.path || ""}
                    onSelect={setSelectedFile}
                    expanded={expanded}
                    onToggle={toggleExpand}
                  />
                ))
              )}
            </div>
          </div>

          {/* Code viewer */}
          <div className="flex-1 flex flex-col overflow-hidden">
            {/* File tab bar */}
            {selectedFile && (
              <div
                className="flex items-center gap-2 px-4 py-2"
                style={{
                  borderBottom: "1px solid #30363d",
                  background: "#161b22",
                }}
              >
                <span style={{ fontSize: 13 }}>
                  {FILE_ICONS[selectedFile.language] || "📄"}
                </span>
                <span
                  style={{
                    color: "#e6edf3",
                    fontSize: 13,
                    fontFamily: "monospace",
                  }}
                >
                  {selectedFile.path}
                </span>
                <span
                  style={{
                    marginLeft: "auto",
                    fontSize: 11,
                    color: "#484f58",
                    fontFamily: "monospace",
                  }}
                >
                  {selectedFile.language} ·{" "}
                  {lines.length} lines ·{" "}
                  {selectedFile.size > 1024
                    ? `${(selectedFile.size / 1024).toFixed(1)} KB`
                    : `${selectedFile.size} B`}
                </span>
              </div>
            )}

            {/* Code content */}
            <div
              className="flex-1 overflow-auto"
              style={{
                fontFamily:
                  "'Consolas', 'Monaco', 'Courier New', monospace",
                fontSize: 13,
                lineHeight: "20px",
                scrollbarWidth: "thin",
                scrollbarColor: "#30363d transparent",
              }}
            >
              {selectedFile ? (
                <table
                  style={{
                    borderCollapse: "collapse",
                    width: "100%",
                    tableLayout: "fixed",
                  }}
                >
                  <tbody>
                    {lines.map((line, i) => (
                      <tr
                        key={i}
                        style={{
                          background:
                            i % 2 === 0
                              ? "transparent"
                              : "rgba(255,255,255,0.01)",
                        }}
                      >
                        <td
                          style={{
                            width: 55,
                            minWidth: 55,
                            textAlign: "right",
                            paddingRight: 12,
                            paddingLeft: 12,
                            color: "#484f58",
                            userSelect: "none",
                            borderRight: "1px solid #21262d",
                            verticalAlign: "top",
                          }}
                        >
                          {i + 1}
                        </td>
                        <td
                          style={{
                            paddingLeft: 16,
                            paddingRight: 16,
                            color: "#e6edf3",
                            whiteSpace: "pre",
                            overflowX: "auto",
                          }}
                        >
                          {highlightLine(line, selectedFile.language)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <div
                  className="flex items-center justify-center h-full"
                  style={{ color: "#484f58" }}
                >
                  Select a file to view
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
