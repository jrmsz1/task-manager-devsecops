from flask import render_template, url_for, flash, redirect, request, jsonify
from flask_login import login_required, current_user, login_user, logout_user

from todo_project import app, db, bcrypt, logger
from todo_project.forms import (
    LoginForm, RegistrationForm, UpdateUserInfoForm,
    UpdateUserPassword, TaskForm, UpdateTaskForm,
)
from todo_project.models import User, Task


# ── Error handlers ─────────────────────────────────────────────────────────

@app.errorhandler(404)
def error_404(error):
    return render_template('errors/404.html'), 404


@app.errorhandler(403)
def error_403(error):
    user = current_user.username if current_user.is_authenticated else 'anonymous'
    logger.warning("SECURITY_VIOLATION action=403 user=%s ip=%s path=%s",
                   user, request.remote_addr, request.path)
    return render_template('errors/403.html'), 403


@app.errorhandler(500)
def error_500(error):
    logger.error("SERVER_ERROR action=500 ip=%s path=%s", request.remote_addr, request.path)
    return render_template('errors/500.html'), 500


# ── Rotas públicas ─────────────────────────────────────────────────────────

@app.route("/")
@app.route("/about")
def about():
    return render_template('about.html', title='About')


@app.route("/login", methods=['POST', 'GET'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('all_tasks'))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            logger.info("AUTH_SUCCESS user=%s ip=%s", form.username.data, request.remote_addr)
            flash('Login Successfull', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('all_tasks'))
        else:
            logger.warning("AUTH_FAILURE user=%s ip=%s", form.username.data, request.remote_addr)
            flash('Login Unsuccessful. Please check Username Or Password', 'danger')

    return render_template('login.html', title='Login', form=form)


@app.route("/logout")
@login_required
def logout():
    logger.info("AUTH_LOGOUT user=%s ip=%s", current_user.username, request.remote_addr)
    logout_user()
    return redirect(url_for('login'))


@app.route("/register", methods=['POST', 'GET'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('all_tasks'))

    form = RegistrationForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(username=form.username.data, password=hashed_password)
        db.session.add(user)
        db.session.commit()
        logger.info("USER_REGISTER user=%s ip=%s", form.username.data, request.remote_addr)
        flash(f'Account Created For {form.username.data}', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', title='Register', form=form)


# ── Rotas protegidas ───────────────────────────────────────────────────────

@app.route("/all_tasks")
@login_required
def all_tasks():
    q = request.args.get('q', '').strip()
    user = User.query.filter_by(username=current_user.username).first()

    if q:
        tasks = Task.query.filter(
            Task.user_id == user.id,
            Task.content.ilike(f'%{q}%')
        ).all()
        logger.info("TASK_SEARCH user=%s query='%s' results=%d ip=%s",
                    current_user.username, q, len(tasks), request.remote_addr)
    else:
        tasks = user.tasks

    logger.info("ACCESS route=all_tasks user=%s ip=%s", current_user.username, request.remote_addr)
    return render_template('all_tasks.html', title='All Tasks', tasks=tasks, search_query=q)


@app.route("/add_task", methods=['POST', 'GET'])
@login_required
def add_task():
    form = TaskForm()
    if form.validate_on_submit():
        task = Task(content=form.task_name.data, author=current_user)
        db.session.add(task)
        db.session.commit()
        logger.info("TASK_CREATE user=%s task_id=%s ip=%s",
                    current_user.username, task.id, request.remote_addr)
        flash('Task Created', 'success')
        return redirect(url_for('add_task'))
    return render_template('add_task.html', form=form, title='Add Task')


@app.route("/all_tasks/<int:task_id>/update_task", methods=['GET', 'POST'])
@login_required
def update_task(task_id):
    task = Task.query.get_or_404(task_id)

    # Garante que o usuário só edita suas próprias tarefas
    if task.author != current_user:
        logger.warning("SECURITY_VIOLATION action=unauthorized_update user=%s task_id=%s ip=%s",
                       current_user.username, task_id, request.remote_addr)
        return render_template('errors/403.html'), 403

    form = UpdateTaskForm()
    if form.validate_on_submit():
        if form.task_name.data != task.content:
            task.content = form.task_name.data
            db.session.commit()
            logger.info("TASK_UPDATE user=%s task_id=%s ip=%s",
                        current_user.username, task_id, request.remote_addr)
            flash('Task Updated', 'success')
            return redirect(url_for('all_tasks'))
        else:
            flash('No Changes Made', 'warning')
            return redirect(url_for('all_tasks'))
    elif request.method == 'GET':
        form.task_name.data = task.content

    return render_template('add_task.html', title='Update Task', form=form)


@app.route("/all_tasks/<int:task_id>/delete_task")
@login_required
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)

    # Garante que o usuário só deleta suas próprias tarefas
    if task.author != current_user:
        logger.warning("SECURITY_VIOLATION action=unauthorized_delete user=%s task_id=%s ip=%s",
                       current_user.username, task_id, request.remote_addr)
        return render_template('errors/403.html'), 403

    db.session.delete(task)
    db.session.commit()
    logger.info("TASK_DELETE user=%s task_id=%s ip=%s",
                current_user.username, task_id, request.remote_addr)
    flash('Task Deleted', 'info')
    return redirect(url_for('all_tasks'))


@app.route("/account", methods=['POST', 'GET'])
@login_required
def account():
    form = UpdateUserInfoForm()
    if form.validate_on_submit():
        if form.username.data != current_user.username:
            current_user.username = form.username.data
            db.session.commit()
            logger.info("ACCOUNT_UPDATE user=%s ip=%s", current_user.username, request.remote_addr)
            flash('Username Updated Successfully', 'success')
            return redirect(url_for('account'))
    elif request.method == 'GET':
        form.username.data = current_user.username

    return render_template('account.html', title='Account Settings', form=form)


@app.route("/account/change_password", methods=['POST', 'GET'])
@login_required
def change_password():
    form = UpdateUserPassword()
    if form.validate_on_submit():
        if bcrypt.check_password_hash(current_user.password, form.old_password.data):
            current_user.password = bcrypt.generate_password_hash(
                form.new_password.data
            ).decode('utf-8')
            db.session.commit()
            logger.info("PASSWORD_CHANGE user=%s ip=%s", current_user.username, request.remote_addr)
            flash('Password Changed Successfully', 'success')
            return redirect(url_for('account'))
        else:
            logger.warning("PASSWORD_CHANGE_FAIL user=%s ip=%s",
                           current_user.username, request.remote_addr)
            flash('Please Enter Correct Password', 'danger')

    return render_template('change_password.html', title='Change Password', form=form)


# ── Health check para Docker / CI ──────────────────────────────────────────

@app.route("/health")
def health():
    return jsonify(status="ok"), 200
