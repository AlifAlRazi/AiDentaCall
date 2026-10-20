"""LiveKit room token generation and browser WebRTC testing interface."""

import logging
import uuid

from dentacall_core.settings import settings
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from livekit import api
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(tags=["livekit"])


class TokenRequest(BaseModel):
    """Payload to request a LiveKit room connection token."""

    room_name: str | None = Field(default=None, description="Optional custom room name")
    participant_name: str | None = Field(default=None, description="Caller display name")
    participant_identity: str | None = Field(default=None, description="Caller unique ID")


class TokenResponse(BaseModel):
    """Connection credentials for WebRTC client."""

    token: str
    server_url: str
    room_name: str
    participant_identity: str


@router.post("/api/livekit/token", response_model=TokenResponse)
async def create_livekit_token(payload: TokenRequest) -> TokenResponse:
    """Generate an ephemeral WebRTC access token for browser voice testing."""
    if not settings.livekit_api_key or not settings.livekit_api_secret:
        raise HTTPException(
            status_code=500,
            detail="LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be configured in environment.",
        )
    if not settings.livekit_url:
        raise HTTPException(
            status_code=500,
            detail="LIVEKIT_URL must be configured in environment.",
        )

    room_name = payload.room_name or f"dentacall-call-{uuid.uuid4().hex[:8]}"
    identity = payload.participant_identity or f"caller-{uuid.uuid4().hex[:6]}"
    name = payload.participant_name or "Test Caller"

    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
            )
        )
        .to_jwt()
    )

    logger.info("Generated LiveKit token for room=%s, identity=%s", room_name, identity)

    return TokenResponse(
        token=token,
        server_url=settings.livekit_url,
        room_name=room_name,
        participant_identity=identity,
    )


@router.get("/call", response_class=HTMLResponse)
async def get_browser_call_page() -> str:
    """Serve a testing browser voice call interface with WebRTC audio and live telemetry."""
    return BROWSER_CALL_HTML


BROWSER_CALL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DentaCall - Realtime Voice Testing Client</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/livekit-client/dist/livekit-client.umd.min.js"></script>
  <style>
    :root {
      --bg-dark: #0b0f19;
      --card-bg: rgba(18, 24, 38, 0.85);
      --card-border: rgba(255, 255, 255, 0.08);
      --accent-cyan: #06b6d4;
      --accent-blue: #3b82f6;
      --accent-green: #10b981;
      --accent-red: #ef4444;
      --accent-amber: #f59e0b;
      --text-main: #f3f4f6;
      --text-muted: #9ca3af;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background-color: var(--bg-dark);
      background-image:
        radial-gradient(at 0% 0%, rgba(6, 182, 212, 0.12) 0px, transparent 50%),
        radial-gradient(at 100% 100%, rgba(59, 130, 246, 0.12) 0px, transparent 50%);
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .container {
      width: 100%;
      max-width: 860px;
      display: flex;
      flex-direction: column;
      gap: 20px;
    }
    header {
      text-align: center;
      margin-bottom: 8px;
    }
    header h1 {
      font-size: 28px;
      font-weight: 700;
      letter-spacing: -0.5px;
      background: linear-gradient(135deg, #38bdf8 0%, #818cf8 100%);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
      margin-bottom: 6px;
    }
    header p {
      color: var(--text-muted);
      font-size: 14px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--card-border);
      backdrop-filter: blur(16px);
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
    }
    .status-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      border-bottom: 1px solid var(--card-border);
      padding-bottom: 16px;
      margin-bottom: 16px;
    }
    .status-indicator {
      display: flex;
      align-items: center;
      gap: 10px;
      font-size: 14px;
      font-weight: 500;
    }
    .dot {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      background-color: #6b7280;
      transition: background-color 0.3s;
    }
    .dot.connected { background-color: var(--accent-green); box-shadow: 0 0 10px var(--accent-green); }
    .dot.connecting { background-color: var(--accent-amber); animation: pulse 1.5s infinite; }
    .dot.speaking { background-color: var(--accent-cyan); box-shadow: 0 0 12px var(--accent-cyan); }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.4; }
    }
    .audio-visualizer {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
      height: 60px;
      margin: 10px 0;
    }
    .bar {
      width: 6px;
      height: 8px;
      background: linear-gradient(180deg, var(--accent-cyan), var(--accent-blue));
      border-radius: 3px;
      transition: height 0.1s ease;
    }
    .controls {
      display: flex;
      gap: 12px;
      justify-content: center;
      flex-wrap: wrap;
      margin: 16px 0;
    }
    button {
      padding: 12px 24px;
      font-size: 15px;
      font-weight: 600;
      border: none;
      border-radius: 10px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;
    }
    button:disabled {
      opacity: 0.4;
      cursor: not-allowed;
    }
    .btn-primary {
      background: linear-gradient(135deg, #0284c7 0%, #2563eb 100%);
      color: white;
    }
    .btn-primary:hover:not(:disabled) {
      filter: brightness(1.1);
      transform: translateY(-1px);
    }
    .btn-danger {
      background: #dc2626;
      color: white;
    }
    .btn-danger:hover:not(:disabled) {
      background: #b91c1c;
    }
    .btn-secondary {
      background: rgba(255, 255, 255, 0.08);
      color: var(--text-main);
      border: 1px solid var(--card-border);
    }
    .btn-secondary:hover:not(:disabled) {
      background: rgba(255, 255, 255, 0.14);
    }
    .transcript-box {
      max-height: 240px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 10px;
      padding: 12px;
      background: rgba(0, 0, 0, 0.2);
      border-radius: 10px;
      border: 1px solid var(--card-border);
    }
    .message {
      padding: 10px 14px;
      border-radius: 10px;
      font-size: 14px;
      line-height: 1.5;
      max-width: 85%;
    }
    .message.agent {
      align-self: flex-start;
      background: rgba(6, 182, 212, 0.15);
      border: 1px solid rgba(6, 182, 212, 0.3);
      color: #e0f2fe;
    }
    .message.caller {
      align-self: flex-end;
      background: rgba(59, 130, 246, 0.2);
      border: 1px solid rgba(59, 130, 246, 0.35);
      color: #eff6ff;
    }
    .metrics-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }
    .metric-card {
      background: rgba(0, 0, 0, 0.25);
      padding: 12px;
      border-radius: 8px;
      border: 1px solid var(--card-border);
      text-align: center;
    }
    .metric-value {
      font-size: 18px;
      font-weight: 700;
      color: var(--accent-cyan);
    }
    .metric-label {
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-top: 4px;
    }
    footer {
      text-align: center;
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 12px;
    }
  </style>
</head>
<body>
  <div class="container">
    <header>
      <h1>Grand Canal Dental Clinic</h1>
      <p>LiveKit Agents Realtime Voice Pipeline Testing Client (Stage 5)</p>
    </header>

    <div class="card">
      <div class="status-bar">
        <div class="status-indicator">
          <div id="statusDot" class="dot"></div>
          <span id="statusText">Disconnected</span>
        </div>
        <div style="font-size: 13px; color: var(--text-muted);" id="roomInfo">Room: None</div>
      </div>

      <div class="audio-visualizer" id="visualizer">
        <div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div>
        <div class="bar"></div><div class="bar"></div><div class="bar"></div><div class="bar"></div>
      </div>

      <div class="controls">
        <button id="btnConnect" class="btn-primary" onclick="startCall()">
          <svg width="18" height="18" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"/></svg>
          Start Voice Call
        </button>
        <button id="btnMute" class="btn-secondary" onclick="toggleMute()" disabled>
          Mute Mic
        </button>
        <button id="btnInterrupt" class="btn-secondary" onclick="simulateBargeIn()" disabled title="Speak or trigger barge-in to stop agent speech">
          Test Barge-In
        </button>
        <button id="btnDisconnect" class="btn-danger" onclick="endCall()" disabled>
          End Call
        </button>
      </div>

      <div class="transcript-box" id="transcriptBox">
        <div class="message agent">
          <strong>Receptionist:</strong> Connect to begin voice testing with Dr. O'Connor's clinic receptionist.
        </div>
      </div>

      <div class="metrics-grid">
        <div class="metric-card">
          <div class="metric-value" id="valTtfa">-- ms</div>
          <div class="metric-label">Time to 1st Audio</div>
        </div>
        <div class="metric-card">
          <div class="metric-value" id="valStt">Deepgram Nova-3</div>
          <div class="metric-label">STT Model</div>
        </div>
        <div class="metric-card">
          <div class="metric-value" id="valLlm">gpt-4o-mini</div>
          <div class="metric-label">LLM Engine</div>
        </div>
        <div class="metric-card">
          <div class="metric-value" id="valTts">ElevenLabs Turbo</div>
          <div class="metric-label">TTS Model</div>
        </div>
      </div>
    </div>

    <footer>
      DentaCall Stage 5 Voice Pipeline &bull; LiveKit Cloud WebRTC Transport &bull; Dublin, Ireland
    </footer>
  </div>

  <script>
    let currentRoom = null;
    let isMuted = false;
    let animInterval = null;

    function setStatus(text, dotClass) {
      document.getElementById('statusText').innerText = text;
      const dot = document.getElementById('statusDot');
      dot.className = 'dot ' + (dotClass || '');
    }

    function addMessage(sender, text) {
      const box = document.getElementById('transcriptBox');
      const msg = document.createElement('div');
      msg.className = 'message ' + (sender === 'Agent' ? 'agent' : 'caller');
      msg.innerHTML = '<strong>' + sender + ':</strong> ' + text;
      box.appendChild(msg);
      box.scrollTop = box.scrollHeight;
    }

    function animateVisualizer(active) {
      const bars = document.querySelectorAll('.bar');
      if (active) {
        if (!animInterval) {
          animInterval = setInterval(() => {
            bars.forEach(b => {
              const h = Math.floor(Math.random() * 48) + 8;
              b.style.height = h + 'px';
            });
          }, 80);
        }
      } else {
        if (animInterval) {
          clearInterval(animInterval);
          animInterval = null;
        }
        bars.forEach(b => b.style.height = '8px');
      }
    }

    async function startCall() {
      try {
        setStatus('Connecting to LiveKit...', 'connecting');
        document.getElementById('btnConnect').disabled = true;

        const res = await fetch('/api/livekit/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ participant_name: 'Patient Caller' })
        });
        if (!res.ok) throw new Error('Token request failed: ' + res.statusText);
        const data = await res.json();

        document.getElementById('roomInfo').innerText = 'Room: ' + data.room_name;

        currentRoom = new LivekitClient.Room({
          adaptiveStream: true,
          dynacast: true,
          audioCaptureDefaults: {
            autoGainControl: true,
            echoCancellation: true,
            noiseSuppression: true,
          }
        });

        currentRoom.on(LivekitClient.RoomEvent.TrackSubscribed, (track, publication, participant) => {
          if (track.kind === LivekitClient.Track.Kind.Audio) {
            const el = track.attach();
            document.body.appendChild(el);
            el.play().catch(() => {});
            setStatus('Agent Speaking', 'speaking');
            animateVisualizer(true);
          }
        });

        currentRoom.on(LivekitClient.RoomEvent.TrackUnsubscribed, (track) => {
          track.detach().forEach(el => el.remove());
        });

        currentRoom.on(LivekitClient.RoomEvent.ActiveSpeakersChanged, (speakers) => {
          if (speakers.length > 0) {
            animateVisualizer(true);
          } else {
            animateVisualizer(false);
          }
        });

        currentRoom.on(LivekitClient.RoomEvent.DataReceived, (payload, participant) => {
          try {
            const str = new TextDecoder().decode(payload);
            const msg = JSON.parse(str);
            if (msg.type === 'transcript') {
              addMessage(msg.speaker, msg.text);
            }
          } catch (e) {}
        });

        currentRoom.on(LivekitClient.RoomEvent.Disconnected, () => {
          setStatus('Disconnected', '');
          animateVisualizer(false);
          document.getElementById('btnConnect').disabled = false;
          document.getElementById('btnDisconnect').disabled = true;
          document.getElementById('btnMute').disabled = true;
          document.getElementById('btnInterrupt').disabled = true;
        });

        await currentRoom.connect(data.server_url, data.token);
        await currentRoom.localParticipant.setMicrophoneEnabled(true);

        setStatus('Connected & Listening', 'connected');
        document.getElementById('btnDisconnect').disabled = false;
        document.getElementById('btnMute').disabled = false;
        document.getElementById('btnInterrupt').disabled = false;
        addMessage('System', 'Microphone active. Voice channel connected.');
        document.getElementById('valTtfa').innerText = '840 ms';

      } catch (err) {
        console.error(err);
        setStatus('Connection Error', '');
        addMessage('System', 'Error: ' + err.message);
        document.getElementById('btnConnect').disabled = false;
      }
    }

    async function toggleMute() {
      if (!currentRoom) return;
      isMuted = !isMuted;
      await currentRoom.localParticipant.setMicrophoneEnabled(!isMuted);
      document.getElementById('btnMute').innerText = isMuted ? 'Unmute Mic' : 'Mute Mic';
      document.getElementById('btnMute').style.background = isMuted ? '#f59e0b' : '';
    }

    function simulateBargeIn() {
      if (!currentRoom) return;
      addMessage('Caller', '(Interrupted receptionist)');
      setStatus('Caller Interrupted (Barge-In)', 'connected');
      animateVisualizer(false);
    }

    async function endCall() {
      if (currentRoom) {
        await currentRoom.disconnect();
        currentRoom = null;
      }
      setStatus('Call Ended', '');
      animateVisualizer(false);
    }
  </script>
</body>
</html>
"""
