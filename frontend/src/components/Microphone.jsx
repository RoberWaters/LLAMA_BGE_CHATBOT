import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff
} from 'lucide-react';
import '../App.css';

const TARGET_SAMPLE_RATE = 16000;

function downsample(buffer, fromRate, toRate) {
    if (fromRate === toRate) return buffer;
    const ratio = fromRate / toRate;
    const newLength = Math.round(buffer.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {
        const pos = i * ratio;
        const idx = Math.floor(pos);
        const frac = pos - idx;
        const next = idx + 1 < buffer.length ? buffer[idx + 1] : buffer[idx];
        result[i] = buffer[idx] * (1 - frac) + next * frac;
    }
    return result;
}

function writeStr(view, offset, str) {
    for (let i = 0; i < str.length; i++) {
        view.setUint8(offset + i, str.charCodeAt(i));
    }
}

function encodeWav(float32Samples, sampleRate) {
    const samples = downsample(float32Samples, sampleRate, TARGET_SAMPLE_RATE);

    const int16 = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        int16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    const dataSize = int16.length * 2;
    const buffer = new ArrayBuffer(44 + dataSize);
    const view = new DataView(buffer);

    writeStr(view, 0, 'RIFF');
    view.setUint32(4, 36 + dataSize, true);
    writeStr(view, 8, 'WAVE');
    writeStr(view, 12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);   // PCM
    view.setUint16(22, 1, true);   // mono
    view.setUint32(24, TARGET_SAMPLE_RATE, true);
    view.setUint32(28, TARGET_SAMPLE_RATE * 2, true);
    view.setUint16(32, 2, true);   // block align
    view.setUint16(34, 16, true);  // bits per sample
    writeStr(view, 36, 'data');
    view.setUint32(40, dataSize, true);

    const pcmView = new Int16Array(buffer, 44);
    pcmView.set(int16);

    return new Blob([buffer], { type: 'audio/wav' });
}

export default function Microphone({ onRecorded, onStartRecording }) {
    const [disabled, setDisabled] = useState(true);
    const [isRecording, setIsRecording] = useState(false);
    const streamRef = useRef(null);
    const audioCtxRef = useRef(null);
    const processorRef = useRef(null);
    const pcmChunksRef = useRef([]);
    const sampleRateRef = useRef(null);
    const speechRecognition = useRef(null);
    const onRecordedRef = useRef(onRecorded);

    useEffect(() => {
        onRecordedRef.current = onRecorded;
    }, [onRecorded]);

    // Get microphone access on mount
    useEffect(() => {
        navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
            }
        })
        .then((stream) => {
            streamRef.current = stream;
            setDisabled(false);
        })
        .catch((err) => {
            console.error("Microphone access denied:", err);
            setDisabled(true);
        });
    }, []);

    // Listen for microphone permission changes
    useEffect(() => {
        let permissionStatus = null;
        navigator.permissions.query({ name: 'microphone' })
            .then((status) => {
                permissionStatus = status;
                permissionStatus.onchange = () => {
                    setDisabled(permissionStatus.state !== 'granted');
                };
            });
        return () => {
            if (permissionStatus) permissionStatus.onchange = null;
        };
    }, []);

    // Stop recording: disconnect audio nodes, build WAV, notify parent.
    // Only reads from refs + stable setters, so safe to call from any closure.
    function doStopRecording() {
        if (processorRef.current) {
            processorRef.current.disconnect();
            processorRef.current = null;
        }

        const rate = sampleRateRef.current || 48000;
        const chunks = pcmChunksRef.current;
        pcmChunksRef.current = [];
        sampleRateRef.current = null;

        if (audioCtxRef.current) {
            audioCtxRef.current.close();
            audioCtxRef.current = null;
        }

        if (chunks.length > 0) {
            const totalLength = chunks.reduce((sum, c) => sum + c.length, 0);
            const merged = new Float32Array(totalLength);
            let offset = 0;
            for (const chunk of chunks) {
                merged.set(chunk, offset);
                offset += chunk.length;
            }
            const wavBlob = encodeWav(merged, rate);
            onRecordedRef.current(wavBlob);
        }

        setIsRecording(false);
    }

    // Init Speech Recognition (used to auto-stop on silence)
    useEffect(() => {
        const SpeechRecognition = (window.SpeechRecognition || window.webkitSpeechRecognition);
        if (typeof SpeechRecognition === "undefined") {
            console.error("Speech Recognition API not supported in this browser.");
            return;
        }
        speechRecognition.current = new SpeechRecognition();
        speechRecognition.current.lang = "es-ES";
        speechRecognition.current.onspeechend = () => {
            speechRecognition.current.stop();
            doStopRecording();
        };
        return () => {
            speechRecognition.current?.abort();
        };
    }, []);

    const handleRecording = async () => {
        if (disabled) return;
        speechSynthesis.cancel();

        if (!isRecording) {
            // Notify parent to stop/mute avatar before recording
            onStartRecording?.();
            await new Promise(r => setTimeout(r, 150));

            // Start PCM capture via AudioContext + ScriptProcessor
            const audioCtx = new AudioContext();
            audioCtxRef.current = audioCtx;
            sampleRateRef.current = audioCtx.sampleRate;

            const source = audioCtx.createMediaStreamSource(streamRef.current);
            const processor = audioCtx.createScriptProcessor(4096, 1, 1);
            processorRef.current = processor;
            pcmChunksRef.current = [];

            processor.onaudioprocess = (e) => {
                pcmChunksRef.current.push(new Float32Array(e.inputBuffer.getChannelData(0)));
            };

            source.connect(processor);
            processor.connect(audioCtx.destination);

            if (speechRecognition.current) speechRecognition.current.start();
            setIsRecording(true);
            console.log("Recording started (PCM)");
        } else {
            speechRecognition.current?.stop();
            doStopRecording();
            console.log("Recording stopped");
        }
    };

    return (
        <button
            disabled={disabled}
            className={`mic-button ${isRecording ? 'recording' : ''}`}
            onClick={() => {
                handleRecording();
            }}
        >
            {disabled ? <MicOff /> : <Mic />}
        </button>
    );
}
