// Speech to Text Service connection with the backend

const TRANSCRIPTION_TIMEOUT_MS = 20_000;

// Returns a promise to transcribe the given audio blob
export default async function transcribe(audioBlob){
    const apiUrl = import.meta.env.VITE_API_URL;
    const requestBody = new FormData();
    requestBody.append('audio', audioBlob, "recording.webm");

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), TRANSCRIPTION_TIMEOUT_MS);

    console.log(`[STT] Enviando audio: ${audioBlob.size} bytes, tipo: ${audioBlob.type}`);
    try{
        const response = await fetch(`${apiUrl}/transcribe`, {
            method: 'POST',
            body: requestBody,
            signal: controller.signal,
        });
        const data = await response.json();
        console.log(`[STT] Respuesta HTTP ${response.status}:`, data);
        return data;
    }catch(error){
        if (error.name === 'AbortError') {
            console.error('[STT] Transcripción cancelada por timeout (20s)');
        } else {
            console.error('[STT] Error al realizar la transcripción:', error);
        }
        return null;
    } finally {
        clearTimeout(timeoutId);
    }
};