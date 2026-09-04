"""Criptografa CPF e adiciona hash de busca do cliente.

Revision ID: 20260904_0002
Revises: 20260904_0001
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.customer_data import decrypt_cpf, protect_customer


revision: str = "20260904_0002"
down_revision: Union[str, Sequence[str], None] = "20260904_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("customer_lookup_hash", sa.String(64), nullable=True))
    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, customer_kind, customer_value FROM orders")).mappings()
    for row in rows:
        plain_value = decrypt_cpf(row["customer_value"]) if row["customer_kind"] == "cpf" else row["customer_value"]
        protected, digest = protect_customer(row["customer_kind"], plain_value)
        bind.execute(
            sa.text("UPDATE orders SET customer_value = :value, customer_lookup_hash = :digest WHERE id = :id"),
            {"value": protected, "digest": digest, "id": row["id"]},
        )
    op.alter_column("orders", "customer_lookup_hash", nullable=False)
    op.create_index("ix_orders_customer_lookup_hash", "orders", ["customer_lookup_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT id, customer_value FROM orders WHERE customer_kind = 'cpf'")
    ).mappings()
    for row in rows:
        bind.execute(
            sa.text("UPDATE orders SET customer_value = :value WHERE id = :id"),
            {"value": decrypt_cpf(row["customer_value"]), "id": row["id"]},
        )
    op.drop_index("ix_orders_customer_lookup_hash", table_name="orders")
    op.drop_column("orders", "customer_lookup_hash")

