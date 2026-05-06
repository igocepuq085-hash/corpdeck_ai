# AI Brand Deck Studio

MVP-сервис для генерации корпоративных HTML-презентаций из PPTX/DOCX/PDF.

Текущий production-контур после surgical cleanup:

1. загрузка файла;
2. извлечение текста;
3. анализ документа через OpenAI или локальный fallback;
4. формирование `slide_plan` и `deck_plan`;
5. финальная проверка качества;
6. просмотр HTML-презентации в браузере;
7. печать/PDF через браузер.

Генерация изображений отключена. Визуалы берутся только из локальной библиотеки `static/assets/`.

## Локальный запуск

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Проверки:

- `http://127.0.0.1:8000/health`
- загрузить файл на главной странице;
- проверить preview diagnostics;
- открыть `/deck/{project_id}`;
- открыть `/deck/{project_id}?debug=1`;
- проверить печать/PDF через браузер.

## Railway

Start command:

```text
uvicorn main:app --host 0.0.0.0 --port $PORT
```

Переменные окружения:

```text
OPENAI_API_KEY=
OPENAI_TEXT_MODEL=gpt-5.5
```

Если `OPENAI_API_KEY` не задан, сервис работает в локальном fallback-режиме.

## Логотип

Основной логотип:

```text
static/brand/logo.png
```

Файл должен быть в репозитории.

## Локальные фоны

Положите фоны строго по этим путям:

```text
static/assets/visuals/background/bg_cover_light.webp
static/assets/visuals/background/bg_content_light.webp
static/assets/visuals/background/bg_data_light.webp
static/assets/visuals/background/bg_roadmap_light.webp
```

Требования к фонам:

- формат 16:9, лучше 1600x900 или 3200x1800;
- без текста, цифр, логотипов и водяных знаков;
- светлая premium-тема: белый, ледяной голубой, фирменный синий;
- без сетки на весь фон;
- спокойные зоны под HTML-текст и карточки.

Рекомендуемый смысл:

- `bg_cover_light.webp` — титульный светлый фон с мягкой hero-зоной справа;
- `bg_content_light.webp` — универсальный фон для смысловых слайдов;
- `bg_data_light.webp` — спокойный фон для KPI/таблиц/графиков;
- `bg_roadmap_light.webp` — фон с мягким ощущением маршрута/движения без подписей.

## Локальные иконки

Положите PNG-иконки строго по этим путям:

```text
static/assets/visuals/hero/hero_cover_transport_light.png
static/assets/visuals/hero/hero_digital_control_light.png
static/assets/visuals/hero/hero_safety_light.png

static/assets/visuals/icons/icon_transport_locomotive.png
static/assets/visuals/icons/icon_transport_route.png
static/assets/visuals/icons/icon_digital_dashboard.png
static/assets/visuals/icons/icon_safety_shield.png
static/assets/visuals/icons/icon_analytics_chart.png
static/assets/visuals/icons/icon_finance_growth.png
static/assets/visuals/icons/icon_education_training.png
static/assets/visuals/icons/icon_production_hub.png
static/assets/visuals/icons/icon_strategy_roadmap.png
static/assets/visuals/icons/icon_protocol_document.png
```

Требования к иконкам:

- PNG с прозрачным фоном;
- без шахматного/checkerboard-фона;
- без текста, цифр, KPI, дат и подписей;
- 3D/premium или чистый линейный corporate style;
- бело-голубая палитра с синими акцентами;
- объект один, не перегруженная сцена.

Рекомендуемые размеры:

- hero: 900x900 или 1200x900;
- icons: 512x512 или 768x768.

## Библиотека визуалов

Каталог ассетов:

```text
static/assets/visual_library.json
```

Код выбирает только ассеты:

- `enabled=true`;
- без текста и чисел;
- подходящие по `semantic_category`;
- подходящие по `visual_role`;
- подходящие под `layout_type`.

Если файл еще не положен, сервис не падает и использует CSS fallback.

## Ключевая архитектура

- `document_context` — что сервис понял про документ;
- `verified_facts` — найденные числа, даты, организации, локации, термины;
- `slide_plan` — роли слайдов, `layout_type`, `visual_intent`, `data_blocks`;
- `deck_plan` — финальная структура презентации;
- `asset_library` — локальная библиотека безопасных фонов и иконок;
- `final_deck_quality_gate` — проверка текста, данных, визуалов и render-ready состояния.

## Что намеренно отключено

В MVP не используются:

- OpenAI Image API;
- массовая генерация PNG;
- старые decorative layers;
- внешние JS-графики;
- серверный экспорт PPTX/PDF;
- база данных, Celery/Redis, редактор слайдов.

Это сделано специально: сначала стабильная красивая HTML-презентация, потом расширения.

## KPI, таблицы и графики

AI не рисует графики и не придумывает показатели. Он только извлекает данные из документа и возвращает их в JSON:

- `kpis` — отдельные ключевые показатели;
- `charts` — данные для графиков;
- `tables` — компактные таблицы.

Для MVP разрешены графики:

- `bar` — сравнение категорий;
- `line` — динамика минимум из 3 точек;
- `donut` — структура частей одного целого;
- `timeline` — зарезервирован, в текущем MVP дорожные карты рендерятся через `steps`.

Ограничения:

- максимум 1 график на слайд;
- максимум 1 таблица на слайд;
- если есть график, таблица на этом же слайде не используется;
- таблица: максимум 5 колонок и 6 строк;
- KPI: максимум 4 карточки на слайд.

Локальный JS-хук для графиков находится в:

```text
static/js/deck.js
```

Если позже нужен Chart.js, положите локальный файл сюда:

```text
static/vendor/chart.umd.js
```

CDN не используется. Если Chart.js отсутствует, презентация показывает HTML/CSS fallback-график.
