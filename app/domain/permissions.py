"""Catálogo central de permissões e perfis (RBAC)."""
from __future__ import annotations

# código -> (label, módulo)
PERMISSIONS: dict[str, tuple[str, str]] = {
    "DASH_VIEW": ("Ver dashboard", "Dashboard"),
    "ENTRY_CREATE": ("Registrar entrada", "Operação"),
    "EXIT_CREATE": ("Registrar saída", "Operação"),
    "EXIT_MANUAL_VALUE": ("Alterar valor em saída", "Operação"),
    "TICKET_CANCEL": ("Cancelar ticket", "Operação"),
    "TICKET_LOST": ("Tratar ticket perdido", "Operação"),
    "DISCOUNT_APPLY": ("Conceder desconto", "Operação"),
    "REFUND": ("Fazer estorno", "Financeiro"),
    "CASH_OPEN": ("Abrir caixa", "Caixa"),
    "CASH_CLOSE": ("Fechar caixa", "Caixa"),
    "CASH_SANGRIA": ("Fazer sangria/suprimento", "Caixa"),
    "CASH_MANUAL": ("Lançamento manual no caixa", "Caixa"),
    "REPORT_VIEW": ("Visualizar relatórios", "Relatórios"),
    "REPORT_EXPORT": ("Exportar relatórios", "Relatórios"),
    "FINANCE_VIEW": ("Visualizar faturamento", "Financeiro"),
    "CUSTOMER_MANAGE": ("Gerenciar clientes", "Cadastros"),
    "VEHICLE_MANAGE": ("Gerenciar veículos", "Cadastros"),
    "MONTHLY_MANAGE": ("Gerenciar mensalistas", "Cadastros"),
    "AGREEMENT_MANAGE": ("Gerenciar convênios", "Cadastros"),
    "RESERVATION_MANAGE": ("Gerenciar reservas", "Cadastros"),
    "TARIFF_MANAGE": ("Alterar tarifas", "Configuração"),
    "SPACE_MANAGE": ("Gerenciar vagas/setores", "Configuração"),
    "USER_MANAGE": ("Gerenciar usuários/permissões", "Configuração"),
    "CONFIG_MANAGE": ("Alterar configurações", "Configuração"),
    "AUDIT_VIEW": ("Visualizar auditoria", "Auditoria"),
    "BACKUP_MANAGE": ("Executar backup/restauração", "Manutenção"),
    "LICENSE_VIEW": ("Visualizar licença", "Licença"),
    "DEVICE_MANAGE": ("Gerenciar dispositivos", "Hardware"),
    "INCIDENT_MANAGE": ("Gerenciar ocorrências", "Operação"),
}

# Perfis padrão -> conjunto de permissões
ROLES: dict[str, tuple[str, set[str]]] = {
    "ADMINISTRADOR": ("Administrador", set(PERMISSIONS.keys())),
    "GERENTE": ("Gerente", {
        "DASH_VIEW", "ENTRY_CREATE", "EXIT_CREATE", "DISCOUNT_APPLY", "REFUND",
        "CASH_OPEN", "CASH_CLOSE", "CASH_SANGRIA", "REPORT_VIEW", "REPORT_EXPORT",
        "FINANCE_VIEW", "CUSTOMER_MANAGE", "VEHICLE_MANAGE", "MONTHLY_MANAGE",
        "AGREEMENT_MANAGE", "RESERVATION_MANAGE", "INCIDENT_MANAGE", "AUDIT_VIEW",
        "LICENSE_VIEW", "BACKUP_MANAGE", "TARIFF_MANAGE",
    }),
    "SUPERVISOR": ("Supervisor", {
        "DASH_VIEW", "ENTRY_CREATE", "EXIT_CREATE", "EXIT_MANUAL_VALUE",
        "DISCOUNT_APPLY", "TICKET_LOST", "CASH_OPEN", "CASH_CLOSE", "CASH_SANGRIA",
        "CASH_MANUAL", "REPORT_VIEW", "FINANCE_VIEW", "INCIDENT_MANAGE",
    }),
    "CAIXA": ("Caixa", {
        "DASH_VIEW", "ENTRY_CREATE", "EXIT_CREATE", "DISCOUNT_APPLY",
        "CASH_OPEN", "CASH_CLOSE", "CASH_SANGRIA", "CASH_MANUAL",
        "REPORT_VIEW", "FINANCE_VIEW",
    }),
    "OPERADOR": ("Operador", {
        "DASH_VIEW", "ENTRY_CREATE", "EXIT_CREATE",
        "TICKET_LOST", "INCIDENT_MANAGE",
    }),
    "AUDITOR": ("Auditor", {
        "DASH_VIEW", "REPORT_VIEW", "REPORT_EXPORT", "FINANCE_VIEW",
        "AUDIT_VIEW", "LICENSE_VIEW",
    }),
}


def role_permissions(role_code: str) -> set[str]:
    return ROLES.get(role_code, ("", set()))[1]


def role_label(role_code: str) -> str:
    return ROLES.get(role_code, (role_code or "?"))[0]


# ----------------------------------------------------------------------
# Recursos exclusivos de administrador
# ----------------------------------------------------------------------
ADMIN_ROLE = "ADMINISTRADOR"

# Telas/navegação disponíveis somente para o perfil administrador.
# O mapa de vagas é VISÍVEL para todos (visualização); o gerenciamento
# (adição, edição, exclusão) fica restrito a SPACE_MANAGE, que só o
# ADMINISTRADOR possui — ver app/ui/map_view.py.
ADMIN_ONLY_SCREENS: frozenset[str] = frozenset({
    "dashboard",
    "reports",
    "settings",
    "health",
    "audit",
    "users",
})

# Telas liberadas por permissão individual (valem para qualquer perfil).
PERMISSION_SCREENS: dict[str, str] = {
    "MONTHLY_MANAGE": "monthly",
    "CUSTOMER_MANAGE": "customers",
    "CASH_OPEN": "cash",
}


def is_admin_role(role_code: str) -> bool:
    return role_code == ADMIN_ROLE


def hidden_menu_keys(role_code: str, permissions: set[str]) -> set[str]:
    """Chaves de menu que devem ficar ocultas para o usuário.

    Recursos de administrador são liberados apenas pelo perfil
    ADMINISTRADOR; o restante depende de permissões individuais.
    """
    hidden = set()
    if not is_admin_role(role_code):
        hidden.update(ADMIN_ONLY_SCREENS)
    for perm, key in PERMISSION_SCREENS.items():
        if perm not in permissions:
            hidden.add(key)
    return hidden


def first_screen_for(role_code: str) -> str:
    """Tela inicial após o login: administrador vê o Dashboard,
    operadores entram direto na Nova Entrada."""
    return "dashboard" if is_admin_role(role_code) else "entry"


def seed_roles(db) -> None:
    for code, (name, perms) in ROLES.items():
        db.execute("INSERT OR IGNORE INTO roles(code, name, is_system) VALUES (?,?,1)",
                   (code, name))
        for perm in perms:
            db.execute("INSERT OR IGNORE INTO permissions(code, label, module)"
                       " VALUES (?,?,?)",
                       (perm, PERMISSIONS[perm][0], PERMISSIONS[perm][1]))
        for perm in perms:
            db.execute("INSERT OR IGNORE INTO role_permissions(role_code, permission_code)"
                       " VALUES (?,?)", (code, perm))