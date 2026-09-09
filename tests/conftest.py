from __future__ import annotations

from pathlib import Path

import duckdb
import pytest


@pytest.fixture
def source_db(tmp_path: Path) -> Path:
    """A miniature operational database with the same shape model2data produces."""
    path = tmp_path / "webshop.duckdb"
    con = duckdb.connect(str(path))
    con.execute("create schema raw")
    con.execute(
        """
        create table raw.customers as
        select * from (values
            (1, 'Ann', 'Peeters', 'ann@example.be', 'Gent', 'Belgium', 'consumer', true,
             timestamp '2026-01-01 09:00', timestamp '2026-01-01 09:00'),
            (2, 'Bart', 'Claes', 'bart@example.be', 'Leuven', 'Belgium', 'business', false,
             timestamp '2026-02-01 09:00', timestamp '2026-02-01 09:00')
        ) t(id, first_name, last_name, email, city, country, segment, is_marketing_opt_in,
            created_at, updated_at)
        """
    )
    con.execute(
        """
        create table raw.products as
        select * from (values
            (1, '5400000000017', 'ethiopia', 'light', 'beans', 250, 1450, 650, true,
             timestamp '2026-01-01', timestamp '2026-01-01')
        ) t(id, sku, origin, roast, category, weight_grams, unit_price_cents, cost_cents,
            is_active, created_at, updated_at)
        """
    )
    con.execute(
        """
        create table raw.orders as
        select * from (values
            (10, 1, 'delivered', 'web', timestamp '2026-03-01 10:00', timestamp '2026-03-02 10:00',
             timestamp '2026-03-04 10:00', 'Gent', 'Belgium',
             timestamp '2026-03-01 10:00', timestamp '2026-03-04 10:00'),
            (11, 2, 'pending', 'store', timestamp '2026-03-05 10:00', null, null, 'Leuven',
             'Belgium', timestamp '2026-03-05 10:00', timestamp '2026-03-05 10:00')
        ) t(id, customer_id, status, channel, ordered_at, shipped_at, delivered_at, shipping_city,
            shipping_country, created_at, updated_at)
        """
    )
    con.execute(
        """
        create table raw.order_items as
        select * from (values
            (100, 10, 1, 2, 1450, 0),
            (101, 11, 1, 1, 1450, 100)
        ) t(id, order_id, product_id, quantity, unit_price_cents, discount_cents)
        """
    )
    con.close()
    return path
