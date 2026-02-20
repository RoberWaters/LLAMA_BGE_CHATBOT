import React, {
  useRef,
  useEffect,
  useState,
  useImperativeHandle,
  forwardRef,
} from 'react';
import { SimliClient, generateSimliSessionToken } from 'simli-client';
import '../App.css';

/**
 * Avatar de tiempo real con Simli.
 *
 * Props:
 *   apiKey  – clave SIMLI_API obtenida del backend
 *   faceId  – FACE_ID_SIMLI obtenido del backend
 *
 * Ref expone:
 *   sendAudio(pcmUint8Array)  – envía audio PCM16 @ 16 kHz al avatar
 *   clearBuffer()             – detiene la voz del avatar
 *   isConnected()             – devuelve true si el avatar está listo
 */
const SimliAvatar = forwardRef(({ apiKey, faceId }, ref) => {
  const videoRef = useRef(null);
  const audioRef = useRef(null);
  const clientRef = useRef(null);
  const [status, setStatus] = useState('connecting'); // connecting | connected | error

  /* Exponer métodos al componente padre */
  useImperativeHandle(ref, () => ({
    sendAudio: (pcmUint8Array) => {
      if (clientRef.current) {
        clientRef.current.sendAudioData(pcmUint8Array);
      }
    },
    clearBuffer: () => {
      if (clientRef.current) {
        clientRef.current.ClearBuffer();
      }
    },
    isConnected: () => status === 'connected',
    /** Silencia/desilencia el elemento <audio> del avatar */
    muteOutput: (muted) => {
      if (audioRef.current) audioRef.current.muted = muted;
    },
  }));

  useEffect(() => {
    if (!apiKey || !faceId || !videoRef.current || !audioRef.current) return;

    let isMounted = true;

    const connect = async () => {
      try {
        /* 1. Obtener token de sesión desde la API de Simli */
        const tokenResponse = await generateSimliSessionToken({
          apiKey,
          config: {
            faceId,
            handleSilence: true,
            maxSessionLength: 3600,
            maxIdleTime: 600,
          },
        });

        if (!isMounted) return;

        const token = tokenResponse.session_token;

        /* 2. Crear cliente Simli con transporte LiveKit */
        const client = new SimliClient(
          token,
          videoRef.current,
          audioRef.current,
          null,       // iceServers – null = LiveKit (más estable globalmente)
          undefined,  // logLevel
          'livekit',  // transport
        );

        client.on('start', () => {
          if (isMounted) setStatus('connected');
        });

        client.on('error', (detail) => {
          console.error('[Simli] error:', detail);
          if (isMounted) setStatus('error');
        });

        client.on('startup_error', (msg) => {
          console.error('[Simli] startup_error:', msg);
          if (isMounted) setStatus('error');
        });

        client.on('stop', () => {
          if (isMounted) setStatus('connecting');
        });

        clientRef.current = client;

        /* 3. Iniciar conexión WebRTC */
        await client.start();
      } catch (err) {
        console.error('[Simli] Error al conectar:', err);
        if (isMounted) setStatus('error');
      }
    };

    connect();

    return () => {
      isMounted = false;
      if (clientRef.current) {
        clientRef.current.stop().catch(() => {});
        clientRef.current = null;
      }
    };
  }, [apiKey, faceId]);

  return (
    <div className="simli-avatar-container">
      {/* Video del avatar – Simli lo alimenta vía WebRTC */}
      <video ref={videoRef} autoPlay playsInline className="simli-video" />
      {/* Audio – Simli reproduce aquí sincronizado con los labios */}
      <audio ref={audioRef} autoPlay />

      {/* Overlay de estado cuando el avatar aún no está listo */}
      {status !== 'connected' && (
        <div className="simli-overlay">
          {status === 'connecting' && (
            <div className="simli-status-box">
              <div className="simli-spinner" />
              <span>Iniciando avatar...</span>
            </div>
          )}
          {status === 'error' && (
            <div className="simli-status-box simli-error-box">
              <span>Avatar no disponible</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

SimliAvatar.displayName = 'SimliAvatar';
export default SimliAvatar;
