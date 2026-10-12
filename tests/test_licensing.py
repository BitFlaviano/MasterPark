"""Testes do sistema de licenciamento criptográfico."""
from __future__ import annotations

import base64
import json
import datetime
from datetime import timedelta

import pytest

import app.services.licensing as licmod
from app.services.licensing import LicenseError, LicenseService


def make_keys():
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = private.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption())
    pub_pem = private.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    return private, pub_pem.decode()


def sign_payload(private, payload: dict) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":")).encode()
    sig = private.sign(canonical, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def make_license_file(private, **over):
    exp = (datetime.datetime.now(datetime.timezone.utc) + timedelta(days=365))\
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {
        "license_key": "PARK-ABCD-1234-EFGH-5678",
        "customer_name": "Cliente Teste",
        "cnpj": "00.000.000/0000-00",
        "product": "MASTERPARK",
        "version": "1.0.0",
        "plan": "PROFESSIONAL",
        "activated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "expires_at": exp,
        "terminals": 2,
        "spaces": 150,
        "features": ["LPR", "API"],
    }
    payload.update(over)
    return json.dumps({
        "payload": payload,
        "signature": sign_payload(private, payload),
    })


@pytest.fixture
def keys():
    return make_keys()


def test_ativa_licenca_valida(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    svc = LicenseService(db)
    lic = make_license_file(private)
    svc.save_license_file(lic)
    cur = svc.activate(lic)
    assert cur["status"] == "ATIVA"
    assert cur["days_left"] > 350
    assert "LPR" in svc.features()
    assert svc.has_feature("API")


def test_rejeita_licenca_adulterada(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    raw = make_license_file(private)
    data = json.loads(raw)
    data["payload"]["terminals"] = 99999   # adulteração não assinada
    forged = json.dumps(data)
    svc = LicenseService(db)
    with pytest.raises(LicenseError):
        svc.activate(forged)


def test_rejeita_assinatura_de_outra_chave(db, keys, monkeypatch):
    _, pub_pem = keys
    other_private, _ = make_keys()
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    raw = make_license_file(other_private)  # assinado por chave errada
    svc = LicenseService(db)
    with pytest.raises(LicenseError):
        svc.activate(raw)


def test_ativa_offline_com_codigo(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    raw = make_license_file(private)
    payload = json.loads(raw)["payload"]
    key = payload["license_key"]
    hw = licmod.hash_anchor(key)
    canonical = json.dumps({"activation": key, "hw": hw}, sort_keys=True).encode()
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    code = base64.b64encode(private.sign(canonical, padding.PKCS1v15(),
                                         hashes.SHA256())).decode()
    svc = LicenseService(db)
    svc.save_license_file(raw)
    cur = svc.activate_offline(key, code, hw_anchor=hw)
    assert cur["status"] == "ATIVA"


def test_ativa_licenca_vitalicia(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    lic = make_license_file(private, expires_at="", lifetime=True,
                            duracao="VITALICIA")
    svc = LicenseService(db)
    svc.save_license_file(lic)
    cur = svc.activate(lic)
    assert cur["status"] == "ATIVA"
    assert cur["lifetime"] is True
    assert cur["expired"] is False
    assert cur["days_left"] is None
    assert "nunca expira" in svc.describe(cur)


def test_rejeita_licenca_expirada(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    exp = (datetime.datetime.now(datetime.timezone.utc)
           - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lic = make_license_file(private, expires_at=exp)
    svc = LicenseService(db)
    with pytest.raises(LicenseError, match="expirada"):
        svc.activate(lic)


def test_rejeita_licenca_sem_data_e_nao_vitalicia(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    lic = make_license_file(private, expires_at="")
    svc = LicenseService(db)
    with pytest.raises(LicenseError):
        svc.activate(lic)


def test_recusa_codigo_offline_incorreto(db, keys, monkeypatch):
    private, pub_pem = keys
    monkeypatch.setattr(licmod, "PUBLIC_KEY", pub_pem)
    raw = make_license_file(private)
    key = json.loads(raw)["payload"]["license_key"]
    svc = LicenseService(db)
    svc.save_license_file(raw)
    with pytest.raises(LicenseError):
        svc.activate_offline(key, "awFakeCode¿¿")