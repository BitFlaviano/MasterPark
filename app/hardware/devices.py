"""Camada de abstração de hardware (integração limpa por fabricante).

Filosofia: interfaces + adaptadores. Dispositivos não integrados de verdade
são SIMULADOS e marcados como DEMO. Nunca afirmamos integração real sem ser.
"""
from __future__ import annotations

import datetime
import random


class BaseDevice:
    kind = "generic"
    simulated = True

    def __init__(self, name: str = "", endpoint: str = ""):
        self.name = name or f"{self.kind.capitalize()} DEMO"
        self.endpoint = endpoint
        self.status = "INDISPONIVEL"

    def connect(self) -> bool:
        self.status = "CONECTADO"
        return True

    def disconnect(self) -> None:
        self.status = "INDISPONIVEL"

    def health(self) -> dict:
        return {"kind": self.kind, "name": self.name,
                "status": self.status, "simulated": self.simulated}


# ----------------------------------------------------------------------
# Câmeras LPR/ANPR
# ----------------------------------------------------------------------
class LprCamera(BaseDevice):
    kind = "camera"
    """Contrato para câmeras com reconhecimento de placa."""

    protocol = "DEMO"

    def read_plate(self) -> dict:
        """Retorna {'plate', 'confidence', 'ts'} ou None."""
        raise NotImplementedError


class SimulatedLprCamera(LprCamera):
    """Gera placas aleatórias para demonstração. NÃO é uma integração real."""

    def __init__(self, name: str = "Câmera Entrada (DEMO)", plates_pool: list[str] | None = None,
                 endpoint: str = ""):
        super().__init__(name, endpoint)
        self.plates_pool = plates_pool or []
        self.protocol = "SIMULATED"

    def read_plate(self) -> dict | None:
        if random.random() < 0.55:
            return None
        if self.plates_pool:
            plate = random.choice(self.plates_pool)
        else:
            plate = random_plate()
        return {"plate": plate,
                "confidence": round(random.uniform(0.72, 0.99), 2),
                "ts": datetime.datetime.now().isoformat()}


# ----------------------------------------------------------------------
# Cancelas
# ----------------------------------------------------------------------
class BarrierGate(BaseDevice):
    kind = "cancela"

    def open(self) -> bool:
        raise NotImplementedError

    def close(self) -> bool:
        raise NotImplementedError


class SimulatedBarrierGate(BarrierGate):
    def open(self) -> bool:
        self.status = "ABERTA"
        return True

    def close(self) -> bool:
        self.status = "FECHADA"
        return True


# ----------------------------------------------------------------------
# Sensores / display / semáforo
# ----------------------------------------------------------------------
class Display(BaseDevice):
    kind = "display"

    def show(self, text: str, color: str = "white") -> bool:
        raise NotImplementedError


class SimulatedDisplay(Display):
    def show(self, text: str, color: str = "white") -> bool:
        self.status = "LIGADO"
        return True


class Sensor(BaseDevice):
    kind = "sensor"

    def detect(self) -> bool:
        raise NotImplementedError


class SimulatedSensor(Sensor):
    def detect(self) -> bool:
        return random.random() < 0.35


# ----------------------------------------------------------------------
# POS / TEF
# ----------------------------------------------------------------------
class PosTerminal(BaseDevice):
    kind = "pos"
    """Contrato para máquinas POS/TEF (Pix, cartões)."""

    def request_payment(self, value_cents: int, method: str) -> dict:
        """Retorna {'status': SOLICITADO|APROVADO|RECUSADO, 'tid', 'message'}."""
        raise NotImplementedError


class SimulatedPosTerminal(PosTerminal):
    """Simulador POS — NUNCA aprova sem o operador confirmar."""

    def request_payment(self, value_cents: int, method: str) -> dict:
        # Em simulação: a operação SÓ confirma pagamento quando o operador
        # clica "Pagamento recebido" — aqui retornamos PENDENTE.
        return {"status": "SOLICITADO", "tid": f"DEMO-{random.randint(1000, 9999)}",
                "method": method, "message": "Aprovação requerida pelo operador (DEMO)"}


# ----------------------------------------------------------------------
class DeviceManager:
    """Registra e gerencia dispositivos por tipo e nome."""

    def __init__(self, db):
        self.db = db
        self._devices: dict[str, BaseDevice] = {}

    def register(self, device: BaseDevice, key: str | None = None) -> None:
        key = key or device.name
        self._devices[key] = device

    def get(self, key: str) -> BaseDevice | None:
        return self._devices.get(key)

    def all(self) -> list[BaseDevice]:
        return list(self._devices.values())

    def status_snapshot(self) -> list[dict]:
        return [d.health() for d in self._devices.values()]

    def build_demo_set(self, plates_pool: list[str] | None = None) -> None:
        self.register(SimulatedLprCamera("Câmera Entrada (DEMO)", plates_pool), "camera_entrada")
        self.register(SimulatedLprCamera("Câmera Saída (DEMO)", plates_pool), "camera_saida")
        self.register(SimulatedBarrierGate("Cancela Entrada (DEMO)"), "cancela_entrada")
        self.register(SimulatedBarrierGate("Cancela Saída (DEMO)"), "cancela_saida")
        self.register(SimulatedDisplay("Display Pátio (DEMO)"), "display")
        self.register(SimulatedSensor("Sensor Vaga 01 (DEMO)"), "sensor_01")
        self.register(SimulatedPosTerminal("POS Rede (DEMO)"), "pos")


def random_plate() -> str:
    import string
    letters = "".join(random.choices(string.ascii_uppercase, k=3))
    digits = "".join(random.choices(string.digits, k=4))
    if random.random() < 0.5:
        letter_digit = random.choice(string.ascii_uppercase + string.digits)
        return f"{letters[:3]}{random.choice(string.digits)}{random.choice(string.ascii_uppercase)}{digits[1:]}"
    return letters + digits