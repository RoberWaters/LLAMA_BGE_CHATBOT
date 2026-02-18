// Text to Speech Service connection with the backend (Amazon Polly)

const API_BASE_URL = 'http://localhost:8000';

/**
 * Preprocesa texto para TTS: elimina markdown y convierte acronimos a minusculas
 * @param {string} text - Texto con posible markdown
 * @returns {string} Texto limpio para sintesis de voz
 */
export function preprocessTextForTTS(text) {
    return text
        .replace(/\*\*(.*?)\*\*/g, '$1')
        .replace(/\*(.*?)\*/g, '$1')
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/^[-*]\s+/gm, '')
        .replace(/\b(VOAE|UNAH|UNAH-VS|VRA|DIPP|PAC|PASEE|PROCAD|PROSENE|CIVU|PAIE|PAI-E|PAPE|PHUMA|IAG)\b/g,
            match => match.toLowerCase());
}

/**
 * Sintetiza texto a voz usando Amazon Polly via el backend
 * @param {string} text - Texto a sintetizar
 * @returns {Promise<Object|null>} Datos de audio y visemas, o null si hay error
 */
export async function synthesize(text) {
    try {
        const response = await fetch(`${API_BASE_URL}/synthesize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });

        if (!response.ok) {
            console.error("Error en sintesis de voz:", response.status);
            return null;
        }

        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error al sintetizar voz:", error);
        return null;
    }
}
