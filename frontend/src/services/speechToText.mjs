// Speech to Text Service connection with the backend

// Returns a promise to transcribe the given audio blob
export default async function transcribe(audioBlob){
    const apiUrl = import.meta.env.VITE_API_URL;
    if (!apiUrl) {
        console.error("VITE_API_URL no está configurada en el archivo .env del frontend");
        return null;
    }
    const requestBody = new FormData();
    requestBody.append('audio', audioBlob, "recording.webm");
    try{
        const response = await fetch(`${apiUrl}/transcribe`, {
            method: 'POST',
            body: requestBody,
        });
        if (!response.ok) {
            throw new Error(`Error del servidor: ${response.status} ${response.statusText}`);
        }
        const data = await response.json();
        return data;
    }catch(error){
        console.error("Error al realizar la transcripción: ", error);
        return null;
    }
};
