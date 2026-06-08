# Automatic Compiler Options Selector

Веб-приложение для подбора оптимальной комбинации флагов компилятора  
на основе:
- теста Манна–Уитни
- многокритериального Парето-анализа

Интерфейс реализован с использованием Streamlit.

---

## Требования

Для запуска необходимы:
- Docker
- Docker Compose

Python и библиотеки устанавливать вручную не требуется.

---

## Запуск приложения (рекомендуемый способ)

1. Клонируйте репозиторий:
git clone <URL_РЕПОЗИТОРИЯ>
cd Automatic_compiler_options_selector

2. Запустите приложение:
docker-compose up

3. Откройте браузер:
http://localhost:8501

Запуск без Docker
myenv\Scripts\activate
streamlit run Information.py


Архитектура проекта

Automatic_compiler_options_selector/
├── app.py                          # Главный файл приложения
├── requirements.txt                # Зависимости Python
├── docker-compose.yaml            # Docker конфигурация
├── README.md                      # Документация
├── db/
│   └── database.py               # Работа с базой данных
├── backend/
│   ├── analysis.py               # Логика анализа (Манн-Уитни)
│   └── pareto.py                # Парето-оптимизация
└── pages/
    ├── analitics.py             # Страница аналитики
    ├── compiler_flags.py        # Страница управления флагами
    └── experiments_results.py   # Страница результатов экспериментов
