import { useRef, forwardRef, useImperativeHandle } from 'react';

// Construye un WAV válido a partir de PCM 16-bit mono 16kHz (formato que devuelve Polly)
function pcmBase64ToWavBlob(base64) {
    const pcm = Uint8Array.from(atob(base64), c => c.charCodeAt(0));
    const sampleRate = 16000;
    const numChannels = 1;
    const bitsPerSample = 16;
    const byteRate = sampleRate * numChannels * (bitsPerSample / 8);
    const blockAlign = numChannels * (bitsPerSample / 8);
    const dataSize = pcm.byteLength;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);
    const write = (offset, str) => { for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i)); };
    write(0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    write(8, 'WAVE');
    write(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);           // PCM
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);
    write(36, 'data');
    view.setUint32(40, dataSize, true);
    new Uint8Array(buffer, 44).set(pcm);
    return new Blob([buffer], { type: 'audio/wav' });
}

const AudioPlayer = forwardRef(function AudioPlayer(_, ref) {
    const queueRef = useRef([]);
    const isPlayingRef = useRef(false);
    const isMutedRef = useRef(false);

    const playNext = async () => {
        if (isPlayingRef.current || queueRef.current.length === 0) return;
        isPlayingRef.current = true;
        const blob = queueRef.current.shift();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        audio.muted = isMutedRef.current;
        try {
            await audio.play();
            await new Promise(resolve => { audio.onended = resolve; audio.onerror = resolve; });
        } finally {
            URL.revokeObjectURL(url);
            isPlayingRef.current = false;
            playNext();
        }
    };

    useImperativeHandle(ref, () => ({
        speak: async (pcmBase64) => {
            if (!pcmBase64) return;
            const blob = pcmBase64ToWavBlob(pcmBase64);
            queueRef.current.push(blob);
            playNext();
        },
        stop: () => {
            queueRef.current = [];
        },
        mute: () => {
            isMutedRef.current = true;
        },
        unmute: () => {
            isMutedRef.current = false;
        },
        pause: () => {
            isMutedRef.current = true;
            queueRef.current = [];
        },
        resume: () => {
            isMutedRef.current = false;
        },
    }));

    return (
        <div className="audio-player-wrapper">
            <img
                src="/voae-logo.png"
                alt="VOAE"
                className="audio-player-avatar"
            />
        </div>
    );
});

export default AudioPlayer;
