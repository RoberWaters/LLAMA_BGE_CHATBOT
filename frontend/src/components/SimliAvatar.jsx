import { useRef, useEffect, forwardRef, useImperativeHandle } from 'react';
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

    useEffect(() => {
        const myId = ++_clientCounter;
        console.log(`[Simli #${myId}] creando cliente`);
        const client = new SimliClient();
        clientRef.current = client;
        isReadyRef.current = false;

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
            if (clientRef.current === client) isReadyRef.current = false;
        });

        client.start();

        return () => {
            console.log(`[Simli #${myId}] cleanup (close). isCurrent=${clientRef.current === client}`);
            if (clientRef.current === client) isReadyRef.current = false;
            client.close();
        };
    }, []);

    useImperativeHandle(ref, () => ({
        speak: async (pcmBase64) => {
            if (!pcmBase64 || !clientRef.current) return;
            console.log(`[Simli speak] isReadyRef=${isReadyRef.current}, isConnected()=${clientRef.current.isConnected()}`);
            // Poll isReadyRef (set por el evento 'connected' del cliente actual)
            let attempts = 0;
            while (!isReadyRef.current && attempts < 100) {
                await new Promise(r => setTimeout(r, 100));
                attempts++;
            }
            if (!isReadyRef.current) {
                console.warn('[Simli] No listo tras espera, descartando audio');
                return;
            }
            const bytes = base64ToUint8Array(pcmBase64);
            clientRef.current.sendAudioData(bytes);
        },
        stop: () => {
            clientRef.current?.ClearBuffer();
        },
    }));

    return (
        <div className="simli-avatar-wrapper">
            <video
                ref={videoRef}
                autoPlay
                playsInline
                className="simli-video"
            />
            <audio ref={audioRef} autoPlay />
        </div>
    );
});

export default SimliAvatar;
