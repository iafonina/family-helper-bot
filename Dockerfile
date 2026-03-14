FROM python:3.12-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY . .

# Создаём директорию для логов
RUN mkdir -p logs

# Запускаем бота
CMD ["python", "bot.py"]
