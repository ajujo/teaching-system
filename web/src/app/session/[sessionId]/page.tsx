'use client';

import { useState, useEffect, useRef } from 'react';
import { useParams, useRouter } from 'next/navigation';
import {
  getSession,
  endSession,
  sendInput,
  createEventSource,
  parseEventData,
  NotFoundError,
} from '@/lib/api';
import type { Session, TutorEvent } from '@/lib/types';
import ChatMessage from '@/components/ChatMessage';

// Message shown when session is not found (404)
const SESSION_NOT_FOUND_MESSAGE =
  'La sesión ha expirado o el servidor fue reiniciado. Las sesiones se almacenan en memoria y se pierden al reiniciar el servidor.';

// Quick action buttons
const QUICK_ACTIONS = [
  { label: 'Apuntes', value: 'apuntes', icon: '📝' },
  { label: 'Siguiente', value: 'siguiente', icon: '➡️' },
  { label: 'Repasar', value: 'repasar', icon: '🔄' },
  { label: 'Stop', value: 'stop', icon: '⏹️' },
];

export default function SessionPage() {
  const params = useParams();
  const router = useRouter();
  const sessionId = params.sessionId as string;

  // State
  const [session, setSession] = useState<Session | null>(null);
  const [events, setEvents] = useState<TutorEvent[]>([]);
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reconnecting, setReconnecting] = useState(false);
  const [animatingEventId, setAnimatingEventId] = useState<string | null>(null);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const hasInitialized = useRef(false);

  // Scroll to bottom when new events arrive
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  // Load session and connect SSE on mount - RUN ONLY ONCE
  useEffect(() => {
    // Prevent double initialization (React StrictMode)
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    async function init() {
      try {
        setLoading(true);

        // First verify session exists
        const sessionData = await getSession(sessionId);
        setSession(sessionData);

        // Then connect SSE - only once
        const es = createEventSource(sessionId);
        eventSourceRef.current = es;

        es.addEventListener('tutor_event', (e) => {
          const event = parseEventData(e.data);
          if (event) {
            setEvents((prev) => {
              // Check for duplicates
              if (prev.some((ev) => ev.event_id === event.event_id)) {
                return prev;
              }
              // Add and sort by (turn_id, seq)
              const updated = [...prev, event];
              updated.sort((a, b) => {
                if (a.turn_id !== b.turn_id) return a.turn_id - b.turn_id;
                return a.seq - b.seq;
              });
              return updated;
            });
            setAnimatingEventId(event.event_id);
            setTimeout(scrollToBottom, 100);
            setReconnecting(false);
          }
        });

        es.addEventListener('keepalive', () => {
          setReconnecting(false);
        });

        es.addEventListener('close', () => {
          console.log('Session closed by server');
          es.close();
        });

        es.addEventListener('error', () => {
          console.log('Session SSE error');
        });

        es.onerror = () => {
          setReconnecting(true);
        };

        es.onopen = () => {
          setReconnecting(false);
        };

      } catch (err) {
        // Handle 404 specifically - redirect to lobby with message
        if (err instanceof NotFoundError) {
          alert(SESSION_NOT_FOUND_MESSAGE);
          router.push('/');
          return;
        }
        setError(err instanceof Error ? err.message : 'Error loading session');
      } finally {
        setLoading(false);
      }
    }

    init();

    // Cleanup on unmount
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
        eventSourceRef.current = null;
      }
    };
  }, [sessionId, router]);

  // Add event helper for user messages
  const addUserEvent = (text: string) => {
    const userEvent: TutorEvent = {
      event_id: `user-${Date.now()}`,
      event_type: 'USER_INPUT',
      turn_id: events.length > 0 ? events[events.length - 1].turn_id + 1 : 1,
      seq: 0,
      title: '',
      markdown: text,
      data: { isUser: true },
    };
    setEvents((prev) => [...prev, userEvent]);
    setTimeout(scrollToBottom, 100);
  };

  // Send input handler
  const handleSendInput = async (text: string) => {
    if (!text.trim() || sending) return;

    try {
      setSending(true);
      setError(null);
      setInputText('');

      // Add user message as pseudo-event for display
      addUserEvent(text);

      // Send to backend - events come through SSE
      await sendInput(sessionId, text);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error sending input');
    } finally {
      setSending(false);
      inputRef.current?.focus();
    }
  };

  // Form submit
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleSendInput(inputText);
  };

  // End session handler
  const handleEndSession = async () => {
    if (!confirm('¿Terminar esta sesion?')) return;

    try {
      await endSession(sessionId);
      router.push('/');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error ending session');
    }
  };

  // Animation complete handler
  const handleAnimationComplete = (eventId: string) => {
    setAnimatingEventId((current) => (current === eventId ? null : current));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">Cargando sesion...</div>
      </div>
    );
  }

  if (!session) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <p className="text-red-500 mb-4">Sesion no encontrada</p>
          <button
            onClick={() => router.push('/')}
            className="text-blue-600 hover:underline"
          >
            Volver al inicio
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b px-4 py-3 flex items-center justify-between">
        <div>
          <h1 className="font-semibold text-gray-800">
            Sesion: {session.book_id}
          </h1>
          <p className="text-sm text-gray-500">
            Capitulo {session.chapter_number} · Unidad {session.unit_number}
          </p>
        </div>
        <button
          onClick={handleEndSession}
          className="px-4 py-2 text-red-600 hover:bg-red-50 rounded transition-colors"
        >
          Terminar
        </button>
      </header>

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 border-b border-red-200 text-red-700 px-4 py-2 text-sm">
          {error}
          <button
            onClick={() => setError(null)}
            className="float-right text-red-500"
          >
            ✕
          </button>
        </div>
      )}

      {/* Messages area */}
      <main className="flex-1 overflow-y-auto p-4">
        <div className="max-w-3xl mx-auto">
          {events.length === 0 ? (
            <div className="text-center text-gray-400 mt-8">
              <p>Esperando respuesta del tutor...</p>
              <p className="text-sm mt-2">Escribe algo para comenzar</p>
            </div>
          ) : (
            events.map((event) => (
              // Skip user input display in main chat (handled separately)
              event.data?.isUser ? (
                <div
                  key={event.event_id}
                  className="flex justify-end mb-3"
                >
                  <div className="bg-blue-600 text-white px-4 py-2 rounded-lg max-w-md">
                    {event.markdown}
                  </div>
                </div>
              ) : (
                <ChatMessage
                  key={event.event_id}
                  event={event}
                  animate={event.event_id === animatingEventId}
                  onAnimationComplete={() => handleAnimationComplete(event.event_id)}
                />
              )
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </main>

      {/* Reconnecting overlay */}
      {reconnecting && (
        <div className="reconnecting-overlay">
          <span className="animate-spin">⟳</span>
          <span>Reconectando...</span>
        </div>
      )}

      {/* Input area */}
      <footer className="bg-white border-t p-4">
        <div className="max-w-3xl mx-auto">
          {/* Quick actions */}
          <div className="flex gap-2 mb-3 flex-wrap">
            {QUICK_ACTIONS.map((action) => (
              <button
                key={action.value}
                onClick={() => handleSendInput(action.value)}
                disabled={sending}
                className="quick-btn border-gray-300 hover:border-gray-400"
              >
                <span className="mr-1">{action.icon}</span>
                {action.label}
              </button>
            ))}
          </div>

          {/* Input form */}
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              placeholder="Escribe tu respuesta..."
              disabled={sending}
              className="flex-1 px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              type="submit"
              disabled={sending || !inputText.trim()}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {sending ? '...' : 'Enviar'}
            </button>
          </form>
        </div>
      </footer>
    </div>
  );
}
