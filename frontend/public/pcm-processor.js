/**
 * AudioWorklet processor con VAD (Voice Activity Detection) integrado.
 * Detecta fin de habla usando RMS de las propias muestras PCM.
 *
 * IMPORTANTE: el RMS se calcula sobre el buffer original de la entrada ANTES
 * de crear la copia para transferir. Si se calculara sobre 'samples' después
 * del postMessage, el buffer ya estaría transferido (longitud 0) y el VAD
 * nunca funcionaría.
 */
class PCMProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this._hasSpeech = false;
        this._silenceFrames = 0;
        this._onsetFrames = 0;
        // RMS mínimo para considerar que hay habla (~-40dB)
        this._SPEECH_THRESHOLD = 0.01;
        // Frames consecutivos por encima del umbral para confirmar inicio de habla
        // 128 samples/frame @ 16kHz → 1 frame ≈ 8ms → 8 frames ≈ 64ms
        this._SPEECH_ONSET_FRAMES = 8;
        // Frames de silencio para confirmar fin de habla (120 frames ≈ 1s)
        this._SILENCE_FRAMES = 120;
    }

    process(inputs) {
        const input = inputs[0];
        if (!input.length || !input[0].length) return true;

        // 'channel' es la vista Float32Array del AudioWorklet — válida durante todo process().
        const channel = input[0];

        // 1. Calcular RMS sobre el buffer ORIGINAL (antes de transferir nada)
        let sumSq = 0;
        for (let i = 0; i < channel.length; i++) sumSq += channel[i] * channel[i];
        const rms = Math.sqrt(sumSq / channel.length);

        // 2. Crear copia para transferir al hilo principal (zero-copy)
        const samples = channel.slice();
        this.port.postMessage({ type: 'audio', samples }, [samples.buffer]);
        // Aquí 'samples' queda transferida (longitud 0), pero 'rms' ya está calculado.

        // 3. VAD con onset detection
        if (rms > this._SPEECH_THRESHOLD) {
            // Acumular frames consecutivos por encima del umbral
            this._onsetFrames++;
            this._silenceFrames = 0;
            if (this._onsetFrames >= this._SPEECH_ONSET_FRAMES) {
                this._hasSpeech = true;
            }
        } else {
            // Señal por debajo del umbral → resetear onset
            this._onsetFrames = 0;
            if (this._hasSpeech) {
                this._silenceFrames++;
                if (this._silenceFrames >= this._SILENCE_FRAMES) {
                    // Silencio suficiente después de habla confirmada → señal de fin
                    this.port.postMessage({ type: 'speechEnd' });
                    this._hasSpeech = false;
                    this._silenceFrames = 0;
                }
            }
        }

        return true;
    }
}

registerProcessor('pcm-processor', PCMProcessor);
