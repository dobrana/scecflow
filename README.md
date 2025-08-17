# Requirements Tracker MVP

Fullstack приложение для управления техническими требованиями с использованием AI для анализа документов.

## Технологии

- **Frontend**: Next.js 14, React, TypeScript, Tailwind CSS
- **Backend**: FastAPI, Python
- **База данных**: Supabase
- **Аутентификация**: Supabase Auth
- **Деплой**: Vercel

## Структура проекта

```
requirements-tracker-mvp/
├── frontend/          # Next.js приложение
├── backend/           # FastAPI сервер
├── test_data/         # Тестовые данные
├── vercel.json        # Конфигурация Vercel
└── README.md
```

## Установка и запуск

### Предварительные требования

- Node.js 18+
- Python 3.9+
- Supabase аккаунт

### Локальная разработка

1. **Клонируйте репозиторий:**
   ```bash
   git clone <your-repo-url>
   cd requirements-tracker-mvp
   ```

2. **Настройте фронтенд:**
   ```bash
   cd frontend
   npm install
   ```

3. **Настройте бэкенд:**
   ```bash
   cd backend
   python -m venv venv
   # Windows:
   venv\Scripts\activate
   # macOS/Linux:
   source venv/bin/activate
   
   pip install -r app/requirements.txt
   ```

4. **Настройте переменные окружения:**
   
   Создайте файл `.env.local` в папке `frontend/`:
   ```
   NEXT_PUBLIC_SUPABASE_URL=your_supabase_url
   NEXT_PUBLIC_SUPABASE_ANON_KEY=your_supabase_anon_key
   NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
   ```
   
   Создайте файл `.env` в папке `backend/`:
   ```
   SUPABASE_URL=your_supabase_url
   SUPABASE_SERVICE_KEY=your_supabase_service_key
   ```

5. **Запустите приложение:**
   
   В одном терминале (бэкенд):
   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   
   В другом терминале (фронтенд):
   ```bash
   cd frontend
   npm run dev
   ```

6. **Откройте браузер:**
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000

## Деплой на Vercel

1. **Подключите репозиторий к Vercel**
2. **Настройте переменные окружения в Vercel:**
   - `NEXT_PUBLIC_SUPABASE_URL`
   - `NEXT_PUBLIC_SUPABASE_ANON_KEY`
   - `NEXT_PUBLIC_API_URL` (автоматически)
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_KEY`

3. **Деплой произойдет автоматически при push в main ветку**

## Функциональность

- ✅ Аутентификация пользователей
- ✅ Создание и редактирование документов
- ✅ Загрузка и обработка транскриптов
- ✅ AI анализ документов
- ✅ История анализа
- ✅ Система обратной связи

## Лицензия

MIT
