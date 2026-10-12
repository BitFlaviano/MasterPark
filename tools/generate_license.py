"""Ferramenta do fabricante: gerar chave RSA, licenças e códigos de ativação.

Uso:
  python tools/generate_license.py genkeys          # gera par de chaves
  python tools/generate_license.py create --cliente "X Ltda" --cnpj 00.000.000/0000-00 \
        --plano PROFESSIONAL --duracao 1            # 1 ano (2 = 2 anos, 3 = 3 anos)
  python tools/generate_license.py create --cliente "Y Ltda" --duracao vida   # vitalícia
  python tools/generate_license.py create --cliente "Z Ltda" --validade 365   # dias (compat)

Saídas:
  keys/private.pem            chave privada (NUNCA vai para o cliente)
  keys/public.pem             chave pública (embutida na aplicação)
  licencas/<licenca>.lic      arquivo de licença assinado
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEYS_DIR = ROOT / "tools" / "keys"
OUT_DIR = ROOT / "tools" / "licencas"


def utcnow() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def later(days: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def sign(private, payload: dict) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    sig = private.sign(canonical(payload), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def load_or_create_keys() -> tuple[object, str]:
    KEYS_DIR.mkdir(parents=True, exist_ok=True)
    priv_path = KEYS_DIR / "private.pem"
    pub_path = KEYS_DIR / "public.pem"
    if priv_path.exists() and pub_path.exists():
        from cryptography.hazmat.primitives import serialization
        private = serialization.load_pem_private_key(
            priv_path.read_bytes(), password=None)
        return private, pub_path.read_text().decode() if isinstance(pub_path.read_text(), bytes) else pub_path.read_text()
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pub_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    priv_path.write_bytes(priv_pem)
    pub_path.write_bytes(pub_pem)
    print(f"[chaves] geradas em {KEYS_DIR}")
    return private, pub_pem.decode()


def embed_public_key(pub_pem: str) -> None:
    """Grava a chave pública na propriedade DEFAULT_PUBLIC_KEY, em app/core/config.py."""
    cfg = ROOT / "app" / "core" / "config.py"
    body = 'DEFAULT_PUBLIC_KEY = """\n' + pub_pem.strip() + '\n"""'
    lines = cfg.read_text(encoding="utf-8").splitlines(keepends=True)
    new_lines, writing = [], False
    for line in lines:
        if line.startswith("DEFAULT_PUBLIC_KEY"):
            writing = True
            new_lines.append(body + "\n")
            continue
        if writing:
            if line.rstrip() == '"""':
                writing = False
            continue
        new_lines.append(line)
    cfg.write_text("".join(new_lines), encoding="utf-8")
    print("[chaves] chave pública embutida em app/core/config.py")


def make_key_code() -> str:
    import secrets
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    groups = ["".join(secrets.choice(chars) for _ in range(4)) for _ in range(4)]
    return "PARK-" + "-".join(groups)


def expiry_for(duracao: str) -> tuple[str, bool, str]:
    """Retorna (expires_at, lifetime, label_duracao)."""
    if duracao == "vida":
        return "", True, "VITALICIA"
    anos = int(duracao)
    return later(365 * anos), False, f"{anos} ANO{'S' if anos > 1 else ''}"


def create_license(args) -> Path:
    private, pub_pem = load_or_create_keys()
    features = [f.upper() for f in (args.feat or [])]
    if getattr(args, "duracao", None):
        expires_at, lifetime, duracao = expiry_for(args.duracao)
    elif getattr(args, "validade", None):
        expires_at, lifetime, duracao = later(int(args.validade)), False, \
            f"{args.validade} DIAS"
    else:
        raise SystemExit("Informe --duracao (1, 2, 3 ou vida) ou --validade (dias).")
    payload = {
        "license_key": args.chave or make_key_code(),
        "customer_name": args.cliente,
        "cnpj": args.cnpj,
        "product": "MASTERPARK",
        "version": args.versao or "1.0.0",
        "plan": (args.plano or "PROFESSIONAL").upper(),
        "activated_at": utcnow(),
        "expires_at": expires_at,
        "lifetime": lifetime,
        "duracao": duracao,
        "terminals": int(args.terminais or 1),
        "spaces": int(args.vagas or 0),
        "features": features,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    raw = json.dumps({"payload": payload,
                      "signature": sign(private, payload)}, ensure_ascii=False)
    out = OUT_DIR / f"licenca_{payload['license_key'].replace('-', '_')}.lic"
    out.write_text(raw, encoding="utf-8")
    print(f"[licença] criada: {out}")
    print(f"  chave      : {payload['license_key']}")
    print(f"  cliente    : {payload['customer_name']}")
    print(f"  plano      : {payload['plan']} | terminais {payload['terminals']} | vagas {payload['spaces']}")
    print(f"  duração    : {duracao}"
          + (" (nunca expira)" if lifetime else f" — expira em {expires_at}"))
    print("  Recursos :", ", ".join(features) if features else "-")
    return out


def activation_code_str(license_key: str, hw: str) -> str:
    """Gera e retorna o código de ativação offline (assinado com a privada)."""
    private, _ = load_or_create_keys()
    data = json.dumps({"activation": license_key.upper(), "hw": hw},
                      sort_keys=True).encode()
    padding_, algorithm = _paddings()
    return base64.b64encode(private.sign(data, padding_, algorithm)).decode()


def activation_code(args) -> None:
    """Gera código de ativação offline para chave+instalação."""
    hw = args.hw
    code = activation_code_str(args.chave, hw)
    print(f"[ativação] código para {args.chave} hw={hw}:")
    print(code)


def _paddings():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    return padding.PKCS1v15(), hashes.SHA256()


def main():
    p = argparse.ArgumentParser(description="Gerador de licenças MasterPark")
    sub = p.add_subparsers(dest="cmd", required=True)

    def _genkeys(args):
        _, pub = load_or_create_keys()
        embed_public_key(pub)

    sub.add_parser("genkeys").set_defaults(fn=_genkeys)
    c = sub.add_parser("create")
    c.add_argument("--cliente", required=True)
    c.add_argument("--cnpj", default="")
    c.add_argument("--plano", default="PROFESSIONAL",
                   choices=["STARTER", "PROFESSIONAL", "BUSINESS", "ENTERPRISE"])
    c.add_argument("--terminais", default="1")
    c.add_argument("--vagas", default="0")
    c.add_argument("--duracao", default="",
                   choices=["1", "2", "3", "vida"],
                   help="1, 2, 3 anos ou 'vida' (vitalícia)")
    c.add_argument("--validade", default="",
                   help="validade em dias (compatibilidade) — alternativo a --duracao")
    c.add_argument("--versao", default="1.0.0")
    c.add_argument("--feat", nargs="*", default=[])
    c.add_argument("--chave", default="")
    c.set_defaults(fn=create_license)
    a = sub.add_parser("ativar")
    a.add_argument("--chave", required=True)
    a.add_argument("--hw", required=True)
    a.set_defaults(fn=activation_code)

    args = p.parse_args()
    fn = args.fn
    # remove atributo antes de invocar fn que espera apenas args
    del args.fn
    fn(args)


if __name__ == "__main__":
    sys.exit(main())