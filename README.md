# algo-tracker

Веб-трекер решённых алгоритмических задач: теплокарта активности, разбор по темам и напоминания о повторении.

**Стек:** TypeScript, React, FastAPI, PostgreSQL.

| Дашборд | Повторение |
| --- | --- |
| ![Дашборд](docs/screenshots/dashboard.png) | ![Повторение](docs/screenshots/reviews.png) |
| **Рекомендации** | **Темы** |
| ![Рекомендации](docs/screenshots/recommendations.png) | ![Темы](docs/screenshots/topics.png) |

> Скриншоты сняты на **синтетических демо-данных** (`scripts/seed_demo.py`), а блок рекомендаций — с живым каталогом задач Codeforces.

## Что умеет

- Заносить решённые задачи вручную или импортировать их с Codeforces (идемпотентно).
- Показывать теплокарту активности (53 недели × 7 дней), серии (streak) и сводку за 7/30 дней.
- Разбирать решения по темам (тегам) и считать «слабость» каждой темы.
- Напоминать о повторении по алгоритму интервального повторения **SM-2**.
- Рекомендовать, какую задачу решать дальше: эвристика по слабым темам и, при достаточном объёме данных, персональная ML-модель.

Интерфейс на русском языке. Код, имена и коммиты — на английском.

## Архитектура

```mermaid
flowchart LR
    B[Браузер] -->|:8080| N[nginx]
    N -->|статика| S[(React bundle)]
    N -->|/api| A[FastAPI]
    A --> P[(PostgreSQL 16)]
    A -->|httpx, 1 запрос / 2 с| CF[Codeforces API]
    subgraph backend
      A --> SV[services: sm2, stats, importer, recommender]
    end
```

- **Backend** (`backend/`): FastAPI, Pydantic v2, SQLAlchemy 2.0 (`Mapped[...]`), Alembic, psycopg 3. Чистая логика (SM-2, серии, weakness, рекомендации) в `app/services` не зависит от БД и покрыта тестами; роутеры в `app/api` только собирают данные.
- **Frontend** (`frontend/`): React 18, Vite, React Router, TanStack Query, Tailwind CSS, Recharts. Теплокарта — собственный SVG-компонент.
- **Инфраструктура:** docker-compose (`db`, `backend`, `frontend`), GitHub Actions, Makefile.

Принятые решения записаны в [DECISIONS.md](DECISIONS.md), план — в [PLAN.md](PLAN.md).

## Быстрый старт

### Docker

```bash
docker compose up --build
```

Приложение: <http://localhost:8080>. Документация API (OpenAPI): <http://localhost:8080/api/docs>.
Backend при старте применяет `alembic upgrade head`. Настройки по умолчанию подходят для локального запуска; для своих значений скопируйте `.env.example` в `.env`.

Демо-данные (синтетические):

```bash
docker compose exec backend python -m scripts.seed_demo
# вход: demo@example.com / demo12345
```

### Локальная разработка

Нужны Python 3.12, [uv](https://docs.astral.sh/uv/), Node 20 и PostgreSQL 16 (например, `docker compose up db`).

```bash
cp .env.example .env          # при необходимости поправьте DATABASE_URL
make migrate                  # alembic upgrade head
make seed                     # демо-пользователь с синтетической историей
make dev                      # backend :8000 + Vite :5173 (прокси /api -> :8000)
```

| Команда | Действие |
| --- | --- |
| `make dev` | backend (uvicorn --reload) и frontend (Vite) |
| `make test` | pytest с покрытием и vitest |
| `make lint` | ruff, mypy, eslint, prettier, tsc |
| `make migrate` | применить миграции |
| `make seed` | создать демо-данные |
| `make up` / `make down` | docker compose up --build / down |

Для backend-тестов нужен реальный PostgreSQL: задайте `TEST_DATABASE_URL` (по умолчанию `postgresql+psycopg://algo:algo@localhost:5432/algo_test`). Тесты пересоздают в этой БД схему через Alembic. **Тесты никогда не ходят в сеть**: Codeforces мокается через `httpx.MockTransport` и JSON-фикстуры из `backend/tests/fixtures/`.

## Переменные окружения

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `ENVIRONMENT` | `dev` | `prod` включает `Secure` для refresh-cookie и запрещает дефолтный секрет |
| `SECRET_KEY` | dev-значение | ключ подписи JWT; в `prod` обязателен собственный |
| `DATABASE_URL` | `postgresql+psycopg://algo:algo@localhost:5432/algo` | подключение к БД |
| `TEST_DATABASE_URL` | `…/algo_test` | БД для тестов |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:8080` | разрешённые origins через запятую |
| `ACCESS_TOKEN_MINUTES` | `15` | срок жизни access-токена |
| `REFRESH_TOKEN_DAYS` | `14` | срок жизни refresh-токена |
| `POSTGRES_USER/PASSWORD/DB` | `algo` | параметры контейнера БД (compose) |

Секреты в репозиторий не попадают: только `.env.example`.

## API

Префикс `/api`, интерактивная документация — `/api/docs` (схема: `/api/openapi.json`). Все эндпоинты, кроме `/auth/*` и `/health`, требуют `Authorization: Bearer <access>`; данные строго изолированы по пользователям.

| Группа | Эндпоинты |
| --- | --- |
| Аутентификация | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout` (лимит 10 запросов/мин на IP) |
| Профиль | `GET/PATCH /me` (`cf_handle`, `timezone`) |
| Решения | `POST/GET /solves`, `PATCH/DELETE /solves/{id}`, `GET /tags?q=` |
| Статистика | `GET /stats/summary`, `/stats/heatmap`, `/stats/topics` |
| Повторения | `GET /reviews/due`, `POST /reviews/{id}/answer`, `GET /reviews/upcoming` |
| Импорт | `POST /import/codeforces` |
| Рекомендации | `GET /recommendations?limit=5` |

Отличия от исходной формулировки ТЗ (причины — в DECISIONS.md): OpenAPI живёт на `/api/docs`, а `GET /recommendations` возвращает объект `{method, fallback_reason, level, items}`, чтобы сообщать о fallback на эвристику.

## Алгоритмы

### SM-2 (повторения)

Карточка создаётся вместе с решением; первое повторение — на следующий локальный день (для задним числом внесённых решений — сегодня). Кнопки интерфейса: «Снова» → 1, «Трудно» → 3, «Хорошо» → 4, «Легко» → 5.

- `quality < 3`: `repetitions = 0`, `interval = 1`, `lapses += 1`, `ease` не меняется.
- Иначе: `repetitions == 0` → интервал 1; `== 1` → 6; дальше `round(interval · ease)`; затем `repetitions += 1`.
- `ease = max(1.3, ease + 0.1 − (5 − q)·(0.08 + (5 − q)·0.02))`, применяется при `q ≥ 3`.
- `due_date = today + interval`.

Интервал считается по `ease` *до* текущего ответа, поэтому ближайший интервал для «Трудно/Хорошо/Легко» совпадает, а разница копится через `ease`. Планировщик спрятан за интерфейсом `Scheduler` — его можно заменить на FSRS.

### Слабость темы

Для тега `t` при `N` решениях всего: `coverage = solved_t / N`; `quality` — средняя оценка повторений по задачам тега, сглаженная к априорному значению 3.5 с весом 3 наблюдения;

```
weakness = 0.5 · (1 − min(1, coverage / 0.15)) + 0.5 · (1 − quality / 5)      # от 0 до 1
```

### Рекомендации, уровень 1 — эвристика

1. Уровень = медиана рейтингов последних 20 решённых задач с рейтингом (по умолчанию 800), округлённая до 100.
2. Кандидаты из каталога Codeforces (`cf_catalog`, обновляется по требованию, TTL 24 ч): не решены, рейтинг в `[level − 100, level + 200]`.
3. `score = Σ weakness_t / √(число тегов) + 0.2 · closeness`, где `closeness = 1 − |rating − (level + 100)| / 300`.
4. Для каждой задачи строится текстовое объяснение («Слабая тема: dp (решено 3, средняя оценка повторений 2.8). Рейтинг 1200 близок к вашему уровню 1100.»).

### Рекомендации, уровень 2 — ML

Отдельная модель на пользователя: `LogisticRegression` (L2), обучаемая на `attempt_stats` после импорта с Codeforces. Метка — «решил / не решил»; признаки — `(rating − level)/400`, `log(1 + solved_count)/10`, multi-hot по тегам. `C` подбирается кросс-валидацией, **учитывающей время** (`TimeSeriesSplit`); оценка качества — хронологический hold-out (первые 80% по `first_attempt_at` — обучение, последние 20% — тест, без перемешивания).

Минимум данных: ≥ 100 задач с попытками (и известным рейтингом), из них ≥ 20 решённых и ≥ 20 нерешённых. Иначе используется эвристика, а в ответе API `method = "heuristic"` и `fallback_reason` с причиной. Для кандидатов `score = weakness_sum + 1 − |p_solve − 0.6| / 0.6`, где `weakness_sum` нормирован как в эвристике.

#### Метрики на синтетических данных

> ⚠️ **Синтетические данные.** Скрипт `scripts/eval_recommender.py` моделирует 20 вымышленных пользователей (скрытый навык, растущий со временем, скрытая склонность к темам, смещение выбора задач), по 400 попыток каждый. Это проверка того, что пайплайн восстанавливает *заложенный* сигнал; на реальных людях такие цифры ничего не доказывают.

```text
uv run python -m scripts.eval_recommender
=== SYNTHETIC DATA: simulated users, not real people ===
simulated users: 20, attempts per user: 400
split: chronological, train 320 / test 80
metric                                      model   baseline (rating-level only)
ROC-AUC (higher is better)          0.825 ± 0.038                  0.808 ± 0.032
log-loss (lower is better)          0.544 ± 0.052                  0.562 ± 0.053
selected C (median): 1.0
```

Модель немного лучше базовой («только `rating − level`»): выигрыш невелик и сопоставим с разбросом между пользователями.

## Ограничения

- **Смещение выбора.** Пользователь сам выбирает, что пробовать, поэтому по его попыткам нельзя судить о задачах, к которым он не притронулся.
- **«Не решил» ≠ «не смог бы решить».** Нерешённая задача могла быть брошена из-за нехватки времени или интереса.
- **Мало данных на одного человека.** Модель обучается на сотнях строк; метрики шумные. ML обучается заново при каждом запросе (без кэша).
- Формулы `score` из ТЗ дают сумму слабостей, которая у задач с многими редкими тегами заметно больше, чем «зона ближайшего развития» (`p ≈ 0.6`): в реальных данных ML-рекомендации могут иметь `p_solve` заметно выше 0.6.
- **Это эвристическая рекомендательная система, а не доказательство или измерение навыка.**
- Серии и агрегации считаются в часовом поясе пользователя; «дата решения» в форме — только день (см. DECISIONS.md, п. 23).

## Безопасность и компромиссы

- Пароли — `argon2`; access-JWT живёт 15 минут и хранится только в памяти страницы; refresh-JWT — httpOnly-cookie `SameSite=Lax` (`Secure` вне `dev`), путь `/api/auth`.
- Единое сообщение об ошибке входа (не раскрывает, существует ли email), выравнивание времени проверки пароля.
- CORS только для origins из окружения; валидация входных данных Pydantic; SQL только через ORM/параметры; ссылки задач принимаются только `http(s)`.
- **Компромисс: refresh-токен stateless.** `logout` очищает cookie, но не отзывает токен: до истечения срока (14 дней) украденный refresh остаётся действительным. Для отзыва потребуется хранилище токенов (таблица или Redis).
- Лимит запросов хранится в памяти процесса: при нескольких воркерах/репликах он считается отдельно в каждом.
- Задачи (`problems`) общие для всех пользователей; чужие метаданные не перезаписываются, но название задачи, впервые добавленной одним пользователем, увидит и другой, кто добавит ту же `(platform, external_id)`.

## Качество

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app && uv run pytest --cov=app
cd frontend && npm run lint && npm run format:check && npm run typecheck && npm test
```

CI (`.github/workflows/ci.yml`) на каждый push/PR: backend (Postgres 16, ruff, mypy, alembic, pytest с порогом покрытия 85%), frontend (eslint, prettier, tsc, vitest, build) и сборка обоих Docker-образов.

## Дорожная карта

- FSRS вместо SM-2 (интерфейс `Scheduler` уже готов).
- Импорт из LeetCode.
- PWA и push-уведомления о повторениях.
- Отзыв refresh-токенов, общий (Redis) rate limit.

## Лицензия

MIT — см. [LICENSE](LICENSE).
