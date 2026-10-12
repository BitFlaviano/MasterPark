"""Ponto de entrada do aplicativo MasterPark.

Fluxo de inicialização:
  1. Verificação de instância única (QSharedMemory)
  2. Primeira execução → assistente de configuração (ou modo demonstração)
  3. Licença → diálogo de ativação (online/offline)
  4. Login (RBAC) → janela principal
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    # garante que app/ está no path quando empacotado
    ROOT = Path(__file__).resolve().parent
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from PySide6.QtCore import QSharedMemory
    from PySide6.QtWidgets import QApplication

    shared = QSharedMemory("MasterPark_SingleInstance")
    if not shared.create(1):
        print("O MasterPark já está em execução nesta máquina.")
        return 1

    app = QApplication(sys.argv)
    app.setApplicationName("MasterPark")
    app.setApplicationVersion("1.0.0")
    app.setStyle("Fusion")

    from app.bootstrap import AppContext
    from app.ui.theme import build_stylesheet

    ctx = AppContext()
    app.setStyleSheet(build_stylesheet(ctx.settings.theme == "dark"))

    # 2. Primeira execução
    if ctx.is_first_run():
        from app.ui.setup_wizard import ask_setup_mode
        mode = ask_setup_mode()
        if mode == "demo":
            from app.services.demo import setup_demo
            setup_demo(ctx.db)
            ctx.refresh()
        elif mode == "wizard":
            from app.ui.setup_wizard import SetupWizard
            wizard = SetupWizard(ctx)
            if not wizard.exec():
                return 0  # usuário cancelou o assistente
            ctx.refresh()
        else:
            return 0  # modo não informado / cancelado

    # 3. Licença
    if not ctx.is_license_ok():
        from app.ui.activation import ActivationDialog
        dlg = ActivationDialog(ctx)
        if not (dlg.exec() and dlg.activated):
            return 0  # licença é obrigatória para operar
        ctx.refresh()

    # 4. Login
    from app.ui.login import LoginDialog
    from app.ui.main_window import MainWindow

    login = LoginDialog(ctx)
    if not login.exec():
        return 0
    user = login.user

    win = MainWindow(ctx)
    win.sidebar.apply_permissions(user)
    win.showMaximized()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())