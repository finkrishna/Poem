FROM python:3.12-slim
RUN useradd -m -u 1000 user && pip install --no-cache-dir huggingface_hub
WORKDIR /app
COPY --chown=user:user factory_server.py library_store.py factory.js reader.js reader.css index.html README.md ./
COPY --chown=user:user bhaja-govindam.html bhaja-govindam.json shravan-masi.html shravan-masi-spoken.html ./
COPY --chown=user:user audio ./audio
ENV HOST=0.0.0.0
ENV PORT=7860
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/user
USER user
EXPOSE 7860
CMD ["python", "factory_server.py"]
