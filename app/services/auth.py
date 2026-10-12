"""Autenticação, sessão e autorização (RBAC)."""
from __future__ import annotations

from datetime import datetime, timedelta

from app.core.audit import AuditService
from app.core.security import PasswordService, generate_token
from app.domain.models import CurrentUser
from app.repositories import UserRepo


class AuthError(Exception):
    pass


class Session:
    def __init__(self, user: CurrentUser):
        self.token = generate_token()
        self.user = user
        self.created_at = datetime.now()
        self.last_activity = datetime.now()


class AuthService:
    def __init__(self, db, failed_limit: int = 5, timeout_minutes: int = 30,
                 lock_minutes: int = 15):
        self._db = db
        self.users = UserRepo(db)
        self.audit = AuditService(db)
        self.failed_limit = failed_limit
        self.timeout_minutes = timeout_minutes
        self.lock_minutes = lock_minutes
        self._session: Session | None = None

    # ------------------------------------------------------------------
    def login(self, username: str, password: str, terminal: str = "") -> CurrentUser:
        row = self.users.get_by_username(username)
        if not row:
            self.audit.log(action="LOGIN_FALHA", username=username, terminal=terminal,
                           reason="usuário inexistente")
            raise AuthError("Usuário ou senha inválidos.")
        if not row["is_active"]:
            self.audit.log(action="LOGIN_BLOQUEADO", user_id=row["id"],
                           username=row["username"], terminal=terminal)
            raise AuthError("Usuário inativo. Contate o administrador.")
        if row.get("locked_until"):
            if not self.users.lock_expired(row):
                self.audit.log(action="LOGIN_FALHA", user_id=row["id"],
                               username=row["username"], terminal=terminal, reason="conta bloqueada")
                raise AuthError("Conta bloqueada por excesso de tentativas.")
            self.users.clear_lock(row["id"])
            row = self.users.get(row["id"])
        if not PasswordService.verify_password(password, row["password_hash"], row["salt"]):
            locked = self.users.register_failure(row["id"], self.failed_limit,
                                            self.lock_minutes)
            reason = "conta bloqueada" if locked else "senha incorreta"
            self.audit.log(action="LOGIN_FALHA", user_id=row["id"],
                           username=row["username"], terminal=terminal, reason=reason)
            if locked:
                raise AuthError("Conta bloqueada por excesso de tentativas.")
            raise AuthError("Usuário ou senha inválidos.")
        self.users.reset_failures(row["id"])
        user = self.users.to_current(row)
        if user.terminal:
            pass
        user.terminal = terminal or user.terminal
        self._session = Session(user)
        self.audit.log(action="LOGIN_OK", user_id=user.id, username=user.username,
                       terminal=terminal, ip="127.0.0.1")
        return user

    def logout(self) -> None:
        if self._session:
            u = self._session.user
            self.audit.log(action="LOGOUT", user_id=u.id, username=u.username,
                           terminal=u.terminal)
        self._session = None

    # ------------------------------------------------------------------
    def current(self) -> CurrentUser | None:
        return self._session.user if self._session else None

    def touch(self) -> bool:
        """Renova uso; False se a sessão expirou."""
        if not self._session:
            return False
        now = datetime.now()
        if now - self._session.last_activity > timedelta(minutes=self.timeout_minutes):
            self.logout()
            return False
        self._session.last_activity = now
        return True

    def require_permission(self, permission: str) -> CurrentUser:
        user = self.current()
        if not user:
            raise AuthError("Sessão expirada. Faça login novamente.")
        if not user.can(permission):
            raise PermissionError("Você não tem permissão para esta ação.")
        return user

    def can(self, permission: str) -> bool:
        user = self.current()
        return bool(user and user.can(permission))

    # ------------------------------------------------------------------
    def change_password(self, user_id: int, old: str, new: str) -> None:
        row = self.users.get(user_id)
        if not row:
            raise AuthError("Usuário não encontrado.")
        if not PasswordService.verify_password(old, row["password_hash"], row["salt"]):
            raise AuthError("Senha atual incorreta.")
        if len(new) < 8:
            raise AuthError("A nova senha deve ter pelo menos 8 caracteres.")
        h, s = PasswordService.hash_password(new)
        self.users.set_password(user_id, h, s)
        self.audit.log(action="SENHA_ALTERADA", user_id=user_id,
                       username=row["username"])

    def create_user(self, username: str, name: str, password: str, role: str,
                    terminal: str = "") -> CurrentUser:
        if len(password) < 8:
            raise AuthError("A senha deve ter pelo menos 8 caracteres.")
        if self.users.get_by_username(username):
            raise AuthError("Nome de usuário já existe.")
        h, s = PasswordService.hash_password(password)
        self.users.create(username.lower(), name, h, s, role, terminal)
        return self.login(username.lower(), password, terminal)