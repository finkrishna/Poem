FROM python:3.12-slim
RUN useradd -m -u 1000 user
WORKDIR /app
COPY --chown=user:user . .
ENV HOST=0.0.0.0
ENV PORT=7860
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/user
USER user
EXPOSE 7860
CMD ["python", "factory_server.py"]
