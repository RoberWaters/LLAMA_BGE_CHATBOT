import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';
import {
  Send,
  Trash2,
  BarChart3,
  BookOpen,
} from 'lucide-react';
import './App.css';

// Components
import Microphone from './components/Microphone.jsx';
import SimliAvatar from './components/SimliAvatar.jsx';
import transcribe from './services/speechToText.mjs';


const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [audio, setAudio] = useState(null);
  const [stats, setStats] = useState(null);

  const [showStats, setShowStats] = useState(false);
  const messagesEndRef = useRef(null);
  const sessionId = useRef(`session-${Date.now()}`);
  const bedrockSessionId = useRef(null);
  const avatarRef = useRef(null);

  // Auto-scroll to bottom
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Cargar estadísticas al iniciar
  useEffect(() => {
    fetchStats();
  }, []);

  // Transcribir audio cuando el Microphone entrega un blob
  useEffect(() => {
    if (!audio) return;
    setIsTranscribing(true);
    transcribe(audio)
      .then(data => handleTranscriptionText(data?.text?.trim() || null))
      .catch(() => handleTranscriptionText(null))
      .finally(() => {
        setIsTranscribing(false);
        setAudio(null);
      });
  }, [audio]);

  // Manejar resultado de transcripción
  const handleTranscriptionText = (text) => {
    avatarRef.current?.unmute();
    if (!text) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: 'Lo siento, no pude entenderte en este momento. Por favor intenta de nuevo o escribe tu pregunta.',
        timestamp: new Date().toLocaleTimeString()
      }]);
      return;
    }
    setInputMessage(text);
    sendMessageWithText(text);
  };

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats?session_id=${sessionId.current}`);
      setStats(response.data);
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const sendMessage = async () => {
    await sendMessageWithText(inputMessage);
  }

  const MAX_MESSAGE_LENGTH = 10000;

  const sendMessageWithText = async (message) => {
    if (!message.trim() || isLoading) return;

    if (message.length > MAX_MESSAGE_LENGTH) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Tu mensaje sobrepasa el límite de ${MAX_MESSAGE_LENGTH.toLocaleString()} caracteres permitidos. Por favor acórtalo e intenta de nuevo.`,
        timestamp: new Date().toLocaleTimeString(),
      }]);
      return;
    }

    // Detener avatar si estaba hablando
    avatarRef.current?.stop();

    setMessages(prev => [...prev, {
      role: 'user',
      content: message,
      timestamp: new Date().toLocaleTimeString()
    }]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/chat-with-audio`, {
        message,
        session_id: sessionId.current,
        bedrock_session_id: bedrockSessionId.current,
        temperature: 0.7,
      });

      const { answer, sentences, bedrock_session_id } = response.data;
      if (bedrock_session_id) bedrockSessionId.current = bedrock_session_id;

      // Mostrar texto completo
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: answer,
        timestamp: new Date().toLocaleTimeString(),
      }]);

      // Enviar audio al avatar oración por oración
      for (const sentence of sentences) {
        await avatarRef.current?.speak(sentence.audio_base64);
      }

    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, {
        role: 'error',
        content: 'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.',
        timestamp: new Date().toLocaleTimeString(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearHistory = async () => {
    try {
      await axios.post(`${API_BASE_URL}/clear-history?session_id=${sessionId.current}`);
      bedrockSessionId.current = null;
      setMessages([]);
    } catch (error) {
      console.error('Error clearing history:', error);
    }
  };


  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };


  return (
    <div className="app-container">
      <div className="avatar-panel">
        <SimliAvatar ref={avatarRef} />
      </div>
      <div className="chat-container">
        {/* Header */}
        <div className="chat-header">
          <div className="header-content">
            <div className="header-title">
              <img
                src="/voae-logo.png"
                alt="VOAE Logo"
                style={{ height: '50px', marginRight: '5px' }}
              />
              <div>
                <h1>Chatbot VOAE</h1>
                <p>Vicerrectoría de Orientación y Asuntos Estudiantiles</p>
              </div>
            </div>
            <div className="header-actions">
              <button
                className="icon-button"
                onClick={() => setShowStats(!showStats)}
                title="Estadísticas"
              >
                <BarChart3 size={20} />
              </button>
              <button
                className="icon-button"
                onClick={clearHistory}
                title="Limpiar historial"
              >
                <Trash2 size={20} />
              </button>
            </div>
          </div>

          {/* Stats Panel */}
          {showStats && stats && (
            <div className="stats-panel">
              <div className="stat-item">
                <span className="stat-label">Proveedor:</span>
                <span className="stat-value">{stats.llm_provider}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Modelo:</span>
                <span className="stat-value">{stats.llm_model}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Historial:</span>
                <span className="stat-value">{stats.current_history_length}/{stats.max_history}</span>
              </div>
            </div>
          )}
        </div>

        {/* Messages */}
        <div className="messages-container">
          {messages.length === 0 && (
            <div className="welcome-message">
              <BookOpen size={64} className="welcome-icon" />
              <h2>¡Bienvenido al Chatbot VOAE!</h2>
              <p>Pregúntame sobre servicios estudiantiles, becas, inscripciones y más.</p>
              <div className="example-questions">
                <p className="example-label">Ejemplos de preguntas:</p>
                <div className="examples">
                  <span onClick={() => setInputMessage('¿Cómo solicito una beca?')}>
                    ¿Cómo solicito una beca?
                  </span>
                  <span onClick={() => setInputMessage('¿Qué servicios médicos ofrecen?')}>
                    ¿Qué servicios médicos ofrecen?
                  </span>
                  <span onClick={() => setInputMessage('¿Qué es Summa Cum Laude?')}>
                    ¿Qué es Summa Cum Laude?
                  </span>
                </div>
              </div>
            </div>
          )}

          {messages.map((message, index) => (
            <div key={index} className={`message ${message.role}`}>
              <div className="message-content">
                {message.role === 'assistant' && (
                  <div className="assistant-avatar">VOAE</div>
                )}
                <div className="message-bubble">
                  {message.role === 'assistant' ? (
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  ) : (
                    <p>{message.content}</p>
                  )}

                  <span className="message-time">{message.timestamp}</span>
                </div>
                {message.role === 'user' && (
                  <div className="user-avatar">Tú</div>
                )}
              </div>
            </div>
          ))}

          {(isLoading || isTranscribing) && (
            <div className="message assistant">
              <div className="message-content">
                <div className="assistant-avatar">VOAE</div>
                <div className="message-bubble typing">
                  <div className="typing-indicator">
                    <span></span>
                    <span></span>
                    <span></span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="input-container">
          <div className="input-wrapper">
            <textarea
              value={inputMessage}
              onChange={(e) => setInputMessage(e.target.value)}
              onKeyDown={handleKeyPress}
              placeholder="Escribe tu pregunta aquí..."
              rows="1"
              disabled={isLoading || isTranscribing}
            />
            <Microphone
              onRecorded={setAudio}
              onStartRecording={() => { avatarRef.current?.stop(); avatarRef.current?.mute(); }}
            />
            <button
              onClick={sendMessage}
              disabled={!inputMessage.trim() || isLoading || isTranscribing}
              className="send-button"
            >
              <Send size={20} />
            </button>
          </div>
          <p className="input-hint">
            Presiona Enter para enviar, Shift+Enter para nueva línea
          </p>
        </div>
      </div>
    </div>
  );
}

export default App;
