# 📚 Документация API — Мониторинг конкурентов

AI-ассистент для анализа конкурентной среды в нише **HR / карьера / EdTech**: разбор текстов, визуальных материалов и страниц сайтов с единой структурой отчёта по тексту и парсингу URL.

## Содержание

1. [Структура проекта](#структура-проекта)
2. [Технологии](#технологии)
3. [Описание API](#описание-api)
4. [Модели данных](#модели-данных)
5. [Примеры запросов](#примеры-запросов)
6. [Текст, изображения и парсинг](#текст-изображения-и-парсинг)
7. [Коды ошибок](#коды-ошибок)
8. [Конфигурация](#конфигурация)
9. [Безопасность](#безопасность)

---

## Структура проекта

```
competitor-monitor/
├── backend/
│   ├── main.py                 # FastAPI, эндпоинты
│   ├── config.py
│   ├── models/schemas.py     # Pydantic v2
│   └── services/
│       ├── openai_service.py   # ProxyAPI / OpenAI-compatible LLM
│       ├── parser_service.py   # Selenium + Chrome
│       └── history_service.py
├── frontend/                   # Веб UI (HTML/CSS/JS), раздаётся с корня и /static
├── desktop/                    # PyQt6 + QWebEngineView (оболочка над тем же UI)
├── data/                       # Примеры материалов для ручных тестов (опционально)
├── screenshots/                # Скриншоты для документации / портфолио (опционально)
├── run.py                      # Запуск Uvicorn
├── requirements.txt
├── .env.example                # Шаблон переменных окружения
├── history.json                # История запросов (создаётся автоматически)
├── README.md
└── docs.md                     # Этот файл
```

---

## Технологии

| Компонент | Стек |
|-----------|------|
| API | **FastAPI**, **Pydantic v2** |
| LLM | **ProxyAPI** (OpenAI-compatible HTTPS API), модели задаются в конфигурации |
| Парсинг страниц | **Selenium** + **Google Chrome** (видимый браузер, не headless по умолчанию), скриншот и видимый текст |
| Веб-клиент | HTML, CSS, JavaScript |
| Desktop | **PyQt6**, **QWebEngineView** |

Разбор страниц для `/parse_demo` выполняется через браузер (DOM); это не типичный «скрейпинг через BeautifulSoup». Зависимости вроде `httpx` могут использоваться транзитивно клиентом OpenAI SDK и не задают основную логику парсинга.

---

## Описание API

### Базовый URL

```
http://localhost:8000
```

Порт по умолчанию совпадает с `API_PORT` в конфигурации (часто `8000`).

### Эндпоинты

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/` | Главная страница веб-интерфейса |
| GET | `/static/...` | Статические файлы фронтенда |
| POST | `/analyze_text` | Анализ текста конкурента (ниша HR / EdTech) |
| POST | `/analyze_image` | Анализ изображения (визуальный разбор) |
| POST | `/parse_demo` | Парсинг сайта (Selenium) + LLM-анализ (`CompetitorAnalysis`) |
| POST | `/parse/demo` | То же, что `/parse_demo` (алиас в коде) |
| GET | `/history` | История последних запросов |
| DELETE | `/history` | Очистка истории |
| GET | `/health` | Проверка работоспособности (используется desktop и мониторингом) |
| POST | `/export_pdf` | Экспорт анализа в PDF (нужен TTF с кириллицей, см. раздел «Конфигурация») |
| GET | `/docs` | Swagger UI |
| GET | `/redoc` | ReDoc |

---

## Модели данных

Схемы задаются в `backend/models/schemas.py` (Pydantic v2).

### Запросы

**TextAnalysisRequest**

| Поле | Тип | Описание |
|------|-----|----------|
| `text` | `string` | Минимум **10** символов |

**ParseDemoRequest**

| Поле | Тип | Описание |
|------|-----|----------|
| `url` | `string` | URL сайта (протокол можно опустить на клиенте — сервер нормализует контекст парсера) |

### Ответы

**CompetitorAnalysis** — единый отчёт для **`/analyze_text`** и поля **`ParsedContent.analysis`** после успешного **`/parse_demo`**.

| Поле | Тип | Описание |
|------|-----|----------|
| `strengths` | `string[]` | Сильные стороны |
| `weaknesses` | `string[]` | Слабые стороны |
| `unique_offers` | `string[]` | Уникальные торговые предложения / УТП |
| `recommendations` | `string[]` | Рекомендации |
| `summary` | `string` | Краткое резюме |
| `design_score` | `int` | Оценка дизайна и подачи контента, **0–10** |
| `ux_score` | `int` | UX для работодателей и кандидатов, **0–10** |
| `hr_relevance_score` | `int` | Релевантность HR-процессам и найму, **0–10** |
| `target_audience` | `string` | Целевая аудитория (формулировка модели) |
| `automation_potential` | `string[]` | Идеи автоматизации HR / рекрутинга |

**ImageAnalysis** — отдельная модель для **`/analyze_image`** (визуальный анализ, без полей `design_score` / `hr_relevance_score`).

| Поле | Тип | Описание |
|------|-----|----------|
| `description` | `string` | Описание изображения |
| `marketing_insights` | `string[]` | Маркетинговые инсайты |
| `visual_style_score` | `int` | Оценка визуального стиля **0–10** |
| `visual_style_analysis` | `string` | Разбор стиля |
| `recommendations` | `string[]` | Рекомендации |

**ParsedContent** — тело поля `data` при успешном **`ParseDemoResponse`**.

| Поле | Тип | Описание |
|------|-----|----------|
| `url` | `string` | Запрошенный URL |
| `title` | `string \| null` | Заголовок страницы (через браузер) |
| `h1` | `string \| null` | Первый логичный H1 |
| `first_paragraph` | `string \| null` | Первый значимый абзац (если извлечён) |
| `page_text_excerpt` | `string \| null` | Укороченный фрагмент **видимого текста** страницы для отображения |
| `analysis` | `CompetitorAnalysis \| null` | Результат LLM по скриншоту и/или тексту страницы |
| `error` | `string \| null` | Ошибка на уровне записи (если используется) |

Парсинг на стороне сервиса: **Selenium + Chrome** — загрузка страницы, **скриншот**, извлечение **видимого текста**; при успехе в LLM уходят скриншот (если есть) и контекст URL/заголовков/текста. Если скриншота нет, но текста достаточно, возможен откат к текстовому анализу страницы.

**TextAnalysisResponse**

| Поле | Тип |
|------|-----|
| `success` | `boolean` |
| `analysis` | `CompetitorAnalysis \| null` |
| `error` | `string \| null` |

**ImageAnalysisResponse**

| Поле | Тип |
|------|-----|
| `success` | `boolean` |
| `analysis` | `ImageAnalysis \| null` |
| `error` | `string \| null` |

**ParseDemoResponse**

| Поле | Тип |
|------|-----|
| `success` | `boolean` |
| `data` | `ParsedContent \| null` |
| `error` | `string \| null` |

**HistoryItem**

| Поле | Тип |
|------|-----|
| `id` | `string` (UUID) |
| `timestamp` | `datetime` (ISO) |
| `request_type` | `"text"` \| `"image"` \| `"parse"` |
| `request_summary` | `string` |
| `response_summary` | `string` |

**HistoryResponse**

| Поле | Тип |
|------|-----|
| `items` | `HistoryItem[]` |
| `total` | `int` |

---

## Примеры запросов

### 1. Анализ текста (`POST /analyze_text`)

**Запрос** (пример про карьерный портал и кандидатов):

```bash
curl -X POST "http://localhost:8000/analyze_text" \
  -H "Content-Type: application/json" \
  -d "{\"text\": \"HeadHunter — ведущий сервис по поиску работы и подбору персонала в России. Мы помогаем соискателям находить вакансии по профессии и региону, а работодателям — публиковать заявки и отбирать кандидатов с помощью фильтров и откликов. Есть разделы про карьерное развитие, зарплатные ожидания и обучение: курсы для перехода в IT и digital от партнёрских школ. Для HR мы предлагаем инструменты массового найма и интеграции с ATS.\"}"
```

**Ответ** (структура; значения полей LLM могут отличаться):

```json
{
  "success": true,
  "analysis": {
    "strengths": [
      "Чёткое позиционирование как карьерного и HR-хаба",
      "Упоминание ценности для соискателей и работодателей",
      "Связка с обучением и развитием (EdTech-партнёры)"
    ],
    "weaknesses": [
      "Мало конкретных цифр по охвату в этом фрагменте",
      "Нет акцента на отличия от прямых конкурентов"
    ],
    "unique_offers": [
      "Связка поиска работы + обучение и переход в IT",
      "Инструменты для массового найма и ATS"
    ],
    "recommendations": [
      "Добавить короткий блок доверия (метрики, кейсы работодателей)",
      "Подчеркнуть уникальные HR-продукты относительно рынка"
    ],
    "summary": "Текст описывает экосистему поиска работы и поддержки HR с элементами EdTech; для конкурентного сравнения полезно усилить метрики и дифференциацию.",
    "design_score": 7,
    "ux_score": 8,
    "hr_relevance_score": 9,
    "target_audience": "Соискатели, рекрутеры и HR-директора в РФ; интерес к дополнительному обучению",
    "automation_potential": [
      "Авто-скринг резюме под профоргу ML",
      "Напоминания кандидатам по воронке откликов"
    ]
  },
  "error": null
}
```

### 2. Анализ изображения (`POST /analyze_image`)

**Запрос:**

```bash
curl -X POST "http://localhost:8000/analyze_image" \
  -F "file=@banner.jpg"
```

**Ответ:**

```json
{
  "success": true,
  "analysis": {
    "description": "Баннер EdTech: крупный слоган про профессию, фото преподавателя, блок с перечнем модулей курса.",
    "marketing_insights": [
      "Акцент на результате и смене карьеры",
      "Визуальная опора на «человека» повышает доверие",
      "Модульная структура снижает страх длинного коммита"
    ],
    "visual_style_score": 8,
    "visual_style_analysis": "Сдержанная палитра, хорошая иерархия заголовок → подзаголовок → CTA; можно усилить контраст кнопки.",
    "recommendations": [
      "Добавить социальное доказательство (количество выпускников)",
      "Проверить читаемость мелкого текста на мобильном кропе"
    ]
  },
  "error": null
}
```

### 3. Парсинг сайта (`POST /parse_demo`)

Загрузка страницы в **Chrome (Selenium)**, снимок экрана и видимый текст → анализ через LLM в формате **`CompetitorAnalysis`**.

**Запрос** (пример URL онлайн-школы):

```bash
curl -X POST "http://localhost:8000/parse_demo" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"https://skillbox.ru\"}"
```

Альтернативно тот же обработчик: `POST /parse/demo`.

**Ответ** (структура):

```json
{
  "success": true,
  "data": {
    "url": "https://skillbox.ru",
    "title": "Skillbox — онлайн-университет ...",
    "h1": "...",
    "first_paragraph": "...",
    "page_text_excerpt": "Фрагмент видимого текста главной страницы (обрезан для UI)...",
    "analysis": {
      "strengths": ["..."],
      "weaknesses": ["..."],
      "unique_offers": ["..."],
      "recommendations": ["..."],
      "summary": "...",
      "design_score": 8,
      "ux_score": 7,
      "hr_relevance_score": 6,
      "target_audience": "Кандидаты на курсы по digital и дизайну, смена профессии",
      "automation_potential": ["Чат-бот записи на курс", "..."]
    },
    "error": null
  },
  "error": null
}
```

Допустимый пример URL в документации: `https://zerocoder.ru` — формат ответа тот же.

При ошибке парсинга или невозможности получить данные для анализа:

```json
{
  "success": false,
  "data": null,
  "error": "Текст сообщения об ошибке"
}
```

### 4. История (`GET /history`)

```bash
curl -X GET "http://localhost:8000/history"
```

**Ответ:**

```json
{
  "items": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "timestamp": "2025-02-10T10:30:00",
      "request_type": "parse",
      "request_summary": "URL: https://skillbox.ru",
      "response_summary": "Краткое резюме из analysis.summary..."
    }
  ],
  "total": 1
}
```

### 5. Очистка истории (`DELETE /history`)

```bash
curl -X DELETE "http://localhost:8000/history"
```

**Ответ:**

```json
{
  "success": true,
  "message": "История очищена"
}
```

### 6. Проверка работоспособности (`GET /health`)

```bash
curl -X GET "http://localhost:8000/health"
```

**Ответ:**

```json
{
  "status": "healthy",
  "service": "Competitor Monitor",
  "version": "1.0.0"
}
```

---

## Текст, изображения и парсинг

### Текст

- Назначение: описания вакансий, лендинги HR/EdTech, рекламные тексты конкурентов.
- **Минимальная длина:** 10 символов (`TextAnalysisRequest`).
- Результат: **`CompetitorAnalysis`** (HR/EdTech поля + списки и `summary`).

### Изображения

- Форматы тела запроса (проверяются на сервере): `image/jpeg`, `image/png`, `image/gif`, `image/webp`.
- Результат: **`ImageAnalysis`** (описание, инсайты, визуальная оценка, рекомендации).

### Парсинг сайтов

- Реализация: **Selenium + Chrome**, стратегия загрузки `eager`, таймаут загрузки из настроек (`parser_timeout` в конфиге).
- Из страницы извлекаются заголовки/абзац и **видимый текст**; сохраняется **скриншот** для мультимодального запроса к LLM.
- Итог для клиента: **`ParsedContent`** с **`page_text_excerpt`** и **`analysis: CompetitorAnalysis`** при успехе.

---

## Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успешный запрос |
| 400 | Некорректный запрос (например, неподдерживаемый MIME изображения) |
| 422 | Ошибка валидации тела запроса (Pydantic) |
| 500 | Внутренняя ошибка сервера (реже; часть сценариев возвращает `success: false` в JSON без 500) |

---

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|------------|----------|--------------|
| `PROXY_API_KEY` | Ключ доступа к ProxyAPI (обязателен для старта приложения) | — |
| `OPENAI_MODEL` | Модель для текста и JSON-анализа | `gpt-4o-mini` |
| `OPENAI_VISION_MODEL` | Модель для изображений и скриншотов сайта | `gpt-4o-mini` |
| `API_HOST` | Хост HTTP-сервера | `0.0.0.0` |
| `API_PORT` | Порт HTTP-сервера | `8000` |

Шаблон см. в файле `.env.example` в корне проекта.

### Экспорт PDF

Для `POST /export_pdf` ReportLab подключает TTF с кириллицей: сначала ищутся файлы в `backend/assets/fonts/`, при отсутствии — системные `arial.ttf` и `arialbd.ttf` в `%WINDIR%\Fonts` (Windows). Если ни один подходящий шрифт не найден, API возвращает **503** с текстом `PDF font with Cyrillic support not found`. Файлы шрифтов из системы в Git не коммитятся — см. `backend/assets/fonts/.gitkeep` и `README.md`.

Тело запроса `ExportPdfRequest`: `pdf_export_kind` можно не указывать — тогда подставляется `image` при `kind=image`, при `kind=competitor` и непустом `site_host` — `site`, иначе `text`. Поле `source_text` опционально и не участвует в обязательной проверке; пустые строки приводятся к отсутствию значения. Имя файла в `Content-Disposition`: `analysis_text.pdf`, `analysis_site_<host>.pdf`, `analysis_image.pdf` или `analysis_report.pdf`, если хост пуст. Раздел «Исходный текст» в PDF только при режиме `text` и непустом `source_text`.

### ProxyAPI

Проект рассчитан на [ProxyAPI](https://proxyapi.ru/) — OpenAI-совместимый API. Подробности — в официальной документации провайдера.

### История

- Лимит записей задаётся в конфигурации (`max_history_items`, по умолчанию **10**).
- Файл: путь из настройки `history_file` (часто **`history.json`** в корне проекта).

---

## Безопасность

- Не храните ключи API в репозитории; используйте переменные окружения и локальный `.env` (файл должен быть в `.gitignore`).
- В продакшене включайте HTTPS и ограничивайте CORS конкретными доменами вместо `*` при необходимости.
