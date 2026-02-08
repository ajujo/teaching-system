# Teaching System Frontend

Frontend Next.js para consumir la Web API del Teaching System.

## Requisitos

- Node.js 18+
- npm o yarn
- Backend corriendo en `http://localhost:8000`

## Inicio rapido

```bash
# Navegar al directorio web
cd web

# Instalar dependencias
npm install

# Iniciar servidor de desarrollo
npm run dev
```

Abrir http://localhost:3000

## Configuracion

El archivo `.env.local` contiene la URL del backend:

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Modificar si el backend corre en otro puerto/host.

## Estructura

```
web/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # Layout principal
│   │   ├── page.tsx          # Lobby (pagina principal)
│   │   ├── globals.css       # Estilos globales + Tailwind
│   │   └── session/
│   │       └── [sessionId]/
│   │           └── page.tsx  # Pagina de sesion
│   ├── components/
│   │   ├── ChatMessage.tsx   # Mensaje del tutor con estilos
│   │   └── TypewriterText.tsx # Efecto typewriter
│   └── lib/
│       ├── api.ts            # Funciones para llamar al backend
│       └── types.ts          # Tipos TypeScript
├── package.json
├── tailwind.config.js
└── next.config.js
```

## Funcionalidades

### Lobby (/)

- **Listar estudiantes**: Muestra todos los estudiantes registrados
- **Crear estudiante**: Formulario para nombre, apellido, email
- **Eliminar estudiante**: Boton para eliminar
- **Seleccionar persona**: Dropdown con tutores disponibles
- **Seleccionar libro**: Dropdown con libros mock o input libre
- **Iniciar sesion**: Navega a la sesion creada

### Sesion (/session/[sessionId])

- **SSE (Server-Sent Events)**: Conexion en tiempo real al backend
- **Chat**: Muestra eventos del tutor con estilos por tipo
- **Input**: Campo de texto para responder
- **Botones rapidos**: apuntes, siguiente, repasar, stop
- **Typewriter**: Animacion de texto caracter a caracter
- **Reconexion**: Indicador cuando se pierde conexion
- **Terminar**: Boton para cerrar sesion y volver al lobby

## Tipos de eventos

| Tipo | Estilo | Icono |
|------|--------|-------|
| UNIT_OPENING | Azul | 📚 |
| POINT_OPENING | Purpura | 📌 |
| POINT_EXPLANATION | Blanco | 💡 |
| ASK_CHECK | Amarillo | ❓ |
| FEEDBACK | Verde | ✅ |
| ASK_CONFIRM_ADVANCE | Indigo | ➡️ |
| UNIT_NOTES | Teal | 📝 |

## Animacion Typewriter

El componente `TypewriterText` anima el texto caracter a caracter:

- **slow**: 50ms por caracter
- **normal**: 20ms por caracter
- **fast**: 5ms por caracter

La velocidad se determina por:
1. `event.data.pace` si esta definido
2. Tipo de evento (explicaciones = normal, preguntas = fast)

## Scripts

```bash
npm run dev      # Desarrollo con hot reload
npm run build    # Build de produccion
npm run start    # Iniciar build de produccion
npm run lint     # Lint del codigo
```

## Desarrollo

### Arrancar backend y frontend juntos

Terminal 1 (backend):
```bash
uv run uvicorn teaching.web.api:app --reload --port 8000
```

Terminal 2 (frontend):
```bash
cd web && npm run dev
```

### CORS

El backend ya tiene CORS configurado para aceptar cualquier origen.
Para produccion, configurar dominios especificos en `api.py`.

## Tecnologias

- **Next.js 14** - React framework con App Router
- **TypeScript** - Tipado estatico
- **Tailwind CSS** - Estilos utilitarios
- **react-markdown** - Renderizado de Markdown
- **remark-gfm** - Soporte para GitHub Flavored Markdown
