PRAGMA foreign_keys = ON;

-- ============================================================
-- MASTERPARK - ESQUEMA RELACIONAL (SQLite / portável p/ PgSQL)
-- Todos os valores monetários em CENTAVOS (INTEGER).
-- Datas/horas em UTC ISO-8601.
-- ============================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version      INTEGER PRIMARY KEY,
    applied_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    legal_name   TEXT NOT NULL DEFAULT '',
    cnpj         TEXT UNIQUE,
    address      TEXT DEFAULT '',
    phone        TEXT DEFAULT '',
    whatsapp     TEXT DEFAULT '',
    email        TEXT DEFAULT '',
    logo_path    TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    updated_at   TEXT
);

CREATE TABLE IF NOT EXISTS parking_lots (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    name            TEXT NOT NULL,
    code            TEXT NOT NULL,
    address         TEXT DEFAULT '',
    phone           TEXT DEFAULT '',
    opening_time    TEXT DEFAULT '07:00',
    closing_time    TEXT DEFAULT '22:00',
    tolerance_minutes INTEGER DEFAULT 10,
    currency        TEXT DEFAULT 'BRL',
    is_default      INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS parking_sectors (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id    INTEGER NOT NULL REFERENCES parking_lots(id),
    name      TEXT NOT NULL,
    color     TEXT DEFAULT '#4C6FFF',
    floor     INTEGER DEFAULT 1,
    sort      INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS parking_spaces (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id             INTEGER NOT NULL REFERENCES parking_lots(id),
    sector_id          INTEGER REFERENCES parking_sectors(id),
    code               TEXT NOT NULL,
    space_type         TEXT NOT NULL DEFAULT 'CARRO',
    state              TEXT NOT NULL DEFAULT 'LIVRE',
    monthly_contract_id INTEGER,
    notes              TEXT DEFAULT '',
    active         INTEGER NOT NULL DEFAULT 1,
    UNIQUE(lot_id, code)
  );

CREATE TABLE IF NOT EXISTS roles (
    code         TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    is_system    INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS permissions (
    code     TEXT PRIMARY KEY,
    label    TEXT NOT NULL,
    module   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permissions (
    role_code      TEXT NOT NULL REFERENCES roles(code),
    permission_code TEXT NOT NULL REFERENCES permissions(code),
    PRIMARY KEY (role_code, permission_code)
);

CREATE TABLE IF NOT EXISTS users (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    username             TEXT NOT NULL UNIQUE,
    name                 TEXT NOT NULL,
    password_hash        TEXT NOT NULL,
    salt                 TEXT NOT NULL,
    role_code            TEXT REFERENCES roles(code),
    is_active            INTEGER DEFAULT 1,
    must_change_password INTEGER DEFAULT 0,
    terminal             TEXT DEFAULT '',
    created_at           TEXT NOT NULL,
    last_login_at        TEXT,
    failed_attempts      INTEGER DEFAULT 0,
    locked_until         TEXT
);

CREATE TABLE IF NOT EXISTS user_permissions (
    user_id         INTEGER NOT NULL REFERENCES users(id),
    permission_code TEXT NOT NULL REFERENCES permissions(code),
    allowed         INTEGER DEFAULT 1,
    PRIMARY KEY (user_id, permission_code)
);

CREATE TABLE IF NOT EXISTS customers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    person_type   TEXT NOT NULL DEFAULT 'FISICA',
    name          TEXT NOT NULL,
    legal_name    TEXT DEFAULT '',
    cpf           TEXT,
    cnpj          TEXT,
    phone         TEXT DEFAULT '',
    whatsapp      TEXT DEFAULT '',
    email         TEXT DEFAULT '',
    address       TEXT DEFAULT '',
    city          TEXT DEFAULT '',
    state         TEXT DEFAULT '',
    notes         TEXT DEFAULT '',
    is_blacklisted INTEGER DEFAULT 0,
    created_at    TEXT NOT NULL,
    updated_at    TEXT,
      active         INTEGER NOT NULL DEFAULT 1
  );

CREATE TABLE IF NOT EXISTS vehicles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER REFERENCES customers(id),
    plate         TEXT NOT NULL,
    model         TEXT DEFAULT '',
    brand         TEXT DEFAULT '',
    color         TEXT DEFAULT '',
    category      TEXT NOT NULL DEFAULT 'CARRO',
    is_blocked    INTEGER DEFAULT 0,
    is_vip        INTEGER DEFAULT 0,
    notes         TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_vehicles_plate ON vehicles(plate);

CREATE TABLE IF NOT EXISTS tariffs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id           INTEGER REFERENCES parking_lots(id),
    name             TEXT NOT NULL,
    vehicle_category TEXT DEFAULT '*',
    sector_id        INTEGER,
    period_type      TEXT NOT NULL DEFAULT 'NORMAL',
    starts_at_str    TEXT DEFAULT '00:00',
    ends_at_str      TEXT DEFAULT '23:59',
    days_mask        TEXT DEFAULT '0111110',
    valid_from       TEXT,
    valid_to         TEXT,
    active           INTEGER DEFAULT 1,
    is_default       INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tariff_rules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    tariff_id   INTEGER NOT NULL REFERENCES tariffs(id),
    minutes_from INTEGER NOT NULL DEFAULT 0,
    minutes_to  INTEGER,
    rule_type   TEXT NOT NULL,
    value       INTEGER DEFAULT 0,
    sort        INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tickets (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id            INTEGER NOT NULL REFERENCES parking_lots(id),
    number            TEXT NOT NULL UNIQUE,
    status            TEXT NOT NULL DEFAULT 'ATIVO',
    vehicle_id        INTEGER REFERENCES vehicles(id),
    customer_id       INTEGER REFERENCES customers(id),
    plate             TEXT NOT NULL,
    vehicle_category  TEXT NOT NULL DEFAULT 'CARRO',
    entry_at          TEXT NOT NULL,
    exit_at           TEXT,
    parking_space_id  INTEGER REFERENCES parking_spaces(id),
    entry_user_id     INTEGER REFERENCES users(id),
    exit_user_id      INTEGER REFERENCES users(id),
    terminal_entry    TEXT DEFAULT '',
    terminal_exit     TEXT DEFAULT '',
    qr_data           TEXT DEFAULT '',
    barcode_data      TEXT DEFAULT '',
    total_minutes     INTEGER,
    tariff_id         INTEGER REFERENCES tariffs(id),
    base_value        INTEGER DEFAULT 0,
    discount_value    INTEGER DEFAULT 0,
    final_value       INTEGER DEFAULT 0,
    cancel_reason     TEXT DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_plate ON tickets(plate);
CREATE INDEX IF NOT EXISTS idx_tickets_entry ON tickets(entry_at);

CREATE TABLE IF NOT EXISTS parking_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id  INTEGER REFERENCES tickets(id),
    space_id   INTEGER REFERENCES parking_spaces(id),
    entry_at   TEXT NOT NULL,
    exit_at    TEXT,
    status     TEXT NOT NULL DEFAULT 'ATIVA'
);

CREATE TABLE IF NOT EXISTS payment_methods (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id        INTEGER REFERENCES tickets(id),
    monthly_payment_id INTEGER REFERENCES monthly_payments(id),
    payment_method   TEXT NOT NULL REFERENCES payment_methods(code),
    status           TEXT NOT NULL DEFAULT 'SOLICITADO',
    value            INTEGER NOT NULL,
    received_at      TEXT,
    received_value   INTEGER,
    operator_id      INTEGER REFERENCES users(id),
    cash_register_id INTEGER REFERENCES cash_registers(id),
    pos_tid          TEXT DEFAULT '',
    external_ref     TEXT DEFAULT '',
    agreement_id     INTEGER REFERENCES agreements(id),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cash_registers (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id             INTEGER REFERENCES parking_lots(id),
    operator_id        INTEGER REFERENCES users(id),
    opened_at          TEXT NOT NULL,
    closed_at          TEXT,
    opening_value      INTEGER DEFAULT 0,
    closing_expected   INTEGER,
    closing_informed   INTEGER,
    closing_difference INTEGER,
    difference_justification TEXT DEFAULT '',
    status             TEXT NOT NULL DEFAULT 'ABERTO'
);

CREATE TABLE IF NOT EXISTS cash_movements (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    cash_register_id INTEGER REFERENCES cash_registers(id),
    payment_id       INTEGER REFERENCES payments(id),
    kind             TEXT NOT NULL,
    value            INTEGER NOT NULL,
    description      TEXT DEFAULT '',
    operator_id      INTEGER REFERENCES users(id),
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS monthly_customers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL REFERENCES customers(id),
    plan_name     TEXT DEFAULT 'Mensalista',
    status        TEXT NOT NULL DEFAULT 'ATIVO',
    start_at      TEXT NOT NULL,
    end_at        TEXT,
    monthly_value INTEGER NOT NULL,
    billing_day   INTEGER DEFAULT 1,
    created_at    TEXT NOT NULL,
    updated_at    TEXT,
      active         INTEGER NOT NULL DEFAULT 1
  );

CREATE TABLE IF NOT EXISTS monthly_contracts (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    monthly_customer_id INTEGER NOT NULL REFERENCES monthly_customers(id),
    vehicle_id          INTEGER REFERENCES vehicles(id),
    space_id            INTEGER REFERENCES parking_spaces(id),
    start_at            TEXT NOT NULL,
    end_at              TEXT,
    value               INTEGER DEFAULT 0,
    renewal_mode        TEXT DEFAULT 'AUTOMATICO'
);

CREATE TABLE IF NOT EXISTS monthly_payments (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    monthly_customer_id INTEGER NOT NULL REFERENCES monthly_customers(id),
    due_date            TEXT NOT NULL,
    reference           TEXT NOT NULL,
    value               INTEGER NOT NULL,
    status              TEXT NOT NULL DEFAULT 'PENDENTE',
    paid_at             TEXT,
    paid_value          INTEGER,
    payment_id          INTEGER,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS agreements (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id          INTEGER REFERENCES parking_lots(id),
    name            TEXT NOT NULL,
    cnpj            TEXT DEFAULT '',
    agreement_type  TEXT DEFAULT 'EMPRESA',
    discount_type   TEXT NOT NULL DEFAULT 'PERCENTUAL',
    discount_value  INTEGER DEFAULT 0,
    discount_hours  INTEGER DEFAULT 0,
    validation_type TEXT DEFAULT 'VALET',
    daily_max       INTEGER DEFAULT 0,
    monthly_max     INTEGER DEFAULT 0,
    active          INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS reservations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id          INTEGER REFERENCES parking_lots(id),
    space_id        INTEGER REFERENCES parking_spaces(id),
    customer_id     INTEGER REFERENCES customers(id),
    vehicle_id      INTEGER REFERENCES vehicles(id),
    start_at        TEXT NOT NULL,
    end_at          TEXT NOT NULL,
    tariff_value    INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'PENDENTE',
    created_by      INTEGER REFERENCES users(id),
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS discounts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id    INTEGER REFERENCES tickets(id),
    kind         TEXT NOT NULL,
    value        INTEGER DEFAULT 0,
    percent      REAL DEFAULT 0,
    operator_id  INTEGER REFERENCES users(id),
    agreement_id INTEGER REFERENCES agreements(id),
    reason       TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incidents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id      INTEGER REFERENCES parking_lots(id),
    ticket_id   INTEGER REFERENCES tickets(id),
    kind        TEXT NOT NULL,
    severity    TEXT DEFAULT 'BAIXA',
    description TEXT NOT NULL,
    operator_id INTEGER REFERENCES users(id),
    status      TEXT DEFAULT 'ABERTO',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS incident_attachments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id INTEGER NOT NULL REFERENCES incidents(id),
    file_path   TEXT NOT NULL,
    kind        TEXT DEFAULT 'IMAGEM'
);

CREATE TABLE IF NOT EXISTS devices (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id      INTEGER REFERENCES parking_lots(id),
    kind        TEXT NOT NULL,
    name        TEXT NOT NULL,
    model       TEXT DEFAULT '',
    manufacturer TEXT DEFAULT '',
    connection  TEXT DEFAULT 'DEMO',
    endpoint    TEXT DEFAULT '',
    status      TEXT DEFAULT 'INDISPONIVEL',
    is_simulated INTEGER DEFAULT 1,
    last_seen   TEXT
);

CREATE TABLE IF NOT EXISTS cameras (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id      INTEGER REFERENCES parking_lots(id),
    name        TEXT NOT NULL,
    brand       TEXT DEFAULT '',
    protocol    TEXT DEFAULT 'DEMO',
    url         TEXT DEFAULT '',
    direction   TEXT DEFAULT 'ENTRADA',
    status      TEXT DEFAULT 'INDISPONIVEL',
    is_simulated INTEGER DEFAULT 1,
    last_event  TEXT
);

CREATE TABLE IF NOT EXISTS access_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id      INTEGER REFERENCES parking_lots(id),
    camera_id   INTEGER REFERENCES cameras(id),
    plate       TEXT,
    confidence  REAL,
    image_path  TEXT DEFAULT '',
    direction   TEXT,
    event_at    TEXT NOT NULL,
    matched_vehicle_id INTEGER,
    matched_ticket_id  INTEGER
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER,
    username    TEXT DEFAULT '',
    terminal    TEXT DEFAULT '',
    ip          TEXT DEFAULT '',
    action      TEXT NOT NULL,
    entity      TEXT DEFAULT '',
    entity_id   TEXT DEFAULT '',
    old_value   TEXT DEFAULT '',
    new_value   TEXT DEFAULT '',
    reason      TEXT DEFAULT '',
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    lot_id     INTEGER,
    level      TEXT DEFAULT 'INFO',
    code       TEXT DEFAULT '',
    title      TEXT NOT NULL,
    message    TEXT DEFAULT '',
    read_at    TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS licenses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    license_key     TEXT UNIQUE,
    customer_name   TEXT,
    cnpj            TEXT,
    product         TEXT DEFAULT 'MASTERPARK',
    version         TEXT DEFAULT '1.0.0',
    plan            TEXT DEFAULT 'PROFESSIONAL',
    activated_at    TEXT,
    expires_at      TEXT,
    lifetime        INTEGER DEFAULT 0,
    duracao         TEXT DEFAULT '',
    terminals       INTEGER DEFAULT 1,
    spaces          INTEGER DEFAULT 0,
    features        TEXT DEFAULT '[]',
    installation_id TEXT,
    hw_anchor       TEXT,
    signature       TEXT NOT NULL,
    status          TEXT DEFAULT 'INATIVA',
    created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS license_activations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    license_id      INTEGER REFERENCES licenses(id),
    installation_id TEXT NOT NULL,
    activated_at    TEXT NOT NULL,
    machine_name    TEXT DEFAULT '',
    hw_id           TEXT DEFAULT '',
    mode            TEXT DEFAULT 'ONLINE'
);

CREATE TABLE IF NOT EXISTS system_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS backups (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    path       TEXT NOT NULL,
    size       INTEGER DEFAULT 0,
    kind       TEXT DEFAULT 'MANUAL',
    status     TEXT DEFAULT 'OK',
    note       TEXT DEFAULT '',
    created_at TEXT NOT NULL
);

-- Formas de pagamento padrão
INSERT OR IGNORE INTO payment_methods (code, name) VALUES
 ('DINHEIRO','Dinheiro'),
 ('PIX','Pix'),
 ('CREDITO','Cartão de Crédito'),
 ('DEBITO','Cartão de Débito'),
 ('TRANSFERENCIA','Transferência'),
 ('CONVENIO','Convênio'),
 ('OUTRO','Outro');