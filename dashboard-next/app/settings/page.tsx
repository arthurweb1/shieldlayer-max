// app/settings/page.tsx
"use client";

import { useState } from "react";

const MODELS = [
  "gpt-4o",
  "gpt-4o-mini",
  "claude-3-5-sonnet-20241022",
  "claude-3-haiku-20240307",
  "meta-llama/Meta-Llama-3-8B-Instruct",
];

export default function SettingsPage() {
  const [upstream, setUpstream] = useState("gpt-4o");
  const [saved, setSaved] = useState(false);

  function handleSave() {
    // In production: POST to gateway /v1/settings
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  return (
    <div className="p-6 max-w-xl">
      <h1 className="text-xl font-semibold mb-6" style={{ color: "#e4e4e7" }}>
        Settings
      </h1>

      <div className="glass-card p-6 flex flex-col gap-6">
        <div className="flex flex-col gap-2">
          <label className="text-xs uppercase tracking-widest" style={{ color: "#71717a" }}>
            Upstream Model
          </label>
          <select
            value={upstream}
            onChange={(e) => setUpstream(e.target.value)}
            className="rounded px-3 py-2 text-sm"
            style={{ background: "#18181b", color: "#e4e4e7", border: "1px solid #3f3f46" }}
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
          <p className="text-xs" style={{ color: "#52525b" }}>
            Routes to OpenAI or Anthropic based on model prefix.
          </p>
        </div>

        <button
          onClick={handleSave}
          className="self-start px-4 py-2 rounded text-sm font-medium transition-colors"
          style={{ background: saved ? "#1e3a5f" : "#3b82f6", color: "#fff" }}
        >
          {saved ? "Saved ✓" : "Save Settings"}
        </button>
      </div>
    </div>
  );
}
