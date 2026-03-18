import { useRef, useState, useEffect, forwardRef, useImperativeHandle, useCallback } from 'react';
import { SimliClient, generateSimliSessionToken } from 'simli-client';

function base64ToUint8Array(base64) {
    const binary = atob(base64);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i++) {
        bytes[i] = binary.charCodeAt(i);
    }
    return bytes;
}

// Contador global para identificar instancias de cliente
let _clientCounter = 0;

const SimliAvatar = forwardRef(function SimliAvatar(_, ref) {
    const videoRef = useRef(null);
    const audioRef = useRef(null);
    const clientRef = useRef(null);
    const isReadyRef = useRef(false);
    const isFailedRef = useRef(false);
    // 'loading' | 'ready' | 'failed'
    const [connectionStatus, setConnectionStatus] = useState('loading');
    // Guarda el srcObject mientras el micrófono está activo
    const savedStreamRef = useRef(null);

    // Crea e inicia un nuevo SimliClient (API v3).
    // Acepta un AbortSignal opcional para cancelar si el componente se desmonta
    // antes de que termine la conexión (evita doble conexión con React StrictMode).
    const startNewClient = useCallback(async (signal) => {
        const myId = ++_clientCounter;
        console.log(`[Simli #${myId}] creando cliente`);
        isReadyRef.current = false;
        isFailedRef.current = false;
        setConnectionStatus('loading');

        // 1. Obtener session token desde la API de Simli
        let tokenData;
        try {
            tokenData = await generateSimliSessionToken({
                apiKey: import.meta.env.VITE_SIMLI_API_KEY,
                config: {
                    faceId: import.meta.env.VITE_SIMLI_FACE_ID,
                    handleSilence: true,
                    maxSessionLength: 600,
                    maxIdleTime: 60,
                },
            });
        } catch (e) {
            console.error(`[Simli #${myId}] error obteniendo token:`, e);
            if (!signal?.aborted) {
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
            return;
        }

        // Si el componente se desmontó mientras esperábamos el token, no continuar
        if (signal?.aborted) {
            console.log(`[Simli #${myId}] cancelado (desmontado antes de conectar)`);
            return;
        }

        // 2. Crear cliente con transport livekit (no requiere ICE servers)
        const client = new SimliClient(
            tokenData.session_token,
            videoRef.current,
            audioRef.current,
            null,       // iceServers no requeridos en modo livekit
            undefined,  // logLevel por defecto
            'livekit'
        );
        clientRef.current = client;

        client.on('start', () => {
            const isCurrent = clientRef.current === client;
            console.log(`[Simli #${myId}] 'start', isCurrent=${isCurrent}`);
            if (isCurrent) {
                isReadyRef.current = true;
                setConnectionStatus('ready');
                console.log(`[Simli #${myId}] LISTO para recibir audio`);
                // Forzar play en el video para evitar pantalla verde en WebRTC/Livekit
                videoRef.current?.play().catch(() => {});
                audioRef.current?.play().catch(() => {});
            }
        });

        client.on('error', (e) => {
            console.error(`[Simli #${myId}] error:`, e);
            if (clientRef.current === client) {
                isReadyRef.current = false;
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        });

        client.on('startup_error', (e) => {
            console.error(`[Simli #${myId}] startup_error:`, e);
            if (clientRef.current === client) {
                isReadyRef.current = false;
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        });

        // 3. Conectar (el cliente ya maneja reintentos internamente)
        try {
            await client.start();
        } catch (e) {
            console.error(`[Simli #${myId}] start() falló:`, e);
            if (clientRef.current === client) {
                isReadyRef.current = false;
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        }
    }, []);

    // Auto-inicia al montar. El cleanup detiene el cliente al desmontar.
    // Usa AbortController para cancelar si StrictMode desmonta antes de conectar.
    useEffect(() => {
        const abort = new AbortController();
        startNewClient(abort.signal);

        return () => {
            abort.abort();
            if (clientRef.current) {
                console.log('[Simli] cleanup (stop)');
                isReadyRef.current = false;
                clientRef.current.stop().catch(() => {});
                clientRef.current = null;
            }
            savedStreamRef.current = null;
        };
    }, []);

    useImperativeHandle(ref, () => ({
        speak: async (pcmBase64) => {
            if (!pcmBase64) return;
            console.log(`[Simli speak] isReadyRef=${isReadyRef.current}`);
            // Poll hasta 2s para que Simli conecte; abortar si falla
            let attempts = 0;
            while (!isReadyRef.current && !isFailedRef.current && attempts < 20) {
                await new Promise(r => setTimeout(r, 100));
                attempts++;
            }
            if (!isReadyRef.current) {
                console.warn('[Simli] No listo tras espera (failed=%s), descartando audio', isFailedRef.current);
                return;
            }
            const bytes = base64ToUint8Array(pcmBase64);
            clientRef.current?.sendAudioData(bytes);
        },
        stop: () => {
            clientRef.current?.ClearBuffer();
        },
        mute: () => {
            console.log('[Simli] silenciando — removiendo srcObject del audio');
            clientRef.current?.ClearBuffer();
            if (audioRef.current) {
                if (audioRef.current.srcObject) {
                    savedStreamRef.current = audioRef.current.srcObject;
                }
                audioRef.current.srcObject = null;
                audioRef.current.muted = true;
            }
        },
        unmute: () => {
            console.log('[Simli] restaurando audio');
            if (audioRef.current) {
                if (savedStreamRef.current) {
                    audioRef.current.srcObject = savedStreamRef.current;
                    savedStreamRef.current = null;
                }
                audioRef.current.muted = false;
                audioRef.current.play().catch(() => {});
            }
        },
        pause: () => {
            console.log('[Simli] pausando (desconectando)');
            isReadyRef.current = false;
            clientRef.current?.stop().catch(() => {});
            if (audioRef.current) audioRef.current.muted = true;
        },
        resume: () => {
            console.log('[Simli] resumiendo (reconectando)');
            if (audioRef.current) audioRef.current.muted = false;
            startNewClient();
        },
    }), [startNewClient]);

    // Si falló la conexión, no mostrar nada
    if (connectionStatus === 'failed') {
        return null;
    }

    return (
        <div className="simli-avatar-wrapper">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                className="simli-video"
            />
            <audio ref={audioRef} autoPlay />
            {connectionStatus === 'loading' && (
                <div className="avatar-loading-overlay">
                    <div className="avatar-spinner" />
                    <span className="avatar-loading-text">Cargando avatar...</span>
                </div>
            )}
        </div>
    );
});

export default SimliAvatar;
