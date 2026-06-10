# Ameaças de Segurança e Mitigações — Task Manager

Este documento descreve as ameaças de segurança identificadas para a aplicação
Task Manager e as mitigações implementadas na Etapa 1 do estudo de caso DevSecOps.

---

## 1. Proteção de dados dos usuários

| Mecanismo | Detalhes |
|-----------|----------|
| **Hash de senhas com bcrypt** | Senhas nunca são armazenadas em texto plano. Utilizamos `Flask-Bcrypt` com fator de custo 12 (padrão). Mesmo em caso de vazamento do banco, as senhas permanecem protegidas. |
| **SECRET_KEY via variável de ambiente** | A chave secreta usada para assinar sessões e tokens CSRF é carregada de `os.environ.get('SECRET_KEY')`. O valor padrão (`dev-only-insecure-key-change-me`) só é aceitável em desenvolvimento local. Em produção, uma chave forte deve ser definida como variável de ambiente. |
| **Sessões protegidas por CSRF token** | Todos os formulários incluem `{{ form.hidden_tag() }}` que injeta o token CSRF automaticamente via Flask-WTF. Requisições POST sem token válido são rejeitadas. |
| **SQLite com acesso restrito** | O banco de dados SQLite reside dentro do container Docker e só é acessível pelo processo da aplicação, executando como usuário não-root (`appuser`). |

---

## 2. Prevenção de ataques de negação de serviço (DoS)

| Mecanismo | Detalhes |
|-----------|----------|
| **Gunicorn com limite de workers** | O servidor WSGI de produção (`gunicorn`) é configurado com `--workers 2 --timeout 60`, limitando a concorrência e evitando consumo excessivo de recursos por requisições lentas. |
| **Docker com limite de recursos** | Em produção, o container é configurado com limites de CPU (1.0) e memória (512MB) via `docker-compose`, impedindo que a aplicação consuma todos os recursos do host. |
| **Fail2ban monitorando AUTH_FAILURE** | O Fail2ban é configurado para monitorar logs de `AUTH_FAILURE` no syslog. Após 5 tentativas de login falhadas em 10 minutos, o IP ofensor é bloqueado automaticamente, mitigando ataques de força bruta. |

---

## 3. O que é registrado como violação de segurança

Todos os eventos de segurança são registrados via syslog (quando disponível) e stdout
(sempre ativo, capturado pelo Docker). Os seguintes eventos são classificados como
violações de segurança:

| Evento de log | Descrição | Nível |
|---------------|-----------|-------|
| `SECURITY_VIOLATION action=403 user=X ip=Y path=Z` | Tentativa de acesso a rota sem permissão (HTTP 403). | WARNING |
| `SECURITY_VIOLATION action=unauthorized_update user=X task_id=Y ip=Z` | Tentativa de editar tarefa pertencente a outro usuário. | WARNING |
| `SECURITY_VIOLATION action=unauthorized_delete user=X task_id=Y ip=Z` | Tentativa de deletar tarefa pertencente a outro usuário. | WARNING |
| `AUTH_FAILURE user=X ip=Y` | Tentativa de login com credenciais incorretas. Monitorado pelo Fail2ban para bloqueio automático após reincidência. | WARNING |

### Eventos informativos de auditoria

| Evento de log | Descrição | Nível |
|---------------|-----------|-------|
| `AUTH_SUCCESS user=X ip=Y` | Login bem-sucedido. | INFO |
| `AUTH_LOGOUT user=X ip=Y` | Logout realizado. | INFO |
| `USER_REGISTER user=X ip=Y` | Registro de novo usuário. | INFO |
| `TASK_CREATE user=X task_id=Y ip=Z` | Criação de tarefa. | INFO |
| `TASK_UPDATE user=X task_id=Y ip=Z` | Atualização de tarefa. | INFO |
| `TASK_DELETE user=X task_id=Y ip=Z` | Exclusão de tarefa. | INFO |
| `PASSWORD_CHANGE user=X ip=Y` | Troca de senha bem-sucedida. | INFO |
| `PASSWORD_CHANGE_FAIL user=X ip=Y` | Tentativa de troca de senha com senha antiga incorreta. | WARNING |
| `SERVER_ERROR ip=X path=Y` | Erro interno do servidor (HTTP 500). | ERROR |
