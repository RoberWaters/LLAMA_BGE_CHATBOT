// Speech to Text Service connection with the backend

// Returns a promise to transcribe the given audio blob
export default async function transcribe(audioBlob){
    const apiUrl = import.meta.env.VITE_API_URL;
    const requestBody = new FormData();
    requestBody.append('audio', audioBlob, "recording.webm");
    try{
        const response = await fetch(`${apiUrl}/transcribe`, {
            method: 'POST',
            body: requestBody,
        });
        const data = await response.json();
        return data;
    }catch(error){
        console.error("Error al realizar la transcripción: ", error);
        return null;
    }
};
