import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff } from 'lucide-react';
import '../App.css';

export default function Microphone({ onRecorded, onRecordStart }) {
    const [disabled, setDisabled] = useState(true);
    const [isRecording, setIsRecording] = useState(false);
    const mediaRecorder = useRef(null);
    const audioMimeType = 'audio/webm';

    // Solo pide permiso del micrófono al montar para habilitar el botón.
    // El stream real se obtiene fresco en cada grabación.
    useEffect(() => {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then((stream) => {
                stream.getTracks().forEach(t => t.stop()); // liberar inmediatamente
                setDisabled(false);
            })
            .catch(() => setDisabled(true));
    }, []);

    // Escuchar cambios de permiso
    useEffect(() => {
        navigator.permissions.query({ name: 'microphone' })
            .then((status) => {
                status.onchange = () => setDisabled(status.state !== 'granted');
            })
            .catch(() => {});
    }, []);

    const handleRecording = async () => {
        if (disabled) return;

        if (!isRecording) {
            // ── Iniciar grabación ──────────────────────────────────────────
            speechSynthesis.cancel();
            onRecordStart?.();

            try {
                // Stream fresco: se crea DESPUÉS de que Simli/WebRTC ya está activo,
                // así Chrome lo inicializa en el contexto de audio correcto.
                const stream = await navigator.mediaDevices.getUserMedia({
                    audio: {
                        echoCancellation: true,
                        noiseSuppression: true,
                        autoGainControl: true,
                    },
                });

                const recorder = new MediaRecorder(stream, {
                    mimeType: `${audioMimeType};codecs=opus`,
                });
                const chunks = [];

                recorder.ondataavailable = (e) => {
                    if (e.data.size > 0) chunks.push(e.data);
                };

                recorder.onstop = () => {
                    const blob = new Blob(chunks, { type: audioMimeType });
                    stream.getTracks().forEach(t => t.stop()); // liberar micrófono
                    onRecorded(blob);
                };

                mediaRecorder.current = recorder;
                recorder.start(); // sin timeslice: un solo blob limpio al parar

                setIsRecording(true);
            } catch (err) {
                console.error('[Mic] Error al acceder al micrófono:', err);
                setDisabled(true);
            }
        } else {
            // ── Detener grabación ─────────────────────────────────────────
            mediaRecorder.current?.stop();
            setIsRecording(false);
        }
    };

    return (
        <button
            disabled={disabled}
            className={`mic-button ${isRecording ? 'recording' : ''}`}
            onClick={handleRecording}
        >
            {disabled ? <MicOff /> : <Mic />}
        </button>
    );
}
