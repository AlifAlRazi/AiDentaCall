"use client";

import React, { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Phone,
  Clock,
  DollarSign,
  ShieldAlert,
  Wrench,
  CheckCircle2,
  Play,
  Pause,
  Layers,
  Activity,
  FileText,
  Volume2,
} from "lucide-react";

interface TimelineEvent {
  timestamp_offset_ms: number;
  actor: string;
  event_type: string;
  description: string;
}

interface CallDetail {
  id: string;
  call_sid: string | null;
  caller_phone: string | null;
  direction: string;
  status: string;
  outcome: string;
  duration_seconds: number;
  estimated_cost_usd: number;
  summary: string | null;
  transcript_redacted: string | null;
  tool_calls: Array<{
    tool: string;
    arguments: Record<string, any>;
    duration_ms?: number;
    result?: Record<string, any>;
  }>;
  latency_metrics: {
    stt_ms?: number;
    llm_ttft_ms?: number;
    tool_ms?: number;
    tts_ttfb_ms?: number;
    total_ttfa_ms?: number;
    target_met?: boolean;
  } | null;
  cost_breakdown: {
    twilio_cost_usd?: number;
    deepgram_cost_usd?: number;
    openai_cost_usd?: number;
    elevenlabs_cost_usd?: number;
    livekit_cost_usd?: number;
    total_cost_usd?: number;
  } | null;
  token_usage: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  } | null;
  timeline: TimelineEvent[];
  created_at_utc: string;
}

export default function CallDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);
  const [call, setCall] = useState<CallDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"transcript" | "tools" | "timeline" | "telemetry">("transcript");
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);

  useEffect(() => {
    async function loadCall() {
      try {
        const res = await fetch(`/api/dashboard/calls/${resolvedParams.id}`);
        if (res.ok) {
          const json = await res.json();
          setCall(json);
        }
      } catch {
        // Fallback seeded payload handled by API
      } finally {
        setLoading(false);
      }
    }
    loadCall();
  }, [resolvedParams.id]);

  const renderHighlightedTranscript = (rawText: string | null) => {
    if (!rawText) return <p style={{ color: "var(--text-muted)" }}>No transcript recorded for this call.</p>;

    const lines = rawText.split("\n").filter((l) => l.trim().length > 0);
    return lines.map((line, idx) => {
      const isCaller = line.startsWith("Caller:") || line.startsWith("User:");
      const speaker = isCaller ? "Caller" : "AI Receptionist";
      const content = line.substring(line.indexOf(":") + 1).trim();

      // Highlight [REDACTED_PHONE] and [REDACTED_EMAIL]
      const parts = content.split(/(\[REDACTED_PHONE\]|\[REDACTED_EMAIL\])/g);

      return (
        <div key={idx} className={isCaller ? "bubble-caller" : "bubble-assistant"}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "6px" }}>
            <span style={{ fontSize: "0.8rem", fontWeight: 700, color: isCaller ? "#38bdf8" : "var(--emerald)" }}>
              {speaker}
            </span>
          </div>
          <p style={{ fontSize: "0.92rem", lineHeight: 1.6 }}>
            {parts.map((p, pIdx) => {
              if (p === "[REDACTED_PHONE]") {
                return (
                  <span key={pIdx} className="redacted-tag" title="Protected under GDPR / Irish Healthcare Privacy">
                    [REDACTED_PHONE]
                  </span>
                );
              }
              if (p === "[REDACTED_EMAIL]") {
                return (
                  <span key={pIdx} className="redacted-tag" title="Protected under GDPR / Irish Healthcare Privacy">
                    [REDACTED_EMAIL]
                  </span>
                );
              }
              return p;
            })}
          </p>
        </div>
      );
    });
  };

  if (loading) {
    return <div style={{ padding: "40px", color: "var(--text-dim)" }}>Loading call detail...</div>;
  }

  if (!call) {
    return (
      <div style={{ padding: "40px", textAlign: "center" }}>
        <p style={{ color: "var(--rose)", marginBottom: "16px" }}>Call record not found.</p>
        <Link href="/calls" className="btn-secondary">
          <ArrowLeft size={16} />
          <span>Return to Call Logs</span>
        </Link>
      </div>
    );
  }

  return (
    <div>
      {/* Back button */}
      <div style={{ marginBottom: "20px" }}>
        <Link href="/calls" className="btn-secondary" style={{ padding: "6px 14px", fontSize: "0.85rem" }}>
          <ArrowLeft size={14} />
          <span>Back to All Calls</span>
        </Link>
      </div>

      {/* Hero Header Card */}
      <div className="card" style={{ marginBottom: "24px", padding: "28px" }}>
        <div style={{ display: "flex", flexWrap: "wrap", alignItems: "flex-start", justifyContent: "space-between", gap: "20px" }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: "12px", marginBottom: "8px" }}>
              <div style={{ padding: "8px", background: "rgba(14, 165, 233, 0.12)", color: "#38bdf8", borderRadius: "8px" }}>
                <Phone size={20} />
              </div>
              <h1 style={{ fontSize: "1.6rem", fontWeight: 700 }}>
                {call.caller_phone || "Inbound WebRTC Call"}
              </h1>
              <span className={`badge ${call.outcome === "BOOKED" ? "badge-emerald" : call.outcome === "DROPPED" ? "badge-rose" : "badge-blue"}`}>
                {call.outcome}
              </span>
            </div>
            <p style={{ fontSize: "0.88rem", color: "var(--text-dim)", maxWidth: "700px" }}>
              {call.summary || "Inbound dental clinic appointment call."}
            </p>
          </div>

          {/* Quick Metrics Pills */}
          <div style={{ display: "flex", gap: "16px", flexWrap: "wrap" }}>
            <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", padding: "10px 16px", borderRadius: "10px" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block" }}>DURATION</span>
              <strong style={{ fontSize: "1.1rem", color: "#f8fafc" }}>{Math.round(call.duration_seconds)}s</strong>
            </div>
            <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", padding: "10px 16px", borderRadius: "10px" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block" }}>ITEMIZED COST</span>
              <strong style={{ fontSize: "1.1rem", color: "#38bdf8" }}>${call.estimated_cost_usd.toFixed(4)}</strong>
            </div>
            <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid var(--border-subtle)", padding: "10px 16px", borderRadius: "10px" }}>
              <span style={{ fontSize: "0.72rem", color: "var(--text-muted)", display: "block" }}>TOOLS EXECUTED</span>
              <strong style={{ fontSize: "1.1rem", color: "var(--emerald)" }}>{call.tool_calls.length} tools</strong>
            </div>
          </div>
        </div>

        {/* Audio Player Simulator */}
        <div
          style={{
            marginTop: "24px",
            padding: "16px 20px",
            background: "rgba(0, 0, 0, 0.25)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-md)",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "20px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
            <button
              onClick={() => setIsPlayingAudio(!isPlayingAudio)}
              style={{
                width: "40px",
                height: "40px",
                borderRadius: "50%",
                background: isPlayingAudio ? "var(--rose)" : "var(--primary)",
                color: "#fff",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                boxShadow: "0 0 14px rgba(14, 165, 233, 0.4)",
              }}
            >
              {isPlayingAudio ? <Pause size={18} /> : <Play size={18} style={{ marginLeft: "2px" }} />}
            </button>
            <div>
              <p style={{ fontSize: "0.85rem", fontWeight: 600 }}>Call Audio Recording (Twilio & LiveKit)</p>
              <p style={{ fontSize: "0.72rem", color: "var(--text-dim)" }}>
                {isPlayingAudio ? "Playing back dual-channel audio stream..." : "Encrypted clinical audio storage (90-day retention)"}
              </p>
            </div>
          </div>

          {/* Waveform Bars */}
          <div style={{ display: "flex", alignItems: "center", gap: "3px", height: "24px", flex: 1, maxWidth: "400px" }}>
            {[40, 60, 20, 80, 50, 90, 70, 30, 85, 45, 100, 65, 35, 75, 55, 95, 60, 40, 80, 50, 25, 70].map((h, i) => (
              <div
                key={i}
                style={{
                  width: "4px",
                  height: isPlayingAudio ? `${h}%` : "30%",
                  background: isPlayingAudio ? "#38bdf8" : "rgba(255,255,255,0.15)",
                  borderRadius: "2px",
                  transition: "height 0.2s ease, background 0.2s ease",
                }}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Tabs Bar */}
      <div style={{ display: "flex", gap: "10px", marginBottom: "20px" }}>
        {[
          { key: "transcript", label: "Redacted Transcript", icon: FileText },
          { key: "tools", label: `Tool Invocations (${call.tool_calls.length})`, icon: Wrench },
          { key: "timeline", label: "Event Timeline", icon: Clock },
          { key: "telemetry", label: "Latency & Costs", icon: Activity },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.key;
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key as any)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "10px 18px",
                borderRadius: "var(--radius-md)",
                fontSize: "0.88rem",
                fontWeight: isActive ? 600 : 500,
                background: isActive ? "var(--bg-card)" : "transparent",
                color: isActive ? "#38bdf8" : "var(--text-dim)",
                border: isActive ? "1px solid var(--border-highlight)" : "1px solid transparent",
                transition: "all 0.15s ease",
              }}
            >
              <Icon size={16} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: Transcript */}
      {activeTab === "transcript" && (
        <div className="card">
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700 }}>Dual-Channel Conversation Transcript</h2>
            <span style={{ fontSize: "0.78rem", color: "var(--emerald)", display: "flex", alignItems: "center", gap: "6px" }}>
              <CheckCircle2 size={14} />
              <span>PII Automatically Redacted</span>
            </span>
          </div>
          <div>{renderHighlightedTranscript(call.transcript_redacted)}</div>
        </div>
      )}

      {/* TAB 2: Tool Invocations */}
      {activeTab === "tools" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
          {call.tool_calls.map((t, idx) => (
            <div key={idx} className="card" style={{ borderLeft: "4px solid #38bdf8" }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "12px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <span style={{ padding: "4px 8px", background: "rgba(56, 189, 248, 0.15)", color: "#38bdf8", borderRadius: "6px", fontFamily: "monospace", fontWeight: 700 }}>
                    Step {idx + 1}
                  </span>
                  <strong style={{ fontSize: "1rem" }}>{t.tool}</strong>
                </div>
                {t.duration_ms && (
                  <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                    Execution: <strong>{t.duration_ms}ms</strong>
                  </span>
                )}
              </div>

              {/* Arguments & Result in code blocks */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px", marginTop: "12px" }}>
                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 600 }}>
                    Arguments Passed:
                  </span>
                  <pre style={{ marginTop: "6px", padding: "12px", background: "rgba(0,0,0,0.3)", borderRadius: "8px", fontSize: "0.82rem", overflowX: "auto", color: "#e2e8f0" }}>
                    {JSON.stringify(t.arguments, null, 2)}
                  </pre>
                </div>
                <div>
                  <span style={{ fontSize: "0.75rem", color: "var(--text-dim)", textTransform: "uppercase", fontWeight: 600 }}>
                    Tool Result Envelope:
                  </span>
                  <pre style={{ marginTop: "6px", padding: "12px", background: "rgba(0,0,0,0.3)", borderRadius: "8px", fontSize: "0.82rem", overflowX: "auto", color: "#34d399" }}>
                    {JSON.stringify(t.result || { success: true }, null, 2)}
                  </pre>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* TAB 3: Event Timeline */}
      {activeTab === "timeline" && (
        <div className="card">
          <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "20px" }}>
            Chronological Call Lifecycle Flow
          </h2>
          <div style={{ position: "relative", paddingLeft: "28px" }}>
            <div style={{ position: "absolute", left: "9px", top: "8px", bottom: "8px", width: "2px", background: "rgba(255,255,255,0.1)" }} />
            {call.timeline.map((event, idx) => (
              <div key={idx} style={{ position: "relative", marginBottom: "24px" }}>
                <div
                  style={{
                    position: "absolute",
                    left: "-28px",
                    top: "3px",
                    width: "18px",
                    height: "18px",
                    borderRadius: "50%",
                    background: event.actor === "SYSTEM" ? "var(--purple)" : event.actor === "TOOL" ? "#38bdf8" : "var(--emerald)",
                    border: "3px solid var(--bg-card)",
                  }}
                />
                <div>
                  <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                    <span style={{ fontSize: "0.88rem", fontWeight: 600, color: "#f8fafc" }}>
                      {event.event_type}
                    </span>
                    <span style={{ fontSize: "0.75rem", color: "var(--text-muted)", fontFamily: "monospace" }}>
                      +{event.timestamp_offset_ms}ms
                    </span>
                    <span className="badge badge-blue" style={{ fontSize: "0.65rem", padding: "2px 6px" }}>
                      {event.actor}
                    </span>
                  </div>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-dim)", marginTop: "4px" }}>
                    {event.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* TAB 4: Latency & Cost Breakdown */}
      {activeTab === "telemetry" && (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "24px" }}>
          {/* Latency Telemetry */}
          <div className="card">
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px" }}>
              Audio Pipeline Latency
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "10px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                <span>Deepgram STT Streaming</span>
                <strong style={{ color: "#38bdf8" }}>{call.latency_metrics?.stt_ms ?? 185}ms</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "10px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                <span>OpenAI LLM Time to First Token (TTFT)</span>
                <strong style={{ color: "var(--amber)" }}>{call.latency_metrics?.llm_ttft_ms ?? 280}ms</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "10px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                <span>Internal Clinic Tool Dispatch</span>
                <strong style={{ color: "var(--purple)" }}>{call.latency_metrics?.tool_ms ?? 68}ms</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "10px", background: "rgba(255,255,255,0.02)", borderRadius: "8px" }}>
                <span>ElevenLabs TTS Time to First Byte (TTFB)</span>
                <strong style={{ color: "var(--emerald)" }}>{call.latency_metrics?.tts_ttfb_ms ?? 140}ms</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", padding: "12px", background: "rgba(16, 185, 129, 0.1)", borderRadius: "8px", border: "1px solid rgba(16, 185, 129, 0.3)" }}>
                <strong>Total Time to First Audio (TTFA)</strong>
                <strong style={{ color: "var(--emerald)", fontSize: "1.1rem" }}>
                  {call.latency_metrics?.total_ttfa_ms ?? 673}ms
                </strong>
              </div>
            </div>
          </div>

          {/* Itemized Cost Breakdown */}
          <div className="card">
            <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px" }}>
              Itemized Provider Cost Breakdown
            </h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "12px", fontSize: "0.88rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-dim)" }}>Twilio Voice ($0.014/min)</span>
                <strong>${(call.cost_breakdown?.twilio_cost_usd ?? 0.0315).toFixed(4)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-dim)" }}>Deepgram Nova-3 ($0.0043/min)</span>
                <strong>${(call.cost_breakdown?.deepgram_cost_usd ?? 0.0097).toFixed(4)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-dim)" }}>OpenAI gpt-4o-mini tokens</span>
                <strong>${(call.cost_breakdown?.openai_cost_usd ?? 0.0011).toFixed(4)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-dim)" }}>ElevenLabs Turbo v2.5 voice</span>
                <strong>${(call.cost_breakdown?.elevenlabs_cost_usd ?? 0.0172).toFixed(4)}</strong>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between" }}>
                <span style={{ color: "var(--text-dim)" }}>LiveKit Cloud WebRTC Audio</span>
                <strong>${(call.cost_breakdown?.livekit_cost_usd ?? 0.0090).toFixed(4)}</strong>
              </div>

              <div style={{ borderTop: "1px solid var(--border-card)", paddingTop: "12px", marginTop: "4px", display: "flex", justifyContent: "space-between" }}>
                <strong style={{ fontSize: "1rem" }}>Total Call Cost</strong>
                <strong style={{ color: "#38bdf8", fontSize: "1.15rem" }}>
                  ${(call.cost_breakdown?.total_cost_usd ?? call.estimated_cost_usd).toFixed(4)}
                </strong>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
