FROM python:3.10-slim

# Устанавливаем рабочую папку
WORKDIR /app

# Копируем список библиотек и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь остальной код (app.py)
COPY . .

# Запускаем бота
CMD ["python", "app.py"]
