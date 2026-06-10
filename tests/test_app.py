"""
Testes automatizados — Task Manager Flask
Execução: pytest tests/ -v --cov=todo_project --cov-report=xml
"""
import os
import sys
import pytest

# Coloca app/ no path para que `from todo_project import ...` funcione
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

os.environ.setdefault("SECRET_KEY", "test-secret-key-pytest")
os.environ.setdefault("DATABASE_URI", "sqlite:///:memory:")
os.environ.setdefault("FLASK_ENV", "testing")


# ── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def app():
    from todo_project import app as flask_app, db

    flask_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,          # desativa CSRF nos testes
        SECRET_KEY="test-secret-key-pytest",
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def registered_user(client):
    """Registra um usuário de teste e retorna as credenciais."""
    client.post("/register", data={
        "username": "testuser",
        "password": "TestPass1!",
        "confirm_password": "TestPass1!",
    })
    return {"username": "testuser", "password": "TestPass1!"}


# ── Testes de saúde ────────────────────────────────────────────────────────

class TestHealth:
    def test_health_returns_200(self, client):
        res = client.get("/health")
        assert res.status_code == 200

    def test_health_returns_ok_json(self, client):
        res = client.get("/health")
        assert res.get_json()["status"] == "ok"


# ── Testes de páginas públicas ─────────────────────────────────────────────

class TestPublicPages:
    def test_about_loads(self, client):
        res = client.get("/about")
        assert res.status_code == 200

    def test_root_loads(self, client):
        res = client.get("/")
        assert res.status_code == 200

    def test_login_page_loads(self, client):
        res = client.get("/login")
        assert res.status_code == 200
        assert b"Login" in res.data

    def test_register_page_loads(self, client):
        res = client.get("/register")
        assert res.status_code == 200
        assert b"Register" in res.data


# ── Testes de autenticação ─────────────────────────────────────────────────

class TestAuthentication:
    @pytest.fixture(autouse=True)
    def ensure_logged_out(self, client):
        """Garante que cada teste começa sem sessão ativa."""
        client.get("/logout")
        yield
        client.get("/logout")

    def test_register_new_user(self, client):
        res = client.post("/register", data={
            "username": "newuser2",
            "password": "NewPass1!",
            "confirm_password": "NewPass1!",
        }, follow_redirects=True)
        assert res.status_code == 200

    def test_register_duplicate_username_fails(self, client, registered_user):
        # Tenta registrar o mesmo username novamente
        res = client.post("/register", data={
            "username": registered_user["username"],
            "password": "AnyPass1!",
            "confirm_password": "AnyPass1!",
        }, follow_redirects=True)
        # Deve permanecer na página de registro com erro
        assert res.status_code == 200
        assert b"Register" in res.data

    def test_login_valid_credentials(self, client, registered_user):
        res = client.post("/login", data=registered_user, follow_redirects=True)
        assert res.status_code == 200

    def test_login_wrong_password(self, client, registered_user):
        res = client.post("/login", data={
            "username": registered_user["username"],
            "password": "WrongPassword!",
        }, follow_redirects=True)
        assert b"Login Unsuccessful" in res.data

    def test_login_nonexistent_user(self, client):
        res = client.post("/login", data={
            "username": "naoexiste",
            "password": "AnyPass1!",
        }, follow_redirects=True)
        assert b"Login Unsuccessful" in res.data


# ── Testes de proteção de rotas (autenticação obrigatória) ────────────────

class TestRouteProtection:
    """Requisito: autenticação é obrigatória antes de qualquer ação."""

    @pytest.fixture(autouse=True)
    def ensure_logged_out(self, client):
        """Garante estado deslogado antes de cada teste."""
        client.get("/logout")
        yield

    def test_all_tasks_sem_login_redireciona(self, client):
        res = client.get("/all_tasks")
        assert res.status_code in (302, 401)

    def test_add_task_sem_login_redireciona(self, client):
        res = client.get("/add_task")
        assert res.status_code in (302, 401)

    def test_account_sem_login_redireciona(self, client):
        res = client.get("/account")
        assert res.status_code in (302, 401)

    def test_change_password_sem_login_redireciona(self, client):
        res = client.get("/account/change_password")
        assert res.status_code in (302, 401)

    def test_redirect_aponta_para_login(self, client):
        res = client.get("/all_tasks", follow_redirects=True)
        assert b"Login" in res.data


# ── Testes funcionais de tarefas ───────────────────────────────────────────

class TestTasks:
    @pytest.fixture(autouse=True)
    def login_user(self, client, registered_user):
        """Faz login antes de cada teste desta classe."""
        client.post("/login", data=registered_user)
        yield
        client.get("/logout")

    def test_all_tasks_carrega_com_login(self, client):
        res = client.get("/all_tasks")
        assert res.status_code == 200

    def test_add_task_carrega_com_login(self, client):
        res = client.get("/add_task")
        assert res.status_code == 200

    def test_criar_tarefa(self, client):
        res = client.post("/add_task", data={
            "task_name": "Tarefa de teste automatizado"
        }, follow_redirects=True)
        assert res.status_code == 200

    def test_deletar_tarefa_inexistente_retorna_404(self, client):
        res = client.get("/all_tasks/99999/delete_task")
        assert res.status_code == 404

    def test_atualizar_tarefa_inexistente_retorna_404(self, client):
        res = client.get("/all_tasks/99999/update_task")
        assert res.status_code == 404

    def test_logout_redireciona_para_login(self, client):
        res = client.get("/logout", follow_redirects=True)
        assert b"Login" in res.data


# ── Testes de busca de tarefas (RF-03) ─────────────────────────────────────

class TestTaskSearch:
    @pytest.fixture(autouse=True)
    def login_and_seed(self, client, registered_user):
        """Faz login e cria tarefas de teste para busca."""
        client.post("/login", data=registered_user)
        client.post("/add_task", data={"task_name": "Comprar leite"})
        client.post("/add_task", data={"task_name": "Estudar Python"})
        client.post("/add_task", data={"task_name": "Comprar pão"})
        yield
        client.get("/logout")

    def test_busca_retorna_resultados(self, client):
        res = client.get("/all_tasks?q=Comprar")
        assert res.status_code == 200
        assert b"Comprar leite" in res.data
        assert b"Comprar" in res.data

    def test_busca_sem_resultado(self, client):
        res = client.get("/all_tasks?q=inexistente")
        assert res.status_code == 200
        assert "Nenhuma tarefa encontrada para".encode() in res.data

    def test_busca_vazia_retorna_todas(self, client):
        res = client.get("/all_tasks?q=")
        assert res.status_code == 200
        # Deve conter todas as tarefas criadas
        assert b"Comprar leite" in res.data
        assert b"Estudar Python" in res.data


# ── Testes de proteção de ownership (RF-04) ────────────────────────────────

class TestOwnershipProtection:
    def test_editar_tarefa_de_outro_usuario_retorna_403(self, client, app):
        """Usuário B tenta editar tarefa do Usuário A → 403."""
        from todo_project import db, bcrypt
        from todo_project.models import User, Task

        with app.app_context():
            # Criar usuário A e sua tarefa
            if not User.query.filter_by(username="ownerA").first():
                pw = bcrypt.generate_password_hash("PassA123!").decode("utf-8")
                user_a = User(username="ownerA", password=pw)
                db.session.add(user_a)
                db.session.commit()
                task = Task(content="Tarefa do A", user_id=user_a.id)
                db.session.add(task)
                db.session.commit()
                task_id = task.id
            else:
                user_a = User.query.filter_by(username="ownerA").first()
                task_id = user_a.tasks[0].id

            # Criar usuário B
            if not User.query.filter_by(username="ownerB").first():
                pw = bcrypt.generate_password_hash("PassB123!").decode("utf-8")
                user_b = User(username="ownerB", password=pw)
                db.session.add(user_b)
                db.session.commit()

        # Login como usuário B
        client.post("/login", data={"username": "ownerB", "password": "PassB123!"})

        # Tentar editar tarefa do usuário A
        res = client.get(f"/all_tasks/{task_id}/update_task")
        assert res.status_code == 403

        client.get("/logout")

    def test_deletar_tarefa_de_outro_usuario_retorna_403(self, client, app):
        """Usuário B tenta deletar tarefa do Usuário A → 403."""
        from todo_project.models import User

        with app.app_context():
            user_a = User.query.filter_by(username="ownerA").first()
            task_id = user_a.tasks[0].id

        # Login como usuário B
        client.post("/login", data={"username": "ownerB", "password": "PassB123!"})

        # Tentar deletar tarefa do usuário A
        res = client.get(f"/all_tasks/{task_id}/delete_task")
        assert res.status_code == 403

        client.get("/logout")


# ── Testes de troca de senha (UC-09) ───────────────────────────────────────

class TestPasswordChange:
    def test_trocar_senha_com_senha_errada(self, client, registered_user):
        """Testa troca de senha com senha antiga incorreta (roda primeiro para não afetar estado)."""
        client.get("/logout")
        client.post("/login", data=registered_user)
        res = client.post("/account/change_password", data={
            "old_password": "SenhaErrada!",
            "new_password": "NovaSenha123!",
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"Please Enter Correct Password" in res.data
        client.get("/logout")

    def test_trocar_senha_com_sucesso(self, client, registered_user):
        """Testa troca de senha com senha antiga correta."""
        client.get("/logout")
        client.post("/login", data=registered_user)
        res = client.post("/account/change_password", data={
            "old_password": registered_user["password"],
            "new_password": "NewSecurePass1!",
        }, follow_redirects=True)
        assert res.status_code == 200
        assert b"Password Changed Successfully" in res.data
        client.get("/logout")
