import { useRef, useState, useEffect, forwardRef, useImperativeHandle, useCallback } from 'react';
import { SimliClient } from 'simli-client';

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
    // Ref para saber si ya se activó (sin depender de closures sobre estado)
    const isActivatedRef = useRef(false);
    const [isActivated, setIsActivated] = useState(false);
    // Guarda el srcObject mientras el micrófono está activo
    const savedStreamRef = useRef(null);

    // Crea e inicia un nuevo SimliClient dentro de un gesto de usuario.
    const startNewClient = useCallback(() => {
        const myId = ++_clientCounter;
        console.log(`[Simli #${myId}] creando cliente`);
        const client = new SimliClient();
        clientRef.current = client;
        isReadyRef.current = false;
        isFailedRef.current = false;

        client.Initialize({
            apiKey: import.meta.env.VITE_SIMLI_API_KEY,
            faceID: import.meta.env.VITE_SIMLI_FACE_ID,
            handleSilence: true,
            videoRef: videoRef.current,
            audioRef: audioRef.current,
        });

        client.on('connected', () => {
            const connected = client.isConnected();
            const isCurrent = clientRef.current === client;
            console.log(`[Simli #${myId}] 'connected', isConnected()=${connected}, isCurrent=${isCurrent}`);
            if (connected && isCurrent) {
                isReadyRef.current = true;
                console.log(`[Simli #${myId}] LISTO para recibir audio`);
            }
        });

        client.on('failed', (e) => {
            console.error(`[Simli #${myId}] fallo:`, e);
            if (clientRef.current === client) {
                isReadyRef.current = false;
                isFailedRef.current = true;
            }
        });

        client.start();
        return client;
    }, []);

    // Activa Simli — debe llamarse dentro o justo después de un gesto de usuario
    // para que el navegador permita AudioContext y audio autoplay.
    const activate = useCallback(() => {
        if (isActivatedRef.current) return;
        isActivatedRef.current = true;
        setIsActivated(true);
        console.log('[Simli] activando por gesto de usuario');
        startNewClient();
    }, [startNewClient]);

    // Solo limpieza al desmontar — no auto-inicia para cumplir autoplay policy.
    useEffect(() => {
        return () => {
            if (clientRef.current) {
                console.log('[Simli] cleanup (close)');
                isReadyRef.current = false;
                clientRef.current.close();
                clientRef.current = null;
            }
            savedStreamRef.current = null;
        };
    }, []);

    useImperativeHandle(ref, () => ({
        speak: async (pcmBase64) => {
            if (!pcmBase64) return;
            // Auto-activar si el usuario envió un mensaje (gesto de teclado/clic)
            activate();
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
                // Guardar el stream WebRTC antes de desconectarlo.
                // muted=true solo suprime el volumen pero el stream WebRTC sigue
                // activo y puede filtrarse al micrófono. srcObject=null lo corta
                // completamente del pipeline de audio del OS.
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
                // Restaurar el stream WebRTC que fue desconectado al mutear
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
            clientRef.current?.close();
            if (audioRef.current) audioRef.current.muted = true;
        },
        // Reconecta Simli tras un pause().
        resume: () => {
            console.log('[Simli] resumiendo (reconectando)');
            if (audioRef.current) audioRef.current.muted = false;
            startNewClient();
        },
    }), [activate, startNewClient]);

    return (
        <div className="simli-avatar-wrapper">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                className="simli-video"
            />
            <audio ref={audioRef} autoPlay />
            {!isActivated && (
                <div
                    className="avatar-activate-overlay"
                    onClick={activate}
                    title="Clic para activar el avatar"
                >
                    <div className="avatar-activate-btn">▶</div>
                </div>
            )}
        </div>
    );
});

export default SimliAvatar;
