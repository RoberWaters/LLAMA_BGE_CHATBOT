import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff } from 'lucide-react';
import '../App.css';
import transcribe from '../services/speechToText.mjs';

export default function Microphone({ onStartRecording, onText, onTranscribingChange }) {
    const [disabled, setDisabled] = useState(true);
    const [isRecording, setIsRecording] = useState(false);
    const [isTranscribing, setIsTranscribing] = useState(false);
    const audioChunks = useRef([]);
    const mediaRecorderRef = useRef(null);
    const streamRef = useRef(null);
    const speechRecognitionRef = useRef(null);
    const audioMimeType = 'audio/webm';

    // Solo verificar permiso al montar — el stream se abre fresh en cada grabación.
    useEffect(() => {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                stream.getTracks().forEach(t => t.stop());
                setDisabled(false);
            })
            .catch(() => setDisabled(true));
    }, []);

    useEffect(() => {
        navigator.permissions.query({ name: 'microphone' })
            .then(status => {
                status.onchange = () => setDisabled(status.state !== 'granted');
            });
    }, []);

    const stopRecording = () => {
        try { speechRecognitionRef.current?.stop(); } catch (_) {}
        if (mediaRecorderRef.current?.state === 'recording') {
            mediaRecorderRef.current.stop();
        }
        setIsRecording(false);
    };

    const handleRecording = async () => {
        if (disabled || isTranscribing) return;

        if (isRecording) {
            stopRecording();
            return;
        }

        // 1. Cortar audio de Simli (srcObject=null en SimliAvatar)
        onStartRecording?.();

        // 2. Esperar a que el buffer de audio del hardware drene
        await new Promise(r => setTimeout(r, 150));

        // 3. Abrir stream FRESCO después de que Simli ya está detenido.
        //    Sin echoCancellation — Simli no suena, no hay eco que cancelar.
        //    Evita que el WebRTC activo de Simli interfiera con el AEC del micrófono.
        let stream;
        try {
            stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                }
            });
        } catch (err) {
            console.error('[STT] Error al acceder al micrófono:', err);
            return;
        }
        streamRef.current = stream;
        audioChunks.current = [];

        // 4. MediaRecorder sobre el stream limpio
        const mr = new MediaRecorder(stream, { mimeType: `${audioMimeType};codecs=opus` });
        mediaRecorderRef.current = mr;

        mr.ondataavailable = (e) => {
            if (e.data.size > 0) audioChunks.current.push(e.data);
        };

        mr.onstop = async () => {
            stream.getTracks().forEach(t => t.stop());
            streamRef.current = null;

            const blob = new Blob(audioChunks.current, { type: audioMimeType });
            audioChunks.current = [];

            setIsTranscribing(true);
            onTranscribingChange?.(true);
            try {
                const result = await transcribe(blob);
                onText?.(result?.text?.trim() || null);
            } catch (err) {
                console.error('[STT] Error en transcripción:', err);
                onText?.(null);
            } finally {
                setIsTranscribing(false);
                onTranscribingChange?.(false);
            }
        };

        // 5. SpeechRecognition para auto-detener cuando el usuario deja de hablar
        const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (SpeechRecognition) {
            const sr = new SpeechRecognition();
            sr.lang = 'es-ES';
            sr.onspeechend = () => {
                sr.stop();
                if (mr.state === 'recording') {
                    mr.stop();
                    setIsRecording(false);
                }
            };
            speechRecognitionRef.current = sr;
            try { sr.start(); } catch (_) {}
        }

        // 6. Iniciar grabación
        mr.start(1000);
        setIsRecording(true);
        console.log('[STT] Grabación iniciada (stream fresco, sin AEC)');
    };

    return (
        <button
            disabled={disabled || isTranscribing}
            className={`mic-button ${isRecording ? 'recording' : ''}`}
            onClick={handleRecording}
        >
            {disabled ? <MicOff /> : <Mic />}
        </button>
    );
}
