# topicsbot

AWS Lambdas для сбора/обработки новостей в Telegram-чате

Данные сохраняются в AWS DynamoDB

### Обязательные параметры для **topicsbot**

DYNAMO_TABLE - таблица для сохранения данных

TELEGRAM_TOKEN - API-токен от бота из BotFather

NEWS_CHANNEL - ID чата/группы на сообщения которой будет реагировать

GCP_JSON - JSON-строка с данными для подключения к GCP

GCP_SPREADSHEET - имя spreadsheet, к которому у бота есть доступ на редактирование

GCP_WORKSHEET - лист в spreadsheet

GCP_START_ROW - начальная строка для вставки

GCP_DATE_COLUMN - столбец для дат

GCP_AUTHOR_COLUMN - столбец для автора

GCP_NEWS_COLUMN - столбец для текста новости

LAMBDA_DIGEST - AWS ARN, ссылающийся на Lambda digest

### Обязательные параметры для **digest**

DYNAMO_TABLE - таблица для чтения данных

GITHUB_TOKEN - GitHub API token для доступа к GitHub

GITHUB_REPO - репозиторий для сохранения дайджеста

GITHUB_BRANCH - branch для сохранения дайджеста
