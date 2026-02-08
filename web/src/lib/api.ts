// API helper for Teaching System backend

import type {
  Student,
  StudentCreate,
  Persona,
  Session,
  SessionStart,
  TutorEvent,
} from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

// Generic fetcher with error handling
async function fetcher<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

// ============================================================================
// Students API
// ============================================================================

export async function listStudents(): Promise<{ students: Student[]; count: number }> {
  return fetcher('/api/students');
}

export async function getStudent(studentId: string): Promise<Student> {
  return fetcher(`/api/students/${studentId}`);
}

export async function createStudent(data: StudentCreate): Promise<Student> {
  return fetcher('/api/students', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteStudent(studentId: string): Promise<void> {
  return fetcher(`/api/students/${studentId}`, {
    method: 'DELETE',
  });
}

// ============================================================================
// Personas API
// ============================================================================

export async function listPersonas(): Promise<{ personas: Persona[]; count: number }> {
  return fetcher('/api/personas');
}

export async function getPersona(personaId: string): Promise<Persona> {
  return fetcher(`/api/personas/${personaId}`);
}

// ============================================================================
// Sessions API
// ============================================================================

export async function startSession(data: SessionStart): Promise<Session> {
  return fetcher('/api/sessions', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function getSession(sessionId: string): Promise<Session> {
  return fetcher(`/api/sessions/${sessionId}`);
}

export async function endSession(sessionId: string): Promise<void> {
  return fetcher(`/api/sessions/${sessionId}`, {
    method: 'DELETE',
  });
}

export async function sendInput(
  sessionId: string,
  text: string
): Promise<TutorEvent[]> {
  return fetcher(`/api/sessions/${sessionId}/input`, {
    method: 'POST',
    body: JSON.stringify({ text }),
  });
}

// ============================================================================
// SSE Helper
// ============================================================================

export function createEventSource(sessionId: string): EventSource {
  const url = `${API_BASE}/api/sessions/${sessionId}/events`;
  return new EventSource(url);
}

// Parse SSE event data safely
export function parseEventData(data: string): TutorEvent | null {
  try {
    return JSON.parse(data) as TutorEvent;
  } catch {
    console.error('Failed to parse event data:', data);
    return null;
  }
}
