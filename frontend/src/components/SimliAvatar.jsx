import { useRef, useState, useEffect, forwardRef, useImperativeHandle, useCallback } from 'react';
import { SimliClient, generateSimliSessionToken, generateIceServers, LogLevel } from 'simli-client';

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
    const [connectionStatus, setConnectionStatus] = useState('loading');
    const savedStreamRef = useRef(null);

    const startNewClient = useCallback(async () => {
        const myId = ++_clientCounter;
        console.log(`[Simli #${myId}] creando cliente v3`);
        isReadyRef.current = false;
        isFailedRef.current = false;
        setConnectionStatus('loading');

        const apiKey = import.meta.env.VITE_SIMLI_API_KEY;
        const faceId = import.meta.env.VITE_SIMLI_FACE_ID;

        let client;
        try {
            // 1. Session token
            const tokenResp = await generateSimliSessionToken({
                apiKey,
                config: {
                    faceId,
                    handleSilence: true,
                    maxSessionLength: 600,
                    maxIdleTime: 300,
                },
            });

            // 2. ICE servers (p2p transport los requiere; livekit fallback los ignora)
            const iceServers = await generateIceServers(apiKey);

            // 3. Construir cliente. Default transport "p2p" con fallback automático a "livekit".
            client = new SimliClient(
                tokenResp.session_token,
                videoRef.current,
                audioRef.current,
                iceServers,
                LogLevel.INFO,
            );
            clientRef.current = client;

            client.on('start', () => {
                if (clientRef.current !== client) return;
                console.log(`[Simli #${myId}] start — conectado`);
                isReadyRef.current = true;
                setConnectionStatus('ready');
            });

            client.on('error', (msg) => {
                console.error(`[Simli #${myId}] error:`, msg);
                if (clientRef.current === client) {
                    isReadyRef.current = false;
                    isFailedRef.current = true;
                    setConnectionStatus('failed');
                }
            });

            client.on('startup_error', (msg) => {
                console.error(`[Simli #${myId}] startup_error:`, msg);
                if (clientRef.current === client) {
                    isReadyRef.current = false;
                    isFailedRef.current = true;
                    setConnectionStatus('failed');
                }
            });

            // 4. Iniciar conexión (async, resuelve al conectar)
            await client.start();
        } catch (err) {
            console.error(`[Simli #${myId}] falló init:`, err);
            if (clientRef.current === client || !clientRef.current) {
                isFailedRef.current = true;
                setConnectionStatus('failed');
            }
        }

        return client;
    }, []);

    useEffect(() => {
        startNewClient();

        return () => {
            const c = clientRef.current;
            clientRef.current = null;
            isReadyRef.current = false;
            if (c) {
                console.log('[Simli] cleanup (stop)');
                // stop() es async en v3 pero en cleanup no esperamos.
                Promise.resolve(c.stop()).catch(() => {});
            }
            savedStreamRef.current = null;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    useImperativeHandle(ref, () => ({
        speak: async (pcmBase64) => {
            if (!pcmBase64) return;
            // Poll hasta 2s para que conecte
            let attempts = 0;
            while (!isReadyRef.current && !isFailedRef.current && attempts < 20) {
                await new Promise(r => setTimeout(r, 100));
                attempts++;
            }
            if (!isReadyRef.current) {
                console.warn('[Simli] no listo (failed=%s), descartando audio', isFailedRef.current);
                return;
            }
            const bytes = base64ToUint8Array(pcmBase64);
            clientRef.current?.sendAudioData(bytes);
        },
        stop: () => {
            // ClearBuffer limpia el buffer pendiente sin cerrar conexión
            clientRef.current?.ClearBuffer();
        },
        mute: () => {
            console.log('[Simli] mute — removiendo srcObject');
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
            console.log('[Simli] unmute — restaurando audio');
            if (audioRef.current) {
                if (savedStreamRef.current) {
                    audioRef.current.srcObject = savedStreamRef.current;
                    savedStreamRef.current = null;
                }
                audioRef.current.muted = false;
                audioRef.current.play().catch(() => {});
            }
        },
        pause: async () => {
            console.log('[Simli] pause');
            isReadyRef.current = false;
            const c = clientRef.current;
            clientRef.current = null;
            if (c) {
                try { await c.stop(); } catch { /* ignore */ }
            }
            if (audioRef.current) audioRef.current.muted = true;
        },
        resume: () => {
            console.log('[Simli] resume');
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
