import { forwardRef, useImperativeHandle, useRef, useCallback } from 'react';

/**
 * Reproductor de audio invisible para chunks MP3 de Amazon Polly.
 * Expone la misma interfaz que SimliAvatar:
 *   speak(audioBase64)  — encola y reproduce un chunk MP3
 *   stop()              — detiene reproducción y vacía la cola
 *   mute()              — silencia futuras reproducciones
 *   unmute()            — reactiva el audio
 */
const AudioPlayer = forwardRef(function AudioPlayer(_, ref) {
    const queueRef     = useRef([]);
    const isPlayingRef = useRef(false);
    const isMutedRef   = useRef(false);
    const currentRef   = useRef(null); // Audio element activo

    const playNext = useCallback(() => {
        if (queueRef.current.length === 0) {
            isPlayingRef.current = false;
            return;
        }
        isPlayingRef.current = true;
        const b64 = queueRef.current.shift();
        const audio = new Audio(`data:audio/mp3;base64,${b64}`);
        audio.muted = isMutedRef.current;
        currentRef.current = audio;
        audio.onended = playNext;
        audio.onerror = playNext; // si falla el chunk, pasar al siguiente
        audio.play().catch(playNext);
    }, []);

    useImperativeHandle(ref, () => ({
        speak: (audioBase64) => {
            if (!audioBase64) return;
            queueRef.current.push(audioBase64);
            if (!isPlayingRef.current) {
                playNext();
            }
        },
        stop: () => {
            queueRef.current = [];
            isPlayingRef.current = false;
            if (currentRef.current) {
                currentRef.current.pause();
                currentRef.current = null;
            }
        },
        mute: () => {
            isMutedRef.current = true;
            if (currentRef.current) currentRef.current.muted = true;
        },
        unmute: () => {
            isMutedRef.current = false;
            if (currentRef.current) currentRef.current.muted = false;
        },
    }), [playNext]);

    return null; // componente invisible
});

export default AudioPlayer;
