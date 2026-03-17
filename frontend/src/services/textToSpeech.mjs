// Text to Speech Service — conecta con el endpoint /synthesize (Amazon Polly)

export default async function synthesize(text) {
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
    try {
        const response = await fetch(`${apiUrl}/synthesize`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text }),
        });
        const data = await response.json();
        return data;
    } catch (error) {
        console.error("Error al sintetizar audio: ", error);
        return null;
    }
}
