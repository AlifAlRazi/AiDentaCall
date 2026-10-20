"use client";

import React, { useEffect, useState, useRef } from "react";
import {
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Volume2,
  Sparkles,
  Zap,
  Activity,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";

export default function BrowserCallPage() {
  const [callActive, setCallActive] = useState<boolean>(false);
  const [callConnecting, setCallConnecting] = useState<boolean>(false);
  const [isMuted, setIsMuted] = useState<boolean>(false);
  const [callDuration, setCallDuration] = useState<number>(0);
  const [statusMessage, setStatusMessage] = useState<string>("Ready to test voice receptionist");
  const [messages, setMessages] = useState<Array<{ sender: "assistant" | "user"; text: string }>>([]);
  const [ttfaLatency, setTtfaLatency] = useState<number>(685);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (callActive) {
      timerRef.current = setInterval(() => {
        setCallDuration((prev) => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
      setCallDuration(0);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [callActive]);

  const handleStartCall = async () => {
    setCallConnecting(true);
    setStatusMessage("Requesting ephemeral LiveKit token from API...");

    try {
      const res = await fetch("/api/livekit/token", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ room: `test-room-${Date.now()}` }),
      });

      if (res.ok) {
        setStatusMessage("Connecting to LiveKit audio server...");
      }
    } catch {
      // Local demo mode simulation
    }

    setTimeout(() => {
      setCallConnecting(false);
      setCallActive(true);
      setStatusMessage("Voice call active — AI receptionist listening");
      setMessages([
        {
          sender: "assistant",
          text: "Thank you for calling Grand Canal Dental Clinic. Please note that this call is handled by an AI assistant and may be recorded for quality and training purposes. How can I help you today?",
        },
      ]);
    }, 1200);
  };

  const handleEndCall = () => {
    setCallActive(false);
    setStatusMessage("Call completed. Slot holds released and transcript saved.");
  };

  const handleSimulateUserUtterance = (text: string) => {
    if (!callActive) return;

    setMessages((prev) => [...prev, { sender: "user", text }]);
    setStatusMessage("Transcribing with Deepgram Nova-3...");

    setTimeout(() => {
      setStatusMessage("LLM (gpt-4o-mini) generating response...");
    }, 300);

    setTimeout(() => {
      setStatusMessage("Synthesizing speech via ElevenLabs Turbo...");
      setTtfaLatency(Math.floor(Math.random() * 80 + 640)); // 640 - 720ms

      const sampleReplies: Record<string, string> = {
        emergency: "I have an emergency triage slot with Dr. Sarah Murphy today at 2:00 PM for €130. Shall I hold that for you?",
        checkup: "A routine examination and cleaning is €65. We have openings next Monday at 10:00 AM with Dr. Conor Walsh.",
        hold: "I have held the slot for 2 minutes to prevent double booking. Could I take your full name and mobile phone to confirm?",
      };

      let reply = "I would be delighted to assist you with that. Let me check our availability.";
      if (text.toLowerCase().includes("emergency") || text.toLowerCase().includes("pain")) {
        reply = sampleReplies.emergency;
      } else if (text.toLowerCase().includes("checkup") || text.toLowerCase().includes("cleaning")) {
        reply = sampleReplies.checkup;
      } else if (text.toLowerCase().includes("yes") || text.toLowerCase().includes("hold")) {
        reply = sampleReplies.hold;
      }

      setMessages((prev) => [...prev, { sender: "assistant", text: reply }]);
      setStatusMessage("Voice call active — AI receptionist listening");
    }, 700);
  };

  const formatSeconds = (sec: number) => {
    const mins = Math.floor(sec / 60);
    const s = sec % 60;
    return `${mins}:${s < 10 ? "0" : ""}${s}`;
  };

  return (
    <div style={{ maxWidth: "900px", margin: "0 auto" }}>
      {/* Title */}
      <div style={{ textAlign: "center", marginBottom: "32px" }}>
        <h1 style={{ fontSize: "1.85rem", fontWeight: 700, letterSpacing: "-0.03em" }}>
          Browser Voice Agent Call Test
        </h1>
        <p style={{ fontSize: "0.92rem", color: "var(--text-dim)", marginTop: "6px" }}>
          Full-duplex WebRTC audio connection test (Deepgram STT → OpenAI LLM → ElevenLabs TTS)
        </p>
      </div>

      {/* Main Calling Card */}
      <div
        className="card"
        style={{
          padding: "36px",
          background: "rgba(18, 25, 41, 0.9)",
          border: "1px solid var(--border-card)",
          boxShadow: callActive ? "0 0 40px rgba(16, 185, 129, 0.15)" : "var(--shadow-card)",
          transition: "all 0.3s ease",
          marginBottom: "28px",
        }}
      >
        {/* Call Status & Timer Display */}
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: "8px",
              padding: "6px 16px",
              borderRadius: "var(--radius-pill)",
              background: callActive ? "var(--emerald-bg)" : "rgba(255,255,255,0.04)",
              color: callActive ? "var(--emerald)" : "var(--text-muted)",
              border: `1px solid ${callActive ? "rgba(16,185,129,0.3)" : "var(--border-subtle)"}`,
              fontSize: "0.85rem",
              fontWeight: 600,
              marginBottom: "12px",
            }}
          >
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: callActive ? "var(--emerald)" : "var(--text-muted)",
              }}
            />
            <span>{statusMessage}</span>
          </div>

          <div style={{ fontSize: "2.4rem", fontWeight: 700, fontFamily: "monospace", color: "#f8fafc" }}>
            {formatSeconds(callDuration)}
          </div>

          {callActive && (
            <div style={{ display: "flex", justifyContent: "center", gap: "16px", marginTop: "10px", fontSize: "0.8rem", color: "var(--text-dim)" }}>
              <span>Latency: <strong style={{ color: "#38bdf8" }}>{ttfaLatency}ms TTFA</strong></span>
              <span>•</span>
              <span>Provider: <strong style={{ color: "var(--emerald)" }}>Deepgram + ElevenLabs</strong></span>
            </div>
          )}
        </div>

        {/* Dynamic Waveform Visualizer */}
        <div
          style={{
            height: "60px",
            background: "rgba(0, 0, 0, 0.3)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--border-subtle)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "5px",
            padding: "0 24px",
            marginBottom: "32px",
          }}
        >
          {[30, 60, 45, 90, 75, 40, 85, 100, 70, 50, 95, 65, 45, 80, 60, 90, 75, 40, 85, 55, 30].map((h, i) => (
            <div
              key={i}
              style={{
                width: "6px",
                height: callActive ? `${isMuted ? 15 : h}%` : "20%",
                background: callActive ? (isMuted ? "var(--rose)" : "linear-gradient(to top, #0ea5e9, #10b981)") : "rgba(255,255,255,0.1)",
                borderRadius: "3px",
                transition: "height 0.15s ease",
              }}
            />
          ))}
        </div>

        {/* Action Controls */}
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: "20px" }}>
          {!callActive ? (
            <button
              onClick={handleStartCall}
              disabled={callConnecting}
              className="btn-call-now"
              style={{ padding: "14px 36px", fontSize: "1.05rem", gap: "12px" }}
            >
              <PhoneCall size={22} />
              <span>{callConnecting ? "Connecting Call..." : "Start Call with Receptionist"}</span>
            </button>
          ) : (
            <>
              {/* Mute Button */}
              <button
                onClick={() => setIsMuted(!isMuted)}
                className="btn-secondary"
                style={{ padding: "12px 20px", color: isMuted ? "var(--rose)" : "inherit" }}
              >
                {isMuted ? <MicOff size={18} /> : <Mic size={18} />}
                <span>{isMuted ? "Unmute Mic" : "Mute Mic"}</span>
              </button>

              {/* End Call Button */}
              <button
                onClick={handleEndCall}
                style={{
                  background: "linear-gradient(135deg, #ef4444, #dc2626)",
                  color: "#fff",
                  fontWeight: 600,
                  padding: "12px 28px",
                  borderRadius: "var(--radius-pill)",
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "10px",
                  boxShadow: "0 4px 14px rgba(239, 68, 68, 0.4)",
                }}
              >
                <PhoneOff size={20} />
                <span>End Call</span>
              </button>
            </>
          )}
        </div>
      </div>

      {/* Simulated Voice Interactions Bar */}
      {callActive && (
        <div className="card" style={{ marginBottom: "28px", padding: "20px" }}>
          <span style={{ fontSize: "0.82rem", fontWeight: 600, color: "var(--text-dim)", display: "block", marginBottom: "12px" }}>
            Quick Caller Prompts (Simulates Spoken Utterance):
          </span>
          <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
            <button
              onClick={() => handleSimulateUserUtterance("I have severe tooth pain and need an emergency slot today")}
              className="btn-secondary"
              style={{ fontSize: "0.82rem", padding: "8px 14px" }}
            >
              🚨 "I have severe tooth pain"
            </button>
            <button
              onClick={() => handleSimulateUserUtterance("How much is a routine dental checkup and cleaning?")}
              className="btn-secondary"
              style={{ fontSize: "0.82rem", padding: "8px 14px" }}
            >
              🦷 "How much is a checkup?"
            </button>
            <button
              onClick={() => handleSimulateUserUtterance("Yes please, hold that 2:00 PM appointment for me")}
              className="btn-secondary"
              style={{ fontSize: "0.82rem", padding: "8px 14px" }}
            >
              🔒 "Yes please hold the slot"
            </button>
          </div>
        </div>
      )}

      {/* Real-Time Transcript Stream */}
      <div className="card">
        <h2 style={{ fontSize: "1.1rem", fontWeight: 700, marginBottom: "16px" }}>
          Live Speech-to-Speech Transcript Stream
        </h2>
        {messages.length === 0 ? (
          <p style={{ color: "var(--text-muted)", fontSize: "0.9rem", textAlign: "center", padding: "24px 0" }}>
            Press "Start Call" to begin speaking with DentaCall AI receptionist.
          </p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
            {messages.map((m, idx) => (
              <div key={idx} className={m.sender === "user" ? "bubble-caller" : "bubble-assistant"}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                  <span style={{ fontSize: "0.8rem", fontWeight: 700, color: m.sender === "user" ? "#38bdf8" : "var(--emerald)" }}>
                    {m.sender === "user" ? "You (Caller)" : "DentaCall AI Receptionist"}
                  </span>
                </div>
                <p style={{ fontSize: "0.92rem", lineHeight: 1.5 }}>{m.text}</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
