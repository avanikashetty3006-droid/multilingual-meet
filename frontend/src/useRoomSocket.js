import { useEffect, useRef, useState, useCallback } from 'react';

/**
 * Hook for managing the Call Server room WebSocket connection.
 */
export function useRoomSocket({ callServerUrl, roomId, participantId, name, lang, onTranslation }) {
  const [participants, setParticipants] = useState([]);
  const [activeSpeaker, setActiveSpeaker] = useState({ holder: null, overlap: [] });
  const [mode, setMode] = useState({ mode: 'subtitle', reason: 'initial_state' });
  const [connected, setConnected] = useState(false);
  const [lastNetStats, setLastNetStats] = useState(null);

  const socketRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const statsIntervalRef = useRef(null);

  // Send a JSON message
  const send = useCallback((msg) => {
    if (socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      socketRef.current.send(JSON.stringify(msg));
    }
  }, []);

  // Update language
  const setLanguage = useCallback((newLang) => {
    send({ type: 'set_lang', lang: newLang });
  }, [send]);

  useEffect(() => {
    if (!callServerUrl || !roomId || !participantId) return;

    const wsProtocol = callServerUrl.startsWith('https') ? 'wss' : 'ws';
    const cleanHost = callServerUrl.replace(/^https?:\/\//, '');
    const wsUrl = `${wsProtocol}://${cleanHost}/ws/room/${roomId}?participant_id=${participantId}`;

    function connect() {
      const ws = new WebSocket(wsUrl);
      socketRef.current = ws;

      ws.onopen = () => {
        setConnected(true);
        // Step 1: Send hello message
        ws.send(JSON.stringify({
          type: 'hello',
          participant_id: participantId,
          name: name,
          lang: lang,
        }));

        // Periodic net_stats every 2 seconds
        if (statsIntervalRef.current) clearInterval(statsIntervalRef.current);
        statsIntervalRef.current = setInterval(() => {
          // Synthetic or WebRTC-derived network statistics
          const stats = {
            type: 'net_stats',
            rtt_ms: Math.round(40 + Math.random() * 30),
            packet_loss_pct: parseFloat((Math.random() * 0.4).toFixed(1)),
            bitrate_kbps: Math.round(950 + Math.random() * 150),
            jitter_ms: Math.round(5 + Math.random() * 5),
          };
          setLastNetStats(stats);
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(stats));
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
        // Attempt reconnection after 2.5 seconds
        reconnectTimeoutRef.current = setTimeout(connect, 2500);
      };

      ws.onerror = (err) => {
        console.warn('WebSocket encountered error:', err);
        ws.close();
      };
    }

    connect();

    return () => {
      if (statsIntervalRef.current) clearInterval(statsIntervalRef.current);
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (socketRef.current) socketRef.current.close();
    };
  }, [callServerUrl, roomId, participantId, name, lang, onTranslation]);

  return {
    connected,
    participants,
    activeSpeaker,
    mode,
    lastNetStats,
    setLanguage,
  };
}
