# ── Stage 1: builder — instala dependências ────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY app/requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: runtime — imagem final mínima ─────────────────────────────────
FROM python:3.11-slim AS runtime

# Usuário não-root para segurança
RUN groupadd -r appgroup \
 && useradd -r -g appgroup -d /app -s /sbin/nologin appuser

WORKDIR /app

# Dependências do stage builder
COPY --from=builder /install /usr/local

# Código da aplicação
COPY app/ .

# Entrypoint para inicializar o banco antes de subir
COPY docker-entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh \
 && chown -R appuser:appgroup /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/health')" \
  || exit 1

ENTRYPOINT ["entrypoint.sh"]

# Dev: python run.py | Staging/Prod: gunicorn (substituído pelo compose)
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "run:app"]
