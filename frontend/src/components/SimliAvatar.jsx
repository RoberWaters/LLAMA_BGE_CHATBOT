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

let _clientCounter = 0;

const SimliAvatar = forwardRef(function SimliAvatar(_, ref) {
    const videoRef = useRef(null);
    const audioRef = useRef(null);
    const clientRef = useRef(null);
    const isReadyRef = useRef(false);
    const isFailedRef = useRef(false);
    const connectingRef = useRef(false);
    // 'idle' | 'loading' | 'ready' | 'failed'
    const [connectionStatus, setConnectionStatus] = useState('idle');
    const savedStreamRef = useRef(null);
    const cancelledRef = useRef(false);

    // Crea e inicia un nuevo SimliClient (API v3).
    const startNewClient = useCallback(async (cancelled) => {
        const myId = ++_clientCounter;
        console.log(`[Simli #${myId}] creando cliente`);
        isReadyRef.current = false;
        isFailedRef.current = false;
        connectingRef.current = true;
        setConnectionStatus('loading');

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
            connectingRef.current = false;
            if (!cancelled.current) {
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
            return;
        }

        if (cancelled.current) {
            console.log(`[Simli #${myId}] abortado antes de crear cliente`);
            connectingRef.current = false;
            return;
        }

        const client = new SimliClient(
            tokenData.session_token,
            videoRef.current,
            audioRef.current,
            null,
            undefined,
            'livekit'
        );
        clientRef.current = client;

        client.on('start', () => {
            const isCurrent = clientRef.current === client;
            console.log(`[Simli #${myId}] 'start', isCurrent=${isCurrent}`);
            if (isCurrent && !cancelled.current) {
                isReadyRef.current = true;
                connectingRef.current = false;
                setConnectionStatus('ready');
                console.log(`[Simli #${myId}] LISTO para recibir audio`);
                videoRef.current?.play().catch(() => {});
                audioRef.current?.play().catch(() => {});
            }
        });

        // Simli cierra la sesión tras maxIdleTime (60s sin audio) o maxSessionLength.
        // No auto-reconectamos: la próxima pregunta llamará ensureConnected() de nuevo.
        client.on('disconnected', () => {
            console.log(`[Simli #${myId}] desconectado (sesión cerrada por Simli)`);
            if (clientRef.current === client) {
                clientRef.current = null;
                isReadyRef.current = false;
                connectingRef.current = false;
                if (!cancelled.current) setConnectionStatus('idle');
            }
        });

        client.on('error', (e) => {
            console.error(`[Simli #${myId}] error:`, e);
            if (clientRef.current === client && !cancelled.current) {
                isReadyRef.current = false;
                connectingRef.current = false;
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        });

        client.on('startup_error', (e) => {
            console.error(`[Simli #${myId}] startup_error:`, e);
            if (clientRef.current === client && !cancelled.current) {
                isReadyRef.current = false;
                connectingRef.current = false;
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        });

        try {
            await client.start();
        } catch (e) {
            console.error(`[Simli #${myId}] start() falló:`, e);
            if (clientRef.current === client && !cancelled.current) {
                isReadyRef.current = false;
                connectingRef.current = false;
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        }
    }, []);

    // Cleanup al desmontar. No auto-inicia: la conexión ocurre on-demand al enviar pregunta.
    useEffect(() => {
        cancelledRef.current = false;
        return () => {
            cancelledRef.current = true;
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
        // Conecta si no hay sesión activa. Idempotente: no-op si ya conectado o conectando.
        ensureConnected: () => {
            if (clientRef.current && isReadyRef.current) return;
            if (connectingRef.current) return;
            cancelledRef.current = false;
            startNewClient(cancelledRef);
        },
        speak: async (pcmBase64) => {
            if (!pcmBase64) return;
            console.log(`[Simli speak] isReadyRef=${isReadyRef.current}`);
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
    }), [startNewClient]);

    return (
        <div className="simli-avatar-wrapper">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                className="simli-video"
            />
            <audio ref={audioRef} autoPlay />
            {connectionStatus !== 'ready' && (
                <div className="avatar-loading-overlay">
                    {connectionStatus === 'failed' ? (
                        <span className="avatar-loading-text">Error de conexión</span>
                    ) : connectionStatus === 'loading' ? (
                        <>
                            <div className="avatar-spinner" />
                            <span className="avatar-loading-text">Cargando avatar...</span>
                        </>
                    ) : (
                        <span className="avatar-loading-text">Avatar en espera</span>
                    )}
                </div>
            )}
        </div>
    );
});

export default SimliAvatar;
