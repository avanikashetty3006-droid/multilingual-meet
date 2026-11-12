import { useEffect, useRef, useState } from "react";
import { audioQueue } from "./audioQueue";

export function useRoomSocket(roomId, participantId, name, lang) {
  const [participants, setParticipants] = useState([]);
  const [activeSpeaker, setActiveSpeaker] = useState({ holder: null, overlap: [] });
  const [currentMode, setCurrentMode] = useState("subtitle");
  const [translations, setTranslations] = useState([]);
  const [overlapTranslations, setOverlapTranslations] = useState([]);
  const socketRef = useRef(null);

  useEffect(() => {
    if (!roomId || !participantId) return;

    const wsUrl = `ws://localhost:8000/ws/room/${roomId}?participant_id=${participantId}`;
    const ws = new WebSocket(wsUrl);
    socketRef.current = ws;

    ws.onopen = () => {
      // Send hello
      ws.send(JSON.stringify({ type: "hello", participant_id: participantId, name, lang }));
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "participants") {
          setParticipants(msg.list || []);
        } else if (msg.type === "active_speaker") {
          setActiveSpeaker({ holder: msg.holder, overlap: msg.overlap || [] });
        } else if (msg.type === "mode") {
          setCurrentMode(msg.mode);
        } else if (msg.type === "translation") {
          if (msg.lane === "main") {
            setTranslations((prev) => [...prev.slice(-10), msg]);
            if (msg.mode === "audio" && msg.audio_url) {
              audioQueue.enqueue(msg.audio_url);
            }
          } else {
            setOverlapTranslations((prev) => [...prev.slice(-5), msg]);
          }
        }
      } catch (err) {
        console.error("Failed to parse room event:", err);
      }
    };

    // Net stats reporter every 2s
    const statsTimer = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(
          JSON.stringify({
            type: "net_stats",
            rtt_ms: 80,
            packet_loss_pct: 0.1,
            bitrate_kbps: 850,
            jitter_ms: 10,
          })
        );
      }
    }, 2000);

    return () => {
      clearInterval(statsTimer);
      ws.close();
      audioQueue.clear();
    };
  }, [roomId, participantId, name, lang]);

  const setLanguage = (newLang) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify({ type: "set_lang", lang: newLang }));
    }
  };

  return {
    participants,
    activeSpeaker,
    currentMode,
    translations,
    overlapTranslations,
    setLanguage,
  };
}
