# Pipeline DevSecOps — CI/CD

Documentação detalhada do pipeline de integração e entrega contínua do projeto
Task Manager, definido em [`.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml).

---

## Índice

1. [Visão geral](#1-visão-geral)
2. [Gatilhos de execução](#2-gatilhos-de-execução)
3. [Estratégia de branches](#3-estratégia-de-branches)
4. [Secrets e variáveis](#4-secrets-e-variáveis)
5. [Job 1 — CI: Testes & Análise Estática (SAST)](#5-job-1--ci-testes--análise-estática-sast)
6. [Job 2 — Build: Docker Image + Docker Slim](#6-job-2--build-docker-image--docker-slim)
7. [Job 3 — Deploy Staging + DAST](#7-job-3--deploy-staging--dast)
8. [Job 4 — Deploy Produção (aprovação manual)](#8-job-4--deploy-produção-aprovação-manual)
9. [Job 5 — Monitoramento pós-deploy](#9-job-5--monitoramento-pós-deploy)
10. [Diagrama de fluxo completo](#10-diagrama-de-fluxo-completo)
11. [Arquivos de configuração relacionados](#11-arquivos-de-configuração-relacionados)
12. [Referência rápida de comandos](#12-referência-rápida-de-comandos)

---

## 1. Visão geral

O pipeline segue o modelo **DevSecOps**, integrando segurança em cada fase do
ciclo de vida do software — desde a análise estática do código (SAST) até testes
dinâmicos contra a aplicação em execução (DAST).

O fluxo completo possui **5 jobs** que se encadeiam em sequência:

```
CI (testes + SAST)  →  Build (imagem Docker)  →  Deploy  →  Monitoramento
```

Cada job só executa se o anterior foi bem-sucedido (`needs`), garantindo que
código com falhas nunca chegue a produção.

---

## 2. Gatilhos de execução

O pipeline é disparado por dois tipos de evento do GitHub:

| Evento | Branches | Quando executa |
|--------|----------|----------------|
| `push` | `dev`, `staging`, `main` | A cada commit pushado para uma dessas branches |
| `pull_request` | `staging`, `main` | Ao abrir ou atualizar um PR contra essas branches |

**Comportamento por evento:**

- **`push`**: executa o pipeline completo (CI → Build → Deploy conforme a branch).
- **`pull_request`**: executa apenas o job de **CI** (testes + SAST) como validação
  do PR. Não faz build nem deploy — o push da imagem Docker é condicional
  (`push: ${{ github.event_name == 'push' }}`).

```yaml
on:
  push:
    branches: [dev, staging, main]
  pull_request:
    branches: [staging, main]
```

---

## 3. Estratégia de branches

O projeto adota um fluxo de **três branches fixas**, cada uma mapeada a um ambiente:

| Branch | Ambiente | Tag Docker | Deploy automático? | Observações |
|--------|----------|------------|---------------------|-------------|
| `dev` | Desenvolvimento | `:dev` | ❌ Não | Apenas CI + Build. Sem deploy. |
| `staging` | Homologação | `:staging` | ✅ Sim | Deploy automático + DAST (ZAP). Porta 5001. |
| `main` | Produção | `:latest` | ⏸️ Com aprovação | Requer aprovação manual de um revisor. Porta 5000. |

A tag da imagem Docker é determinada dinamicamente com base na branch:

```bash
case "$GITHUB_REF_NAME" in
  main)    tag=latest  ;;
  staging) tag=staging ;;
  *)       tag=dev     ;;
esac
```

Além da tag por ambiente, cada build também recebe uma tag com o SHA do commit
(ex: `:staging-a1b2c3d`) para rastreabilidade e possibilidade de rollback.

---

## 4. Secrets e variáveis

Os seguintes secrets devem ser configurados em **Settings › Secrets and variables › Actions**:

| Secret | Descrição | Usado em |
|--------|-----------|----------|
| `DOCKERHUB_USERNAME` | Usuário do Docker Hub | Build (login + push) |
| `DOCKERHUB_TOKEN` | Token de acesso (não usar senha!) | Build (login) |
| `SECRET_KEY` | Chave secreta do Flask (sessões/CSRF) | Deploy Staging e Prod |
| `DATABASE_URI` | URI do banco de dados | Deploy Prod |
| `STAGING_HOST` | IP ou DNS do servidor de staging | Deploy Staging + DAST |
| `STAGING_SSH_KEY` | Chave SSH privada para acesso ao staging | Deploy Staging |
| `PROD_HOST` | IP ou DNS do servidor de produção | Deploy Prod + Monitoramento |
| `PROD_SSH_KEY` | Chave SSH privada para acesso à produção | Deploy Prod + Monitoramento |

**Variável de ambiente global do pipeline:**

```yaml
env:
  IMAGE_NAME: ${{ secrets.DOCKERHUB_USERNAME }}/task-manager
```

Esta variável monta o nome completo da imagem Docker (ex: `usuario/task-manager`)
e é referenciada em todos os jobs subsequentes.

---

## 5. Job 1 — CI: Testes & Análise Estática (SAST)

**Nome:** `ci`
**Executa em:** `ubuntu-latest`
**Condição:** roda em **todas** as branches e eventos (push e PR)

Este é o job mais importante do pipeline — valida que o código está funcional e
seguro antes de qualquer build ou deploy.

### 5.1. Etapas do job

#### a) Setup do ambiente

```yaml
- uses: actions/checkout@v4
- uses: actions/setup-python@v5
  with:
    python-version: "3.11"
    cache: pip
- run: pip install -r app/requirements-dev.txt
```

- Faz checkout do código
- Instala Python 3.11 com cache de pacotes pip (acelera execuções subsequentes)
- Instala todas as dependências, incluindo ferramentas de teste (`pytest`,
  `pytest-cov`, `bandit`)

#### b) Testes automatizados (pytest)

```bash
pytest tests/ -v \
  --cov=app/todo_project \
  --cov-report=xml:reports/coverage.xml \
  --cov-report=term-missing \
  --junitxml=reports/junit.xml
```

| Flag | Propósito |
|------|-----------|
| `-v` | Saída verbosa — mostra cada teste individualmente |
| `--cov=app/todo_project` | Mede cobertura de código do pacote principal |
| `--cov-report=xml` | Gera relatório XML (compatível com ferramentas como Codecov) |
| `--cov-report=term-missing` | Exibe no terminal quais linhas não foram cobertas |
| `--junitxml` | Gera relatório JUnit XML (compatível com GitHub Actions) |

O relatório é salvo como artefato `test-reports` e fica disponível para download
na interface do GitHub Actions, mesmo se o pipeline falhar (`if: always()`).

#### c) SAST — Bandit (análise estática de segurança do Python)

```bash
bandit -r app/ -f json -o reports/bandit-report.json -ll -ii || true
bandit -r app/ -f txt -ll -ii || true
```

O [Bandit](https://bandit.readthedocs.io/) é uma ferramenta de análise estática
de segurança específica para Python. Ele examina a AST (árvore sintática abstrata)
do código em busca de padrões inseguros.

| Flag | Significado |
|------|-------------|
| `-r app/` | Recursivo no diretório `app/` |
| `-f json` | Formato de saída JSON |
| `-ll` | Severidade mínima: **Medium** (ignora Low) |
| `-ii` | Confiança mínima: **Medium** (ignora Low) |
| `\|\| true` | Não falha o pipeline por findings — gera relatório |

O comando é executado **duas vezes**: uma para gerar o relatório JSON (artefato)
e outra em texto plano (exibido no log do pipeline).

**Exemplos de vulnerabilidades que o Bandit detecta:**
- Uso de `eval()` ou `exec()`
- Senhas hardcoded
- Uso inseguro de `subprocess`
- Algoritmos de hash fracos (MD5, SHA1)
- SQL injection

#### d) SAST — OWASP Dependency-Check

```yaml
- uses: dependency-check/Dependency-Check_Action@main
  with:
    project: "task-manager"
    path: "app/"
    format: "HTML"
    out: "reports/dependency-check"
    args: >
      --enableRetired
      --failOnCVSS 7
```

O [OWASP Dependency-Check](https://owasp.org/www-project-dependency-check/)
analisa as dependências do projeto (listadas em `requirements.txt`) e verifica
se possuem **CVEs** (Common Vulnerabilities and Exposures) conhecidas.

| Parâmetro | Significado |
|-----------|-------------|
| `--enableRetired` | Inclui componentes retirados/descontinuados na análise |
| `--failOnCVSS 7` | **Falha o pipeline** se alguma vulnerabilidade tiver CVSS ≥ 7.0 (HIGH) |

Isso garante que dependências com vulnerabilidades graves bloqueiem o pipeline
antes que o código chegue a qualquer ambiente.

---

## 6. Job 2 — Build: Docker Image + Docker Slim

**Nome:** `build`
**Executa em:** `ubuntu-latest`
**Depende de:** `ci` (só roda se CI passou)

### 6.1. Build da imagem Docker

```yaml
- uses: docker/build-push-action@v5
  with:
    context: .
    dockerfile: Dockerfile
    push: ${{ github.event_name == 'push' }}
    tags: |
      ${{ env.IMAGE_NAME }}:${{ steps.tag.outputs.tag }}
      ${{ env.IMAGE_NAME }}:${{ steps.tag.outputs.tag }}-${{ github.sha }}
    cache-from: type=gha
    cache-to: type=gha,mode=max
```

**Pontos relevantes:**

- **Push condicional**: só faz push para o Docker Hub em eventos `push` (não em PRs)
- **Duas tags por build**: uma genérica (`:dev`, `:staging`, `:latest`) e uma com
  o SHA do commit para rastreabilidade
- **Cache do GitHub Actions** (`type=gha`): reutiliza layers entre builds para
  acelerar o processo. O `mode=max` armazena todas as layers intermediárias.

O Dockerfile usa um build **multi-stage** com duas fases:

1. **`builder`**: instala dependências Python em `/install`
2. **`runtime`**: copia apenas os pacotes instalados e o código da aplicação,
   resultando numa imagem final menor

A imagem final executa como usuário `appuser` (não-root) e utiliza `gunicorn`
como servidor WSGI com 2 workers e timeout de 60 segundos.

### 6.2. Docker Slim (otimização)

```yaml
- name: Docker Slim — otimizar imagem
  if: github.event_name == 'push' && github.ref_name != 'dev'
```

O [Docker Slim (SlimToolkit)](https://slimtoolkit.org/) é executado **apenas para
staging e produção** (não para `dev`). Ele:

1. Executa a imagem base em um ambiente monitorado
2. Faz probe HTTP (`GET /health`) para identificar quais arquivos são realmente
   necessários em runtime
3. Gera uma imagem otimizada (tag `-slim`) removendo tudo que não foi acessado

**Benefícios:**
- Reduz drasticamente o tamanho da imagem (frequentemente 3-10x menor)
- Remove binários e bibliotecas desnecessários, reduzindo a **superfície de ataque**
- A imagem slim é publicada no Docker Hub com sufixo `-slim`

| Parâmetro | Significado |
|-----------|-------------|
| `--http-probe=true` | Ativa probe HTTP para detectar dependências de runtime |
| `--http-probe-cmd "GET /health"` | Rota usada pelo probe |
| `--continue-after 20` | Espera 20 segundos de execução antes de finalizar a análise |
| `--publish-port 5000` | Expõe a porta para o probe |

---

## 7. Job 3 — Deploy Staging + DAST

**Nome:** `deploy-staging`
**Executa em:** `ubuntu-latest`
**Depende de:** `build`
**Condição:** `github.ref_name == 'staging' && github.event_name == 'push'`

Este job só executa em pushes para a branch `staging`.

### 7.1. GitHub Environment

```yaml
environment:
  name: staging
  url: http://${{ secrets.STAGING_HOST }}:5001
```

O uso de [GitHub Environments](https://docs.github.com/en/actions/deployment/targeting-different-environments)
permite:
- Agrupar secrets por ambiente
- Configurar regras de proteção (ex: revisores obrigatórios)
- Visualizar o histórico de deploys por ambiente na interface do GitHub

### 7.2. Deploy via SSH

```yaml
- uses: appleboy/ssh-action@v1.0.3
  with:
    host: ${{ secrets.STAGING_HOST }}
    username: ubuntu
    key: ${{ secrets.STAGING_SSH_KEY }}
```

O deploy é feito via SSH no servidor de staging usando a action `appleboy/ssh-action`.
O script remoto:

1. Exporta variáveis de ambiente (`DOCKER_IMAGE`, `IMAGE_TAG`, `SECRET_KEY`, `DATABASE_URI`)
2. Faz `docker compose pull` para baixar a imagem mais recente do Docker Hub
3. Faz `docker compose up -d --remove-orphans` para atualizar o container
4. Utiliza o compose file `environments/staging/docker-compose.staging.yml`

O ambiente de staging roda na **porta 5001** (diferente da 5000 de produção)
para permitir coexistência no mesmo host, se necessário.

### 7.3. DAST — OWASP ZAP

Após o deploy e um período de espera de 25 segundos para inicialização, o pipeline
executa **dois tipos de scan** do OWASP ZAP contra a aplicação em execução:

#### a) ZAP Baseline Scan (rápido)

```yaml
- uses: zaproxy/action-baseline@v0.11.0
  with:
    target: "http://${{ secrets.STAGING_HOST }}:5001"
    rules_file_name: ".github/zap-rules.tsv"
    cmd_options: "-a -j"
    fail_action: false
```

O Baseline Scan é um scan **passivo e rápido** que:
- Faz spider (rastreamento) da aplicação
- Analisa headers, cookies e respostas HTTP
- Identifica problemas óbvios de segurança (headers faltando, cookies inseguros, etc.)
- Não tenta explorar vulnerabilidades ativamente

| Flag | Significado |
|------|-------------|
| `-a` | Inclui alertas alfa (experimentais) |
| `-j` | Usa o Ajax Spider além do spider tradicional |
| `fail_action: false` | Não quebra o pipeline — apenas gera relatório |

#### b) ZAP Full Scan (abrangente)

```yaml
- uses: zaproxy/action-full-scan@v0.10.0
  with:
    target: "http://${{ secrets.STAGING_HOST }}:5001"
    rules_file_name: ".github/zap-rules.tsv"
    fail_action: false
    cmd_options: "-a"
```

O Full Scan é mais abrangente e inclui testes **ativos**:
- SQL Injection
- Cross-Site Scripting (XSS)
- Path Traversal
- Remote File Inclusion
- E dezenas de outros ataques automatizados

#### c) Regras de supressão (`.github/zap-rules.tsv`)

O arquivo de regras suprime **falsos positivos conhecidos** que são inerentes ao
Flask e Bootstrap e não representam riscos reais:

| ID | Regra suprimida | Razão |
|----|-----------------|-------|
| 10015 | Incomplete Cache-control Header | Flask não define por padrão; não é risco para esta app |
| 10027 | Information Disclosure - Suspicious Comments | Comentários HTML do Bootstrap |
| 10096 | Timestamp Disclosure - Unix | Timestamps em headers/cookies do Flask |
| 90033 | Loosely Scoped Cookie | Comportamento padrão do Flask session cookie |

O relatório HTML do ZAP é salvo como artefato `zap-dast-report`.

---

## 8. Job 4 — Deploy Produção (aprovação manual)

**Nome:** `deploy-prod`
**Executa em:** `ubuntu-latest`
**Depende de:** `build`
**Condição:** `github.ref_name == 'main' && github.event_name == 'push'`

### 8.1. Aprovação manual

```yaml
environment:
  name: production    # configure "Required reviewers" neste Environment
```

Este é o mecanismo de **gate de aprovação manual**. Quando o job é acionado:

1. O pipeline fica no estado **"Waiting"** no GitHub Actions
2. Um revisor autorizado (configurado em Settings › Environments › production ›
   Required reviewers) recebe uma notificação
3. O revisor acessa **Actions › workflow run › Review deployments** e aprova ou rejeita
4. Somente após aprovação o deploy é executado

Isso garante que **nenhum código vai para produção sem revisão humana**.

### 8.2. Deploy e health check

O script de deploy é similar ao de staging, mas com diferenças importantes:

| Aspecto | Staging | Produção |
|---------|---------|----------|
| Compose file | `docker-compose.staging.yml` | `docker-compose.prod.yml` |
| Tag da imagem | `:staging` | `:latest` |
| Porta exposta | 5001 | 5000 |
| `restart` policy | `unless-stopped` | `always` |
| Limites de recursos | Sem limite | CPU 1.0, Memória 512MB |

**Health check pós-deploy:**

```bash
sleep 15
curl -sf http://localhost:5000/health \
  && echo "Health check OK" \
  || (echo "ERRO: health check falhou!" && exit 1)
```

Após o deploy, o script espera 15 segundos e verifica o endpoint `/health`.
Se a aplicação não responder com sucesso, o **job inteiro falha** (`exit 1`),
sinalizando problema imediato no deploy de produção.

---

## 9. Job 5 — Monitoramento pós-deploy

**Nome:** `monitoring`
**Executa em:** `ubuntu-latest`
**Depende de:** `deploy-prod`
**Condição:** `always() && github.ref_name == 'main'`

O uso de `always()` garante que este job execute **mesmo se o deploy falhou**,
permitindo diagnosticar problemas.

### 9.1. Health check externo (3 tentativas)

```bash
for i in 1 2 3; do
  HTTP=$(curl -s -o /dev/null -w "%{http_code}" \
    "http://${{ secrets.PROD_HOST }}:5000/health" || echo "000")
  echo "Tentativa $i → HTTP $HTTP"
  [ "$HTTP" = "200" ] && exit 0
  sleep 15
done
echo "ALERTA: aplicação não respondeu após deploy em produção!"
exit 1
```

Faz até **3 tentativas** de health check com intervalo de 15 segundos entre cada.
Isso acomoda o tempo de inicialização do container. Se nenhuma tentativa retornar
HTTP 200, o job falha com alerta.

### 9.2. Verificação de logs via SSH

O pipeline se conecta ao servidor de produção via SSH e coleta:

| Verificação | Comando | Propósito |
|-------------|---------|-----------|
| Últimas 50 linhas de log | `docker logs --tail=50` | Visão geral do estado da app |
| Erros e exceções | `grep -iE "error\|exception\|critical"` | Detectar erros pós-deploy |
| Falhas de autenticação | `grep "AUTH_FAILURE"` | Detectar possíveis ataques de brute-force |
| Violações de segurança | `grep "SECURITY_VIOLATION"` | Detectar tentativas de acesso não autorizado |

Esses logs são exibidos diretamente na interface do GitHub Actions, permitindo
diagnóstico rápido sem necessidade de acessar o servidor manualmente.

---

## 10. Diagrama de fluxo completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                     GitHub Actions — DevSecOps Pipeline             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  push/PR em dev, staging ou main                                    │
│          │                                                          │
│          ▼                                                          │
│  ┌──────────────────────────────────┐                               │
│  │  JOB 1: CI                      │                               │
│  │  ├─ pytest (testes + cobertura) │                               │
│  │  ├─ Bandit (SAST Python)        │                               │
│  │  └─ Dependency-Check (SAST CVE) │                               │
│  └──────────────┬───────────────────┘                               │
│                 │ ✅                                                 │
│                 ▼                                                    │
│  ┌──────────────────────────────────┐                               │
│  │  JOB 2: Build                   │                               │
│  │  ├─ Docker Build + Push         │                               │
│  │  └─ Docker Slim (staging/prod)  │                               │
│  └──────────────┬───────────────────┘                               │
│                 │ ✅                                                 │
│         ┌───────┴────────┐                                          │
│         │                │                                          │
│   branch=staging    branch=main                                     │
│         │                │                                          │
│         ▼                ▼                                          │
│  ┌─────────────┐  ┌──────────────┐                                 │
│  │ JOB 3:      │  │ JOB 4:       │                                 │
│  │ Deploy      │  │ Deploy Prod  │                                 │
│  │ Staging     │  │ (aprovação   │                                 │
│  │ + DAST ZAP  │  │  manual)     │                                 │
│  └─────────────┘  └──────┬───────┘                                 │
│                          │ ✅                                       │
│                          ▼                                          │
│                   ┌──────────────┐                                  │
│                   │ JOB 5:       │                                  │
│                   │ Monitoramento│                                  │
│                   │ pós-deploy   │                                  │
│                   └──────────────┘                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 11. Arquivos de configuração relacionados

| Arquivo | Propósito |
|---------|-----------|
| [`.github/workflows/ci-cd.yml`](../.github/workflows/ci-cd.yml) | Definição completa do pipeline |
| [`.github/zap-rules.tsv`](../.github/zap-rules.tsv) | Regras de supressão de falsos positivos do ZAP |
| [`Dockerfile`](../Dockerfile) | Build multi-stage da imagem Docker |
| [`docker-entrypoint.sh`](../docker-entrypoint.sh) | Script de inicialização do banco |
| [`environments/dev/docker-compose.dev.yml`](../environments/dev/docker-compose.dev.yml) | Compose para desenvolvimento local |
| [`environments/staging/docker-compose.staging.yml`](../environments/staging/docker-compose.staging.yml) | Compose para staging (porta 5001) |
| [`environments/prod/docker-compose.prod.yml`](../environments/prod/docker-compose.prod.yml) | Compose para produção (porta 5000, com limites de recursos) |
| [`app/requirements-dev.txt`](../app/requirements-dev.txt) | Dependências de desenvolvimento (pytest, bandit) |

---

## 12. Referência rápida de comandos

### Executar o pipeline localmente (simulação parcial)

```bash
# Testes unitários (equivale ao Job 1 - testes)
cd /mnt/c/Projetos/task-manager-devsecops
pip install -r app/requirements-dev.txt
pytest tests/ -v --cov=app/todo_project --cov-report=term-missing

# SAST — Bandit (equivale ao Job 1 - Bandit)
bandit -r app/ -ll -ii

# Build da imagem Docker (equivale ao Job 2)
docker build -t task-manager:dev .

# Deploy local dev (equivale ao Job 3/4 mas em ambiente local)
docker compose up --build -d

# Health check (equivale ao Job 5)
curl -sf http://localhost:5000/health
```

### Verificar status do pipeline no GitHub

1. Acesse o repositório no GitHub
2. Vá em **Actions** → selecione o workflow run desejado
3. Cada job mostra suas etapas expandíveis com logs em tempo real
4. Artefatos (relatórios de teste, Bandit, ZAP) ficam disponíveis para
   download ao final de cada run, na seção **Artifacts**
