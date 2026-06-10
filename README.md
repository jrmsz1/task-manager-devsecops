# Task Manager — DevSecOps Pipeline

Projeto baseado em [Task Manager using Flask](https://github.com/AdityaBagad/Task-Manager-using-Flask),
adaptado com pipeline CI/CD completo, separação por ambientes e práticas DevSecOps.

---

## Estrutura do projeto

```
task-manager-devsecops/
├── app/                              # Código Flask (baseado no repositório original)
│   ├── todo_project/
│   │   ├── __init__.py               # App factory + logging via syslog
│   │   ├── routes.py                 # Rotas com logs de segurança estruturados
│   │   ├── models.py                 # Modelos User e Task (idêntico ao original)
│   │   ├── forms.py                  # Formulários WTForms (idêntico ao original)
│   │   ├── templates/                # Templates HTML originais
│   │   └── static/                   # Bootstrap CSS/JS originais
│   ├── requirements.txt              # Dependências de produção
│   ├── requirements-dev.txt          # + pytest, bandit
│   └── run.py                        # Entry point Flask
│
├── tests/
│   └── test_app.py                   # Testes unitários e de integração (pytest)
│
├── environments/
│   ├── dev/docker-compose.dev.yml    # Porta 5000, hot-reload, sem SECRET_KEY
│   ├── staging/docker-compose.staging.yml  # Porta 5001, requer SECRET_KEY
│   └── prod/docker-compose.prod.yml  # Porta 5000, requer SECRET_KEY + DATABASE_URI
│
├── monitoring/
│   ├── fail2ban-config.conf          # Bloqueio de força bruta via syslog
│   ├── docker-compose.monitoring.yml # Grafana + Loki + Promtail
│   ├── promtail-config.yml           # Coleta logs dos containers + syslog
│   └── grafana-datasources.yml       # Datasource Loki no Grafana
│
├── .github/
│   ├── workflows/ci-cd.yml           # Pipeline GitHub Actions (5 jobs)
│   └── zap-rules.tsv                 # Regras OWASP ZAP
│
├── Dockerfile                        # Multi-stage, usuário não-root, gunicorn
├── docker-compose.yml                # Atalho rápido para dev local
└── docker-entrypoint.sh              # Inicializa banco antes de subir servidor
```

---

## Primeiro uso — passo a passo para iniciantes

Se é a primeira vez que você está configurando este projeto, siga os passos abaixo.

### 1. Pré-requisitos

Certifique-se de ter instalado:

| Ferramenta | Verificar instalação | Download |
|------------|---------------------|----------|
| **Git** | `git --version` | [git-scm.com](https://git-scm.com/downloads) |
| **Docker Desktop** | `docker --version` | [docker.com](https://www.docker.com/products/docker-desktop/) |
| **Python 3.11+** | `python --version` | [python.org](https://www.python.org/downloads/) |
| **Conta GitHub** | — | [github.com/signup](https://github.com/signup) |
| **Conta Docker Hub** | — | [hub.docker.com/signup](https://hub.docker.com/signup) |

### 2. Criar o repositório no GitHub

1. Acesse [github.com/new](https://github.com/new)
2. Nome do repositório: `task-manager-devsecops`
3. Visibilidade: **Public** (necessário para GitHub Actions gratuito)
4. **NÃO** marque "Initialize this repository with a README"
5. Clique em **Create repository**

### 3. Inicializar o Git e enviar o código

Abra o terminal na pasta do projeto e execute:

```bash
cd C:\Projetos\task-manager-devsecops

# Inicializar o repositório Git
git init
git add .
git commit -m "Etapa 1: aplicação Flask com requisitos DevSecOps"

# Criar a branch dev e conectar ao GitHub
git branch -M dev
git remote add origin https://github.com/SEU_USUARIO/task-manager-devsecops.git
git push -u origin dev
```

> **Nota:** Substitua `SEU_USUARIO` pelo seu nome de usuário no GitHub.

### 4. Configurar os Secrets no GitHub

O pipeline CI/CD precisa de secrets para funcionar. Configure-os em:

**Repositório → Settings → Secrets and variables → Actions → New repository secret**

Para rodar pelo menos o job de **CI** (testes + análise estática), você **não precisa de secrets** —
ele funciona sem nenhuma configuração. Os secrets são necessários apenas para build e deploy:

| Secret | Necessário para | Como obter |
|--------|----------------|------------|
| `DOCKERHUB_USERNAME` | Build (Job 2) | Seu usuário do [Docker Hub](https://hub.docker.com) |
| `DOCKERHUB_TOKEN` | Build (Job 2) | Docker Hub → Account Settings → [Security → New Access Token](https://hub.docker.com/settings/security) |
| `SECRET_KEY` | Deploy (Jobs 3-4) | Gere com: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DATABASE_URI` | Deploy Prod (Job 4) | Ex: `sqlite:///site.db` |
| `STAGING_HOST` | Deploy Staging (Job 3) | IP ou DNS do servidor de staging |
| `STAGING_SSH_KEY` | Deploy Staging (Job 3) | Chave SSH privada para acessar o servidor |
| `PROD_HOST` | Deploy Prod (Job 4) | IP ou DNS do servidor de produção |
| `PROD_SSH_KEY` | Deploy Prod (Job 4) | Chave SSH privada para acessar o servidor |

### 5. Verificar que o pipeline rodou

Após o `git push`:

1. Acesse `https://github.com/SEU_USUARIO/task-manager-devsecops/actions`
2. Você verá o workflow **"DevSecOps Pipeline"** em execução (ícone amarelo ⏳)
3. Quando terminar, ficará verde ✅ (sucesso) ou vermelho ❌ (falha)
4. Clique no workflow run para ver detalhes de cada job

### 6. Ver os artefatos gerados pelo pipeline

Os artefatos (relatórios de teste, análise de segurança) ficam disponíveis após cada execução:

1. Acesse **Actions** → clique no workflow run desejado
2. Role até o final da página → seção **Artifacts**
3. Clique no nome do artefato para baixar como `.zip`

| Artefato | Conteúdo | Gerado por |
|----------|----------|------------|
| `test-reports` | `coverage.xml` + `junit.xml` (cobertura e resultados dos testes) | pytest |
| `bandit-report` | `bandit-report.json` (vulnerabilidades encontradas no código) | Bandit (SAST) |
| `dependency-check-report` | Relatório HTML de CVEs nas dependências | OWASP Dependency-Check |
| `zap-dast-report` | `report_html.html` (vulnerabilidades na app em execução) | OWASP ZAP (DAST) |

> **Dica:** O artefato `test-reports` contém o arquivo `coverage.xml` que mostra
> quais linhas do código foram testadas e quais não foram.

---

## Desenvolvimento local

```bash
# Subir em modo desenvolvimento (hot-reload)
docker compose up --build

# Acessar: http://localhost:5000
```

Ou sem Docker:

```bash
pip install -r app/requirements-dev.txt
cd app
python run.py
```

---

## Ambientes

| Ambiente    | Branch    | Porta | Trigger no pipeline          | SECRET_KEY |
|-------------|-----------|-------|------------------------------|------------|
| Development | `dev`     | 5000  | CI + Build automático        | Não exige  |
| Staging     | `staging` | 5001  | CI + Build + Deploy + DAST   | Obrigatório|
| Production  | `main`    | 5000  | CI + Build + Aprovação manual| Obrigatório|

### Subir staging manualmente
```bash
export SECRET_KEY="chave-segura-aqui"
docker compose -f environments/staging/docker-compose.staging.yml up -d
```

### Subir produção manualmente
```bash
export SECRET_KEY="chave-segura-aqui"
export DATABASE_URI="sqlite:///site.db"
docker compose -f environments/prod/docker-compose.prod.yml up -d
```

---

## Rodar testes localmente

```bash
pip install -r app/requirements-dev.txt
pytest tests/ -v --cov=app/todo_project
```

---

## Análise de segurança local

```bash
# SAST — Bandit
bandit -r app/ -ll -ii

# DAST — OWASP ZAP (requer app rodando em localhost:5000)
docker run -t owasp/zap2docker-stable zap-baseline.py \
  -t http://host.docker.internal:5000 -r zap-report.html
```

---

## Pipeline CI/CD — GitHub Actions

O arquivo `.github/workflows/ci-cd.yml` executa 5 jobs em sequência:

```
push dev     ──► [ci] ──► [build:dev]
push staging ──► [ci] ──► [build:staging] ──► [deploy-staging + DAST]
push main    ──► [ci] ──► [build:latest]  ──► [deploy-prod (aprovação manual)] ──► [monitoring]
```

### Jobs

| Job | O que faz |
|-----|-----------|
| `ci` | pytest + cobertura + Bandit + OWASP Dependency-Check |
| `build` | Docker multi-stage + push Docker Hub + Docker Slim (staging/prod) |
| `deploy-staging` | SSH deploy + OWASP ZAP Baseline + Full Scan |
| `deploy-prod` | Aprovação manual (GitHub Environment) + SSH deploy + health check |
| `monitoring` | Health check externo + leitura de logs de segurança |

### Configurar aprovação manual em produção
1. Acesse **Settings → Environments → production**
2. Ative **Required reviewers** e adicione seu usuário
3. A cada push na `main`, o pipeline aguarda sua aprovação

---

## Monitoramento

```bash
# Subir Grafana + Loki + Promtail
docker compose -f monitoring/docker-compose.monitoring.yml up -d

# Acessar Grafana: http://localhost:3000
# Login: admin / admin
```

**Queries úteis no Loki (Explore):**
```
{container="task-manager-prod"} |= "AUTH_FAILURE"
{container="task-manager-prod"} |= "SECURITY_VIOLATION"
{job="syslog"} |= "task-manager"
```

---

## Eventos de log gerados pela aplicação

| Evento | Nível | Quando |
|--------|-------|--------|
| `AUTH_SUCCESS` | INFO | Login bem-sucedido |
| `AUTH_FAILURE` | WARNING | Usuário ou senha incorretos |
| `AUTH_LOGOUT` | INFO | Logout realizado |
| `USER_REGISTER` | INFO | Novo usuário cadastrado |
| `SECURITY_VIOLATION` | WARNING | Acesso não autorizado (403) |
| `TASK_CREATE` | INFO | Tarefa criada |
| `TASK_UPDATE` | INFO | Tarefa atualizada |
| `TASK_DELETE` | INFO | Tarefa removida |
| `PASSWORD_CHANGE` | INFO | Senha alterada com sucesso |
| `PASSWORD_CHANGE_FAIL` | WARNING | Senha atual incorreta |
| `SERVER_ERROR` | ERROR | Erro interno do servidor (500) |

---

## Documentação detalhada

| Documento | Descrição |
|-----------|-----------|
| [`docs/ci-cd.md`](docs/ci-cd.md) | Explicação detalhada do pipeline CI/CD (5 jobs, ferramentas, fluxo) |
| [`docs/security.md`](docs/security.md) | Ameaças de segurança identificadas e mitigações implementadas |
