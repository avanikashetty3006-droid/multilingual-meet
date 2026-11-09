import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Hook for managing the Call Server room WebSocket connection.
 * Features:
 * - Real WebRTC getStats integration (rtt, packet loss, bitrate, jitter).
 * - "closedByUs" flag to permanently prevent ghost reconnects on leave.
 * - Decoupled language/name dependencies so set_lang does not re-trigger connection.
 */
export function useRoomSocket({
  callServerUrl,
  roomId,
  participantId,
  name,
  lang,
  onTranslation,
  getLiveKitStats, // Function returning Promise<{ rtt_ms, packet_loss_pct, bitrate_kbps, jitter_ms }>
}) {
  const [participants, setParticipants] = useState([]);
  const [activeSpeaker, setActiveSpeaker] = useState({ holder: null, overlap: [] });
  const [mode, setMode] = useState({ mode: 'subtitle', reason: 'initial_state' });
  const [connected, setConnected] = useState(false);
  const [lastNetStats, setLastNetStats] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const statsIntervalRef = useRef(null);
  const closedByUsRef = useRef(false);

  // Keep references to latest name and lang without re-triggering connection effect
  const nameRef = useRef(name);
  nameRef.current = name;
  const langRef = useRef(lang);
  langRef.current = lang;

  // Send a JSON message
  const send = useCallback((msg) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(msg));
    }
  }, []);

  // Update language via WebSocket without reconnecting
  const setLanguage = useCallback((newLang) => {
    langRef.current = newLang;
    send({ type: 'set_lang', lang: newLang });
  }, [send]);

  useEffect(() => {
    if (!callServerUrl || !roomId || !participantId) return;

    closedByUsRef.current = false;

    const wsProtocol = callServerUrl.startsWith('https') ? 'wss' : 'ws';
    const cleanHost = callServerUrl.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}://${cleanHost}/ws/room/${roomId}?participant_id=${participantId}`;

    function connect() {
      if (closedByUsRef.current) return;

      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        if (closedByUsRef.current) {
          ws.close();
          return;
        }

        setConnected(true);

        // Send hello with latest credentials
        ws.send(JSON.stringify({
          type: 'hello',
          participant_id: participantId,
          name: nameRef.current,
          lang: langRef.current,
        }));

        // Periodic real WebRTC net_stats every 2 seconds
        if (statsIntervalRef.current) clearInterval(statsIntervalRef.current);
        statsIntervalRef.current = setInterval(async () => {
          if (closedByUsRef.current) return;

          let realStats = null;
          if (getLiveKitStats) {
            try {
              realStats = await getLiveKitStats();
            } catch (err) {
              console.warn('Error reading WebRTC stats:', err);
            }
          }

          // Fallback only if getLiveKitStats is unavailable yet
          const statsPayload = {
            type: 'net_stats',
            rtt_ms: realStats?.rtt_ms ?? 50,
            packet_loss_pct: realStats?.packet_loss_pct ?? 0.0,
            bitrate_kbps: realStats?.bitrate_kbps ?? 850,
            jitter_ms: realStats?.jitter_ms ?? 10,
          };

          setLastNetStats(statsPayload);
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(statsPayload));
          }
        }, 2000);
      };

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          switch (msg.type) {
            case 'participants':
              setParticipants(msg.list || []);
              break;
            case 'active_speaker':
              setActiveSpeaker({ holder: msg.holder, overlap: msg.overlap || [] });
              break;
            case 'mode':
              setMode({ mode: msg.mode, reason: msg.reason });
              break;
            case 'translation':
              onTranslation?.(msg);
              break;
            case 'error':
              console.error('Call server error:', msg.message);
              break;
            default:
              break;
          }
        } catch (e) {
          console.warn('Failed to parse WS message:', e);
        }
      };

      ws.onclose = () => {
        setConnected(false);
        if (statsIntervalRef.current) clearInterval(statsIntervalRef.current);

        // Ghost reconnect fix: only reconnect if NOT intentionally closed by us
        if (!closedByUsRef.current) {
          reconnectTimeoutRef.current = setTimeout(connect, 2500);
        }
      };

      ws.onerror = (err) => {
        console.warn('WebSocket encountered error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      // Mark as explicitly closed by us to prevent ghost reconnect
      closedByUsRef.current = true;
      if (statsIntervalRef.current) clearInterval(statsIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [callServerUrl, roomId, participantId, onTranslation, getLiveKitStats]);

  return {
    connected,
    participants,
    activeSpeaker,
    mode,
    lastNetStats,
    setLanguage,
  };
}
