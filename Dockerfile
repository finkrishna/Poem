FROM python:3.12-slim
WORKDIR /app
COPY . .
ENV HOST=0.0.0.0
ENV PORT=7860
ENV PYTHONUNBUFFERED=1
EXPOSE 7860
CMD ["python", "factory_server.py"]
