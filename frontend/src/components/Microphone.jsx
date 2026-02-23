import React, { useState, useEffect, useRef } from 'react';
import {
  Mic,
  MicOff
} from 'lucide-react';
import '../App.css';

export default function Microphone({ onRecorded, onStartRecording }) {
    // TODO: CLEAN CODE METHODS. SEPARATE CONCERNS FOR BETTER READABILITY
    // TODO: Implement comm with LLM for audio transcription
    const [disabled, setDisabled] = useState(true);
    const [isRecording, setIsRecording] = useState(false);
    const audioChunks = useRef([]);
    const mediaRecorder = useRef(null);
    const speechRecognition = useRef(null);
    // Ref para siempre llamar a la versión más reciente de onRecorded sin
    // re-crear el MediaRecorder (evita stale closure en onstop).
    const onRecordedRef = useRef(onRecorded);
    const audioMimeType = 'audio/webm';

    // Mantener onRecordedRef actualizado en cada render
    useEffect(() => {
        onRecordedRef.current = onRecorded;
    }, [onRecorded]);

    // Media Recorder setup
    useEffect(() => {
        // Ask for microphone access on component mount
        navigator.mediaDevices.getUserMedia({
            audio: {
                echoCancellation: true,
                noiseSuppression: true,
            }
        })
        .then((stream) => {
            // Configure and set the MediaRecorder object
            const options = {mimeType: `${audioMimeType};codecs=opus`};
            mediaRecorder.current = new MediaRecorder(stream, options);

            // Handle Recording logic. Add chunks when available
            mediaRecorder.current.ondataavailable = (event) => {
                audioChunks.current = [...audioChunks.current, event.data];
            };

            // Handle Stop logic
            mediaRecorder.current.onstop = () => {
                const blob = new Blob(audioChunks.current, { type: audioMimeType });
                // Clear audio chunks for the next recording
                audioChunks.current = [];
                // Llamar siempre a la versión más reciente del callback
                onRecordedRef.current(blob);
            }

            // Enable the microphone button if access was granted
            setDisabled(false);
            }
        )
        .catch((err) => {
            // Disable the microphone button if access was denied
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
    }, [])

    // Init Speech Recognition service. SR is used to stop recording when user stops speaking
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
            mediaRecorder.current?.stop();
            setIsRecording(false);
        };
        return () => {
            speechRecognition.current?.abort();
        };
    }, []);

    const handleRecording = async () => {
        // TODO: Implement modal to inform user to enable microphone access?
        if (disabled) return;
        // Stop any ongoing speech synthesis when starting a new recording
        speechSynthesis.cancel();

        const toggleRecording = !isRecording;
        if (toggleRecording){
            // Notificar al padre para que detenga/silencie el avatar (srcObject=null)
            onStartRecording?.();
            // Esperar a que el buffer de audio del hardware drene antes de grabar,
            // evitando que los últimos milisegundos del audio de Simli entren al mic.
            await new Promise(r => setTimeout(r, 150));
            // Start recording
            mediaRecorder.current.start(1000);
            // Start recongnition service to stop when user stops speaking
            if (speechRecognition.current)
                speechRecognition.current?.start();
            console.log("Recording started");
        } else{
            // Stop recording
            mediaRecorder.current.stop();
            console.log("Recording stopped");
        }
        setIsRecording(toggleRecording);
    }

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
