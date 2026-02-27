import { useRef, useState, useEffect, forwardRef, useImperativeHandle, useCallback } from 'react';
import { SimliClient, generateSimliSessionToken, generateIceServers } from 'simli-client';

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

    // Crea e inicia un nuevo SimliClient con la API v3.
    const startNewClient = useCallback(async () => {
        const myId = ++_clientCounter;
        console.log(`[Simli #${myId}] creando cliente`);
        isReadyRef.current = false;
        isFailedRef.current = false;
        setConnectionStatus('loading');

        const apiKey = import.meta.env.VITE_SIMLI_API_KEY;
        const faceId = import.meta.env.VITE_SIMLI_FACE_ID;

        try {
            // Obtener session token e ICE servers en paralelo
            const [sessionData, iceServers] = await Promise.all([
                generateSimliSessionToken({
                    apiKey,
                    config: {
                        faceId,
                        handleSilence: true,
                        maxSessionLength: 3600,
                        maxIdleTime: 300,
                        model: 'fasttalk',
                    },
                }),
                generateIceServers(apiKey),
            ]);

            const client = new SimliClient(
                sessionData.session_token,
                videoRef.current,
                audioRef.current,
                iceServers,
            );
            clientRef.current = client;

            client.on('connected', () => {
                const isCurrent = clientRef.current === client;
                console.log(`[Simli #${myId}] 'connected', isCurrent=${isCurrent}`);
                if (isCurrent) {
                    isReadyRef.current = true;
                    setConnectionStatus('ready');
                    console.log(`[Simli #${myId}] LISTO para recibir audio`);
                }
            });

            client.on('failed', (e) => {
                console.error(`[Simli #${myId}] fallo:`, e);
                if (clientRef.current === client) {
                    isReadyRef.current = false;
                    isFailedRef.current = true;
                    setConnectionStatus('failed');
                }
            });

            // start() es async e internamente maneja reintentos
            client.start().catch((e) => {
                console.error(`[Simli #${myId}] start() falló:`, e);
                if (clientRef.current === client) {
                    isReadyRef.current = false;
                    isFailedRef.current = true;
                    setConnectionStatus('failed');
                }
            });
        } catch (e) {
            console.error(`[Simli #${myId}] error al obtener token/ICE:`, e);
            isFailedRef.current = true;
            setConnectionStatus('failed');
        }
    }, []);

    // Auto-inicia al montar. El cleanup detiene el cliente al desmontar.
    useEffect(() => {
        startNewClient();
        return () => {
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
        // Desconecta Simli completamente (solo si es necesario liberar el pipeline).
        pause: () => {
            console.log('[Simli] pausando (desconectando)');
            isReadyRef.current = false;
            clientRef.current?.stop().catch(() => {});
            if (audioRef.current) audioRef.current.muted = true;
        },
        // Reconecta Simli tras un pause().
        resume: () => {
            console.log('[Simli] resumiendo (reconectando)');
            if (audioRef.current) audioRef.current.muted = false;
            startNewClient();
        },
    }), [startNewClient]);

    return (
        <div className="simli-avatar-wrapper">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                className="simli-video"
                onPlay={() => {
                    setConnectionStatus('ready');
                    isReadyRef.current = true;
                }}
            />
            <audio ref={audioRef} autoPlay />
            {connectionStatus !== 'ready' && (
                <div className="avatar-loading-overlay">
                    {connectionStatus === 'failed' ? (
                        <span className="avatar-loading-text">Error de conexión</span>
                    ) : (
                        <>
                            <div className="avatar-spinner" />
                            <span className="avatar-loading-text">Cargando avatar...</span>
                        </>
                    )}
                </div>
            )}
        </div>
    );
});

export default SimliAvatar;
