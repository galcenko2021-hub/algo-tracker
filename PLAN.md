# PLAN

## Архитектура

```
Browser ──> nginx (:8080) ──/──> статика React (Vite build)
                         └─/api─> FastAPI (uvicorn :8000) ──> PostgreSQL 16
                                      └─> Codeforces API (httpx, троттлинг 2 с)
```

- **Backend**: FastAPI, синхронный SQLAlchemy 2.0 (`Mapped[...]`) + psycopg 3, Alembic. Чистая логика
  (SM-2, серии, weakness, рекомендации) лежит в `app/services` и не зависит от БД: функции принимают
  простые структуры данных, роутеры только собирают данные из БД и вызывают сервисы.
- **Frontend**: React 18 + TS strict + Vite, React Router, TanStack Query, Tailwind. Access-токен хранится
  в памяти, refresh — httpOnly-cookie. Теплокарта — собственный SVG-компонент.
- **Инфраструктура**: docker-compose (db, backend, frontend), GitHub Actions (backend / frontend / docker).

## Структура репозитория

См. раздел 4 ТЗ (`PROMPT.md`): `backend/{app,alembic,scripts,tests}`, `frontend/src/{api,components,pages,hooks,lib}`,
`docker-compose.yml`, `.github/workflows/ci.yml`, `Makefile`, `.env.example`.

## Этапы

| Этап | Содержание |
| ---- | ---------- |
| M0 | Каркас, PLAN/DECISIONS, Makefile, `.env.example`, пустые backend/frontend, `/api/health` |
| M1 | Модели, миграция Alembic, подключение к БД, фикстуры тестов |
| M2 | Аутентификация: register/login/refresh/logout, rate limit, изоляция данных |
| M3 | Решения и теги: CRUD, фильтры, пагинация, автосоздание карточек |
| M4 | Статистика: summary, heatmap, серии, темы (weakness) |
| M5 | Повторения: SM-2, очередь, ответы, upcoming |
| M6 | Импорт Codeforces, каталог, `attempt_stats`, идемпотентность |
| M7 | Рекомендации: эвристика, ML с fallback, `eval_recommender.py` |
| M8 | Frontend: страницы и тесты компонентов |
| M9 | Docker, compose, GitHub Actions, seed |
| M10 | README и финальная проверка по чек-листу |
