import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import axios from 'axios';
import {
  Send,
  Trash2,
  BarChart3,
  BookOpen,
  CheckCircle,
  AlertCircle,
  FileText
} from 'lucide-react';
import './App.css';

// Components
import Microphone from './components/Microphone.jsx';
import TalkingHeadAvatar from './components/TalkingHeadAvatar.jsx';

// Services
import transcribe from './services/speechToText.mjs';
import { preprocessTextForTTS, synthesize } from './services/textToSpeech.mjs';

const API_BASE_URL = 'http://localhost:8000';

function App() {
  const [messages, setMessages] = useState([]);
  const [inputMessage, setInputMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [stats, setStats] = useState(null);
  const [showStats, setShowStats] = useState(false);
  const [llmProvider, setLlmProvider] = useState('groq'); // 'groq' o 'deepseek'
  const [isChangingModel, setIsChangingModel] = useState(false);
  const [audio, setAudio] = useState(null);
  const [isSynthesizing, setIsSynthesizing] = useState(false);
  const messagesEndRef = useRef(null);
  const sessionId = useRef(`session-${Date.now()}`);
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

  // Realizar transcripción y envío del mensaje cuando se grabe un nuevo audio
  useEffect(() => {
    if (!audio) return;
    const fetchData = async () => {
      setIsTranscribing(true);
      const transcription = await transcribe(audio);
      setIsTranscribing(false);
      const text = transcription?.text;
      // There was an error when trying to transcribe the audio, show an error message in the chat
      if (text == null){
        const errorMessage = {
          role: 'error',
          content: 'Lo siento, no pude entenderte en este momento. Por favor intenta de nuevo o escribe tu pregunta.',
          timestamp: new Date().toLocaleTimeString()
        };
        setMessages(prev => [...prev, errorMessage]);
        return;
      }
      setInputMessage(text);
      sendMessageWithText(text);
    }
    fetchData();
  }, [audio]);

  const fetchStats = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/stats?session_id=${sessionId.current}`);
      setStats(response.data);
      // Actualizar el proveedor actual desde las estadísticas
      if (response.data.llm_provider) {
        setLlmProvider(response.data.llm_provider);
      }
    } catch (error) {
      console.error('Error fetching stats:', error);
    }
  };

  const sendMessage = async () => {
    await sendMessageWithText(inputMessage);
  }

  const sendMessageWithText = async (message) => {
    if (!message.trim() || isLoading) return;
    avatarRef.current?.stop();
    // Desbloquear AudioContext sincrónicamente desde el gesto del usuario
    // antes de entrar en la cadena async (API call + synthesis)
    avatarRef.current?.initAudio();

    const userMessage = {
      role: 'user',
      content: message,
      timestamp: new Date().toLocaleTimeString()
    };

    setMessages(prev => [...prev, userMessage]);
    setInputMessage('');
    setIsLoading(true);

    try {
      const response = await axios.post(`${API_BASE_URL}/chat`, {
        message: message,
        session_id: sessionId.current,
        top_k: 4,
        temperature: 0.7,
        llm_provider: llmProvider  // Enviar proveedor actual
      });

      const assistantMessage = {
        role: 'assistant',
        content: response.data.answer,
        timestamp: new Date().toLocaleTimeString(),
        matchType: response.data.match_type,
        similarity: response.data.best_faq_similarity,
        contextType: response.data.context_type,
        sources: response.data.relevant_documents
      };

      setMessages(prev => [...prev, assistantMessage]);

      // Sintetizar voz con Amazon Polly + avatar 3D (fire-and-forget, no bloquea)
      const plainText = preprocessTextForTTS(response.data.answer);
      setIsSynthesizing(true);
      synthesize(plainText).then((data) => {
        setIsSynthesizing(false);
        if (data && avatarRef.current) {
          avatarRef.current.speak(data);
        }
      }).catch(() => {
        setIsSynthesizing(false);
      });
    } catch (error) {
      console.error('Error sending message:', error);
      const errorMessage = {
        role: 'error',
        content: 'Lo siento, ocurrió un error al procesar tu mensaje. Por favor intenta de nuevo.',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const clearHistory = async () => {
    try {
      await axios.post(`${API_BASE_URL}/clear-history?session_id=${sessionId.current}`);
      setMessages([]);
    } catch (error) {
      console.error('Error clearing history:', error);
    }
  };

  const changeModel = async (newProvider) => {
    if (isChangingModel || isLoading) return;

    setIsChangingModel(true);
    try {
      const response = await axios.post(`${API_BASE_URL}/change-model`, {
        session_id: sessionId.current,
        llm_provider: newProvider
      });

      setLlmProvider(newProvider);

      // Mensaje de confirmación en el chat
      const confirmationMessage = {
        role: 'system',
        content: `Modelo cambiado a ${newProvider === 'groq' ? 'Groq (Llama 3.3 70B)' : 'DeepSeek'}. El historial se mantiene.`,
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, confirmationMessage]);

      // Actualizar estadísticas
      await fetchStats();
    } catch (error) {
      console.error('Error changing model:', error);
      const errorMessage = {
        role: 'error',
        content: 'Error al cambiar el modelo. Por favor intenta de nuevo.',
        timestamp: new Date().toLocaleTimeString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsChangingModel(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const getMatchIcon = (matchType) => {
    switch(matchType) {
      case 'high': return <CheckCircle size={16} className="match-icon high" />;
      case 'medium': return <AlertCircle size={16} className="match-icon medium" />;
      case 'low': return <FileText size={16} className="match-icon low" />;
      default: return null;
    }
  };

  const getMatchLabel = (matchType) => {
    switch(matchType) {
      case 'high': return 'FAQ Exacto';
      case 'medium': return 'FAQ + Docs';
      case 'low': return 'Documentos';
      default: return '';
    }
  };

  const handleStopAvatar = () => {
    avatarRef.current?.stop();
    // También desbloquear AudioContext cuando el usuario activa el micrófono
    avatarRef.current?.initAudio();
  };

  return (
    <div className="app-container">
      <div className="avatar-panel">
        <TalkingHeadAvatar ref={avatarRef} />
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
              {/* Selector de Modelo */}
              <div className="model-selector">
                <select
                  value={llmProvider}
                  onChange={(e) => changeModel(e.target.value)}
                  disabled={isChangingModel || isLoading}
                  className="model-select"
                  title="Cambiar modelo LLM"
                >
                  <option value="deepseek">DeepSeek</option>
                  <option value="groq">Groq (Llama 3.3 70B)</option>
                </select>
              </div>

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
                <span className="stat-label">Documentos:</span>
                <span className="stat-value">{stats.total_documents}</span>
              </div>
              <div className="stat-item">
                <span className="stat-label">Proveedor:</span>
                <span className="stat-value">{stats.llm_provider === 'groq' ? 'Groq' : 'DeepSeek'}</span>
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

                  {/* Match Info */}
                  {message.matchType && (
                    <div className="match-info">
                      {getMatchIcon(message.matchType)}
                      <span className="match-label">{getMatchLabel(message.matchType)}</span>
                      {message.similarity !== null && message.similarity > 0 && (
                        <span className="similarity">
                          ({(message.similarity * 100).toFixed(1)}%)
                        </span>
                      )}
                    </div>
                  )}

                  {/* Sources */}
                  {message.sources && message.sources.length > 0 && (
                    <div className="sources">
                      <p className="sources-title">Fuentes:</p>
                      {message.sources.slice(0, 3).map((source, idx) => (
                        <div key={idx} className="source-item">
                          <span className="source-icon">
                            {source.type === 'faq' ? '❓' : '📄'}
                          </span>
                          <span className="source-name">{source.filename}</span>
                          <span className="source-sim">
                            {(source.similarity * 100).toFixed(0)}%
                          </span>
                        </div>
                      ))}
                    </div>
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
              onKeyPress={handleKeyPress}
              placeholder="Escribe tu pregunta aquí..."
              rows="1"
              disabled={isLoading || isTranscribing}
            />
            <Microphone onRecorded={setAudio} onStartRecording={handleStopAvatar} />
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
