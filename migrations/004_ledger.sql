-- Ledger entries replace the free-text notes on invoices.
ALTER TABLE invoices DROP COLUMN notes;
ALTER TABLE invoices ADD COLUMN ledger_ref TEXT NOT NULL;

CREATE TABLE ledger_entries (
    id INTEGER PRIMARY KEY,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    amount REAL NOT NULL,
    created_at TEXT
);
