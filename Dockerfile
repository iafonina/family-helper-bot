FROM python:3.12-slim

WORKDIR /app

# Устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
COPY . .

# Создаём директорию для логов
RUN mkdir -p logs

# Порт для health check (Koyeb проверяет здоровье приложения)
EXPOSE 8000

# Запускаем бота
CMD ["python", "bot.py"]
