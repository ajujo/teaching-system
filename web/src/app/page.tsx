'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import {
  listStudents,
  createStudent,
  deleteStudent,
  listPersonas,
  listBooks,
  startSession,
} from '@/lib/api';
import type { Student, Persona, Book } from '@/lib/types';

export default function LobbyPage() {
  const router = useRouter();

  // State
  const [students, setStudents] = useState<Student[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [books, setBooks] = useState<Book[]>([]);
  const [selectedStudent, setSelectedStudent] = useState<string>('');
  const [selectedPersona, setSelectedPersona] = useState<string>('');
  const [selectedBook, setSelectedBook] = useState<string>('');

  // Form state
  const [newName, setNewName] = useState('');
  const [newSurname, setNewSurname] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [showForm, setShowForm] = useState(false);

  // Loading/error state
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  // Load data on mount
  useEffect(() => {
    async function loadData() {
      try {
        setLoading(true);
        const [studentsData, personasData, booksData] = await Promise.all([
          listStudents(),
          listPersonas(),
          listBooks(),
        ]);
        setStudents(studentsData.students);
        setPersonas(personasData.personas);
        setBooks(booksData.books);

        // Auto-select default persona
        const defaultPersona = personasData.personas.find((p) => p.default);
        if (defaultPersona) {
          setSelectedPersona(defaultPersona.id);
        }

        // Auto-select first student if exists
        if (studentsData.students.length > 0) {
          setSelectedStudent(studentsData.students[0].student_id);
        }

        // Auto-select first book if exists
        if (booksData.books.length > 0) {
          setSelectedBook(booksData.books[0].id);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error loading data');
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // Create student handler
  const handleCreateStudent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;

    try {
      setCreating(true);
      setError(null);
      const student = await createStudent({
        name: newName.trim(),
        surname: newSurname.trim(),
        email: newEmail.trim(),
        tutor_persona_id: selectedPersona || 'dra_vega',
      });
      setStudents([...students, student]);
      setSelectedStudent(student.student_id);
      setNewName('');
      setNewSurname('');
      setNewEmail('');
      setShowForm(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error creating student');
    } finally {
      setCreating(false);
    }
  };

  // Delete student handler
  const handleDeleteStudent = async (studentId: string) => {
    if (!confirm('¿Eliminar este estudiante?')) return;

    try {
      await deleteStudent(studentId);
      setStudents(students.filter((s) => s.student_id !== studentId));
      if (selectedStudent === studentId) {
        setSelectedStudent(students[0]?.student_id || '');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error deleting student');
    }
  };

  // Start session handler
  const handleStartSession = async () => {
    if (!selectedStudent || !selectedBook) {
      setError('Selecciona un estudiante y un libro');
      return;
    }

    try {
      setError(null);
      const session = await startSession({
        student_id: selectedStudent,
        book_id: selectedBook,
        chapter_number: 1,
        unit_number: 1,
      });
      router.push(`/session/${session.session_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Error starting session');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-gray-500">Cargando...</div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto p-6">
      {/* Header */}
      <header className="mb-8">
        <h1 className="text-3xl font-bold text-gray-800">Teaching System</h1>
        <p className="text-gray-600 mt-1">Selecciona estudiante y comienza una sesion</p>
      </header>

      {/* Error message */}
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-6">
          {error}
          <button
            onClick={() => setError(null)}
            className="float-right text-red-500 hover:text-red-700"
          >
            ✕
          </button>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Students section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <span>👤</span> Estudiantes
          </h2>

          {/* Student list */}
          <div className="space-y-2 mb-4">
            {students.length === 0 ? (
              <p className="text-gray-500 text-sm">No hay estudiantes. Crea uno nuevo.</p>
            ) : (
              students.map((student) => (
                <div
                  key={student.student_id}
                  className={`flex items-center justify-between p-3 rounded border cursor-pointer transition-colors ${
                    selectedStudent === student.student_id
                      ? 'border-blue-500 bg-blue-50'
                      : 'border-gray-200 hover:bg-gray-50'
                  }`}
                  onClick={() => setSelectedStudent(student.student_id)}
                >
                  <div>
                    <div className="font-medium">
                      {student.name} {student.surname}
                    </div>
                    <div className="text-sm text-gray-500">{student.email || 'Sin email'}</div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteStudent(student.student_id);
                    }}
                    className="text-red-500 hover:text-red-700 p-1"
                    title="Eliminar"
                  >
                    🗑️
                  </button>
                </div>
              ))
            )}
          </div>

          {/* Create student form */}
          {showForm ? (
            <form onSubmit={handleCreateStudent} className="space-y-3 border-t pt-4">
              <input
                type="text"
                placeholder="Nombre *"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
              <input
                type="text"
                placeholder="Apellido"
                value={newSurname}
                onChange={(e) => setNewSurname(e.target.value)}
                className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <input
                type="email"
                placeholder="Email"
                value={newEmail}
                onChange={(e) => setNewEmail(e.target.value)}
                className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <div className="flex gap-2">
                <button
                  type="submit"
                  disabled={creating || !newName.trim()}
                  className="flex-1 bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  {creating ? 'Creando...' : 'Crear'}
                </button>
                <button
                  type="button"
                  onClick={() => setShowForm(false)}
                  className="px-4 py-2 border rounded hover:bg-gray-50"
                >
                  Cancelar
                </button>
              </div>
            </form>
          ) : (
            <button
              onClick={() => setShowForm(true)}
              className="w-full py-2 border-2 border-dashed border-gray-300 rounded text-gray-500 hover:border-blue-500 hover:text-blue-500 transition-colors"
            >
              + Nuevo estudiante
            </button>
          )}
        </section>

        {/* Session config section */}
        <section className="bg-white rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 flex items-center gap-2">
            <span>⚙️</span> Configuracion
          </h2>

          {/* Persona selector */}
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Tutor (Persona)
            </label>
            <select
              value={selectedPersona}
              onChange={(e) => setSelectedPersona(e.target.value)}
              className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {personas.map((persona) => (
                <option key={persona.id} value={persona.id}>
                  {persona.name} - {persona.short_title}
                </option>
              ))}
            </select>
            {selectedPersona && (
              <p className="mt-1 text-sm text-gray-500">
                {personas.find((p) => p.id === selectedPersona)?.background.slice(0, 100)}...
              </p>
            )}
          </div>

          {/* Book selector */}
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Libro ({books.length} disponibles)
            </label>
            {books.length === 0 ? (
              <p className="text-gray-500 text-sm">No hay libros disponibles</p>
            ) : (
              <select
                value={selectedBook}
                onChange={(e) => setSelectedBook(e.target.value)}
                className="w-full px-3 py-2 border rounded focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                {books.map((book) => (
                  <option key={book.id} value={book.id}>
                    {book.title}
                  </option>
                ))}
              </select>
            )}
            <p className="mt-1 text-xs text-gray-400">
              Tambien puedes escribir un ID de libro personalizado
            </p>
            <input
              type="text"
              placeholder="O escribe book_id..."
              value={selectedBook}
              onChange={(e) => setSelectedBook(e.target.value)}
              className="mt-2 w-full px-3 py-2 border rounded text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>

          {/* Start button */}
          <button
            onClick={handleStartSession}
            disabled={!selectedStudent || !selectedBook}
            className="w-full bg-green-600 text-white py-3 rounded-lg font-semibold hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            🚀 Iniciar Sesion
          </button>

          {!selectedStudent && (
            <p className="mt-2 text-sm text-orange-600 text-center">
              Selecciona o crea un estudiante
            </p>
          )}
        </section>
      </div>

      {/* Footer */}
      <footer className="mt-8 text-center text-sm text-gray-400">
        Teaching System MVP - F9 Web Frontend
      </footer>
    </div>
  );
}
