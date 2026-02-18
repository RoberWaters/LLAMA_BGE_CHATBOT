import React, { useRef, useEffect, useState, forwardRef, useImperativeHandle } from 'react';
import { TalkingHead } from '@met4citizen/talkinghead';

const AVATAR_URL = '/avatar/avatar.glb';

const TalkingHeadAvatar = forwardRef(function TalkingHeadAvatar(props, ref) {
    const containerRef = useRef(null);
    const headRef = useRef(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useImperativeHandle(ref, () => ({
        speak: async (data) => {
            const head = headRef.current;
            if (!head || !data) return;
            try {
                const audioCtx = head.audioCtx;

                // --- DIAGNÓSTICO ---
                console.log('[AVATAR-DIAG] isRunning:', head.isRunning);
                console.log('[AVATAR-DIAG] isSpeaking:', head.isSpeaking);
                console.log('[AVATAR-DIAG] isAudioPlaying:', head.isAudioPlaying);
                console.log('[AVATAR-DIAG] audioCtx.state:', audioCtx.state);
                console.log('[AVATAR-DIAG] animQueue.length (pre):', head.animQueue.length);
                console.log('[AVATAR-DIAG] data.words.length:', data.words?.length);
                console.log('[AVATAR-DIAG] data.visemes.length:', data.visemes?.length);
                console.log('[AVATAR-DIAG] data.visemes[0]:', data.visemes?.[0]);
                console.log('[AVATAR-DIAG] data.vtimes[0]:', data.vtimes?.[0]);
                console.log('[AVATAR-DIAG] data.vdurations[0]:', data.vdurations?.[0]);
                console.log('[AVATAR-DIAG] mtAvatar viseme keys:', Object.keys(head.mtAvatar).filter(k => k.startsWith('viseme_')));

                // Garantizar que el AudioContext esté running.
                // Usar timeout para evitar cuelgue si Chrome no permite el resume.
                if (audioCtx.state !== 'running') {
                    await Promise.race([
                        audioCtx.resume(),
                        new Promise(resolve => setTimeout(resolve, 500))
                    ]);
                }
                console.log('[AVATAR-DIAG] audioCtx.state (post-resume):', audioCtx.state);

                // Decodificar audio base64 a ArrayBuffer
                const response = await fetch(`data:audio/mp3;base64,${data.audio}`);
                const arrayBuffer = await response.arrayBuffer();
                const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
                console.log('[AVATAR-DIAG] audioBuffer.duration:', audioBuffer.duration);

                // Construir payload: visemas de Polly si los retornó, si no TalkingHead
                // usa el módulo de lipsync por palabras (inglés, funciona bien con español)
                const speakPayload = {
                    audio: audioBuffer,
                    words: data.words,
                    wtimes: data.wtimes,
                    wdurations: data.wdurations,
                };

                // Array vacío de visemas es truthy en JS y bloquea el lipsync por palabras,
                // por eso solo se incluye si Polly realmente devolvió visemas
                if (data.visemes && data.visemes.length > 0) {
                    speakPayload.visemes = data.visemes;
                    speakPayload.vtimes = data.vtimes;
                    speakPayload.vdurations = data.vdurations;
                }

                console.log('[AVATAR-DIAG] animClock before speakAudio:', head.animClock);
                head.speakAudio(speakPayload, { lipsyncLang: "en" });
                console.log('[AVATAR-DIAG] animQueue.length (post-speakAudio):', head.animQueue.length);
                console.log('[AVATAR-DIAG] speechQueue.length (post-speakAudio):', head.speechQueue.length);
                console.log('[AVATAR-DIAG] isSpeaking (post):', head.isSpeaking);
                console.log('[AVATAR-DIAG] isAudioPlaying (post):', head.isAudioPlaying);

                // Monitorear valores de visema durante 3s
                let count = 0;
                const monitor = setInterval(() => {
                    count++;
                    const pp = head.mtAvatar?.['viseme_PP']?.value;
                    const aa = head.mtAvatar?.['viseme_aa']?.value;
                    const aq = head.animQueue?.length;
                    console.log(`[AVATAR-DIAG] t+${count*200}ms | animQueue:${aq} | viseme_PP:${pp?.toFixed(3)} | viseme_aa:${aa?.toFixed(3)} | isSpeaking:${head.isSpeaking}`);
                    if (count >= 15) clearInterval(monitor);
                }, 200);

            } catch (err) {
                console.error("Error al reproducir audio con avatar:", err);
            }
        },
        stop: () => {
            if (headRef.current) {
                try {
                    headRef.current.stopSpeaking();
                } catch (err) {
                    console.error("Error al detener habla del avatar:", err);
                }
            }
        },
        // Llamar sincrónicamente desde el gesto del usuario para desbloquear el AudioContext
        initAudio: () => {
            if (!headRef.current) return;
            const audioCtx = headRef.current.audioCtx;
            if (audioCtx && audioCtx.state !== 'running') {
                audioCtx.resume().catch(() => {});
            }
        },
        isSpeaking: () => {
            if (!headRef.current) return false;
            return headRef.current.isSpeaking || false;
        }
    }));

    useEffect(() => {
        if (!containerRef.current) return;

        let mounted = true;

        const initAvatar = async () => {
            try {
                const head = new TalkingHead(containerRef.current, {
                    ttsEndpoint: null,
                    cameraView: 'upper',
                    lipsyncModules: ["en"]
                });

                await head.showAvatar({
                    url: AVATAR_URL,
                    body: 'F',
                    avatarMood: 'neutral',
                    lipsyncLang: 'en'
                });

                if (mounted) {
                    headRef.current = head;
                    setLoading(false);
                }
            } catch (err) {
                console.error("Error al inicializar avatar:", err);
                if (mounted) {
                    setError("No se pudo cargar el avatar 3D");
                    setLoading(false);
                }
            }
        };

        initAvatar();

        return () => {
            mounted = false;
        };
    }, []);

    if (error) {
        return (
            <div className="avatar-container">
                <div className="avatar-error">
                    <p>{error}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="avatar-container">
            {loading && (
                <div className="avatar-loading">
                    <div className="typing-indicator">
                        <span></span>
                        <span></span>
                        <span></span>
                    </div>
                    <p>Cargando avatar...</p>
                </div>
            )}
            <div
                ref={containerRef}
                style={{
                    width: '100%',
                    height: '100%',
                    display: loading ? 'none' : 'block'
                }}
            />
        </div>
    );
});

export default TalkingHeadAvatar;
