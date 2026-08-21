"""Расчёт цены заказа — «медленный путь», который и должен закрывать кэш.

Цена собирается из журнала `price_events`: берём рыночное среднее по валюте
и последние компоненты по конкретному заказу, затем дописываем компоненты
текущего расчёта.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, datetime
from typing import Any

from db import pool

# Сколько строк пишется в журнал на один расчёт: по строке на каждую пару
# «позиция заказа × применённое правило тарификации».
PRICE_COMPONENTS = int(os.getenv("PRICE_COMPONENTS", "200"))

COMPONENT_NAMES = (
    "base",
    "discount",
    "tax",
    "shipping",
    "fx_spread",
    "loyalty",
    "fee",
    "rounding",
)


def compute_price(order_id: str, currency: str) -> dict[str, Any]:
    with pool.connection() as conn:
        market = conn.execute(
            """
            SELECT count(*) AS samples,
                   coalesce(avg(amount), 0) AS avg_amount,
                   count(DISTINCT order_id) AS orders
            FROM price_events
            WHERE currency = %s
            """,
            (currency,),
        ).fetchone()

        recent = conn.execute(
            """
            SELECT component, amount
            FROM price_events
            WHERE order_id = %s
            ORDER BY ts DESC
            LIMIT 20
            """,
            (order_id,),
        ).fetchall()

        rng = random.Random(order_id)
        now = datetime.now(UTC)
        rows = [
            (
                now,
                order_id,
                currency,
                f"item{i // len(COMPONENT_NAMES):02d}:{COMPONENT_NAMES[i % len(COMPONENT_NAMES)]}",
                round(rng.uniform(1.0, 900.0), 2),
            )
            for i in range(PRICE_COMPONENTS)
        ]
        with (
            conn.cursor() as cur,
            cur.copy("COPY price_events (ts, order_id, currency, component, amount) FROM STDIN") as copy,
        ):
            for row in rows:
                copy.write_row(row)

    samples, avg_amount, orders = market
    total = round(sum(row[4] for row in rows), 2)
    return {
        "order_id": order_id,
        "currency": currency,
        "total": total,
        "components": [{"name": row[3], "amount": row[4]} for row in rows[:8]],
        "market_reference": {
            "samples": samples,
            "orders": orders,
            "avg_amount": round(float(avg_amount), 2),
        },
        "recent_components": [{"name": name, "amount": amount} for name, amount in recent[:5]],
    }
