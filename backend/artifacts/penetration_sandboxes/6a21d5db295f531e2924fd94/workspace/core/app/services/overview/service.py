from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from core.app.core.cache import get_cached, invalidate_cached, set_cached
from core.app.core.distributed_lock import distributed_lock
from core.app.models.orders.status import OrderStatus
from core.app.repositories.analytics.repository import (
    OVERVIEW_SNAPSHOT_COLLECTION as _OVERVIEW_SNAPSHOT_COLLECTION,
    OverviewSnapshotRepository,
)

MAX_CHART_BUCKETS = 8
DENSE_CHART_BUCKET_LIMIT = 400
logger = logging.getLogger("commerceops.overview.service")

OVERVIEW_CACHE_NAMESPACE = "overview:owner:v2"
OVERVIEW_CACHE_TTL_SECONDS = 45
OVERVIEW_STALE_CACHE_NAMESPACE = "overview:owner:stale:v2"
OVERVIEW_STALE_CACHE_TTL_SECONDS = 86400
OVERVIEW_SNAPSHOT_COLLECTION = _OVERVIEW_SNAPSHOT_COLLECTION
OVERVIEW_SNAPSHOT_MAX_AGE_SECONDS = OVERVIEW_STALE_CACHE_TTL_SECONDS
OVERVIEW_LOCK_TTL_SECONDS = 30
OVERVIEW_LOCK_WAIT_SECONDS = 20
OVERVIEW_LOCK_POLL_SECONDS = 0.1
EPOCH = datetime.fromtimestamp(0, tz=UTC)
RETURNED_STATUSES = {OrderStatus.RETURNED, OrderStatus.PARTIALLY_RETURNED}
SOURCE_PLATFORMS = {
    "facebook",
    "instagram",
    "tiktok",
    "google",
    "whatsapp",
    "direct",
    "organic",
}
ANALYTICS_PLATFORM_KEYS = (
    "facebook",
    "instagram",
    "tiktok",
    "google",
    "direct",
    "organic",
)
PLATFORM_LABELS = {
    "facebook": "Facebook",
    "instagram": "Instagram",
    "tiktok": "TikTok",
    "google": "Google",
    "whatsapp": "WhatsApp",
    "woocommerce": "WooCommerce",
    "shopify": "Shopify",
    "organic": "Organic",
    "direct": "Direct",
    "unknown": "Unknown",
}


async def owner_overview(
    database: Any,
    *,
    workspace_id: str,
    store_id: str | None,
    permissions: frozenset[str],
    analytics_range: str | None = None,
    date_range: tuple[datetime, datetime] | None = None,
    woo_sync_service: Any | None = None,
    bosta_integration_service: Any | None = None,
    shopify_service: Any | None = None,
) -> dict[str, Any]:
    include_team = "team.manage" in permissions
    cache_key_parts = _owner_overview_cache_key_parts(
        workspace_id,
        store_id,
        include_team,
        analytics_range=analytics_range,
        date_range=date_range,
    )
    cached = await get_cached(OVERVIEW_CACHE_NAMESPACE, *cache_key_parts)
    if cached is not None:
        return cached
    snapshot = await _get_owner_overview_snapshot(database, cache_key_parts)
    if snapshot is not None:
        result, needs_refresh = snapshot
        await _cache_owner_overview_redis(cache_key_parts, result)
        if needs_refresh:
            _schedule_owner_overview_refresh(
                database,
                cache_key_parts,
                workspace_id=workspace_id,
                store_id=store_id,
                include_team=include_team,
                date_range=date_range,
                woo_sync_service=woo_sync_service,
                bosta_integration_service=bosta_integration_service,
                shopify_service=shopify_service,
            )
        return result

    lock_scope = ":".join(cache_key_parts)
    async with distributed_lock(
        "overview:owner",
        workspace_id=lock_scope,
        ttl_seconds=OVERVIEW_LOCK_TTL_SECONDS,
    ) as acquired:
        if acquired:
            cached = await get_cached(OVERVIEW_CACHE_NAMESPACE, *cache_key_parts)
            if cached is not None:
                return cached
            snapshot = await _get_owner_overview_snapshot(database, cache_key_parts)
            if snapshot is not None:
                result, needs_refresh = snapshot
                await _cache_owner_overview_redis(cache_key_parts, result)
                if needs_refresh:
                    _schedule_owner_overview_refresh(
                        database,
                        cache_key_parts,
                        workspace_id=workspace_id,
                        store_id=store_id,
                        include_team=include_team,
                        date_range=date_range,
                        woo_sync_service=woo_sync_service,
                        bosta_integration_service=bosta_integration_service,
                        shopify_service=shopify_service,
                    )
                return result
            result = await _build_owner_overview(
                database,
                workspace_id=workspace_id,
                store_id=store_id,
                include_team=include_team,
                date_range=date_range,
                woo_sync_service=woo_sync_service,
                bosta_integration_service=bosta_integration_service,
                shopify_service=shopify_service,
            )
            await _cache_owner_overview(database, cache_key_parts, result)
            return result

        stale = await get_cached(OVERVIEW_STALE_CACHE_NAMESPACE, *cache_key_parts)
        if stale is not None:
            return stale

        attempts = int(OVERVIEW_LOCK_WAIT_SECONDS / OVERVIEW_LOCK_POLL_SECONDS)
        for _ in range(attempts):
            await asyncio.sleep(OVERVIEW_LOCK_POLL_SECONDS)
            cached = await get_cached(OVERVIEW_CACHE_NAMESPACE, *cache_key_parts)
            if cached is not None:
                return cached
        stale = await get_cached(OVERVIEW_STALE_CACHE_NAMESPACE, *cache_key_parts)
        if stale is not None:
            return stale
        snapshot = await _get_owner_overview_snapshot(database, cache_key_parts)
        if snapshot is not None:
            result, needs_refresh = snapshot
            await _cache_owner_overview_redis(cache_key_parts, result)
            if needs_refresh:
                _schedule_owner_overview_refresh(
                    database,
                    cache_key_parts,
                    workspace_id=workspace_id,
                    store_id=store_id,
                    include_team=include_team,
                    date_range=date_range,
                    woo_sync_service=woo_sync_service,
                    bosta_integration_service=bosta_integration_service,
                    shopify_service=shopify_service,
                )
            return result

    result = await _build_owner_overview(
        database,
        workspace_id=workspace_id,
        store_id=store_id,
        include_team=include_team,
        date_range=date_range,
        woo_sync_service=woo_sync_service,
        bosta_integration_service=bosta_integration_service,
        shopify_service=shopify_service,
    )
    await _cache_owner_overview(database, cache_key_parts, result)
    return result


async def _build_owner_overview(
    database: Any,
    *,
    workspace_id: str,
    store_id: str | None,
    include_team: bool,
    date_range: tuple[datetime, datetime] | None,
    woo_sync_service: Any | None,
    bosta_integration_service: Any | None,
    shopify_service: Any | None,
) -> dict[str, Any]:
    orders = database["orders"]
    products = database["products"]
    customers = database["customers"]
    memberships = database["memberships"]

    customer_query = _workspace_store_query(workspace_id, store_id)
    order_summary_task = asyncio.create_task(
        _order_summary(orders, products, workspace_id, store_id, date_range=date_range)
    )
    product_summary_task = asyncio.create_task(_product_summary(products, workspace_id, store_id))
    customer_total_task = asyncio.ensure_future(customers.count_documents(customer_query))
    repeat_customer_total_task = asyncio.ensure_future(
        customers.count_documents({**customer_query, "total_orders": {"$gt": 1}})
    )
    team_summary_task = (
        asyncio.create_task(_team_summary(memberships, workspace_id))
        if include_team
        else None
    )
    integrations_task = asyncio.create_task(
        _integration_summary(
            workspace_id,
            woo_sync_service=woo_sync_service,
            bosta_integration_service=bosta_integration_service,
            shopify_service=shopify_service,
        )
    )
    order_summary, product_summary, customer_total, repeat_customer_total, integrations = await asyncio.gather(
        order_summary_task,
        product_summary_task,
        customer_total_task,
        repeat_customer_total_task,
        integrations_task,
    )
    team_summary = await team_summary_task if team_summary_task else _empty_team_summary()

    result = {
        "totals": {
            "orders": order_summary["orders"],
            "products": product_summary["products"],
            "activeProducts": product_summary["activeProducts"],
            "customers": customer_total,
            "repeatCustomers": repeat_customer_total,
            "teamMembers": team_summary["teamMembers"],
            "activeTeamMembers": team_summary["activeTeamMembers"],
            "permissionSections": team_summary["permissionSections"],
            "connectedIntegrations": sum(
                1 for item in integrations if item["status"] == "connected"
            ),
            "deliveredOrders": order_summary["deliveredOrders"],
            "cancelledOrders": order_summary["cancelledOrders"],
            "returnedOrders": order_summary["returnedOrders"],
            "revenueByCurrency": order_summary["revenueByCurrency"],
        },
        "trend": order_summary["trend"],
        "topProducts": order_summary["topProducts"],
        "latestOrders": order_summary["latestOrders"],
        "platforms": order_summary["platforms"],
        "roleSummary": team_summary["roleSummary"],
        "integrations": integrations,
    }
    return result


async def _cache_owner_overview(
    database: Any,
    cache_key_parts: tuple[str, ...],
    result: dict[str, Any],
) -> None:
    await _cache_owner_overview_redis(cache_key_parts, result)
    await _persist_owner_overview_snapshot(database, cache_key_parts, result)


async def _cache_owner_overview_redis(
    cache_key_parts: tuple[str, ...],
    result: dict[str, Any],
) -> None:
    await set_cached(
        OVERVIEW_CACHE_NAMESPACE,
        *cache_key_parts,
        value=result,
        ttl_seconds=OVERVIEW_CACHE_TTL_SECONDS,
    )
    await set_cached(
        OVERVIEW_STALE_CACHE_NAMESPACE,
        *cache_key_parts,
        value=result,
        ttl_seconds=OVERVIEW_STALE_CACHE_TTL_SECONDS,
    )


def _owner_overview_snapshot_id(cache_key_parts: tuple[str, ...]) -> str:
    digest = hashlib.sha256("\x1f".join(cache_key_parts).encode("utf-8")).hexdigest()
    return f"owner:{cache_key_parts[0]}:{digest[:24]}"


def _owner_overview_cache_key_parts(
    workspace_id: str,
    store_id: str | None,
    include_team: bool,
    *,
    analytics_range: str | None,
    date_range: tuple[datetime, datetime] | None,
) -> tuple[str, ...]:
    base = (workspace_id, store_id or "", "team" if include_team else "self")
    if not analytics_range and date_range is None:
        return base
    if analytics_range:
        if analytics_range in {"today", "yesterday"}:
            return (*base, f"range:{analytics_range}:hourly:v1")
        return (*base, f"range:{analytics_range}")
    assert date_range is not None
    return (*base, f"range:{_cache_date_token(date_range[0])}:{_cache_date_token(date_range[1])}")


def _cache_date_token(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


async def _persist_owner_overview_snapshot(
    database: Any,
    cache_key_parts: tuple[str, ...],
    result: dict[str, Any],
) -> None:
    now = datetime.now(UTC)
    try:
        await OverviewSnapshotRepository(database).upsert_snapshot(
            snapshot_id=_owner_overview_snapshot_id(cache_key_parts),
            cache_key_parts=cache_key_parts,
            data=result,
            built_at=now,
        )
    except Exception:
        logger.warning("Overview snapshot persistence failed", exc_info=True)


async def _get_owner_overview_snapshot(
    database: Any,
    cache_key_parts: tuple[str, ...],
) -> tuple[dict[str, Any], bool] | None:
    try:
        document = await OverviewSnapshotRepository(database).get_snapshot(
            snapshot_id=_owner_overview_snapshot_id(cache_key_parts)
        )
    except Exception:
        logger.warning("Overview snapshot read failed", exc_info=True)
        return None
    if not document or not isinstance(document.get("data"), dict):
        return None
    built_at = _datetime(document.get("built_at"))
    age_seconds = (datetime.now(UTC) - built_at).total_seconds()
    if age_seconds > OVERVIEW_SNAPSHOT_MAX_AGE_SECONDS:
        return None
    return document["data"], age_seconds > OVERVIEW_CACHE_TTL_SECONDS


def _schedule_owner_overview_refresh(
    database: Any,
    cache_key_parts: tuple[str, ...],
    *,
    workspace_id: str,
    store_id: str | None,
    include_team: bool,
    date_range: tuple[datetime, datetime] | None,
    woo_sync_service: Any | None,
    bosta_integration_service: Any | None,
    shopify_service: Any | None,
) -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    task = loop.create_task(
        _refresh_owner_overview_snapshot(
            database,
            cache_key_parts,
            workspace_id=workspace_id,
            store_id=store_id,
            include_team=include_team,
            date_range=date_range,
            woo_sync_service=woo_sync_service,
            bosta_integration_service=bosta_integration_service,
            shopify_service=shopify_service,
        )
    )
    task.add_done_callback(_log_owner_overview_refresh_failure)


async def _refresh_owner_overview_snapshot(
    database: Any,
    cache_key_parts: tuple[str, ...],
    *,
    workspace_id: str,
    store_id: str | None,
    include_team: bool,
    date_range: tuple[datetime, datetime] | None,
    woo_sync_service: Any | None,
    bosta_integration_service: Any | None,
    shopify_service: Any | None,
) -> None:
    lock_scope = ":".join(cache_key_parts)
    async with distributed_lock(
        "overview:owner:refresh",
        workspace_id=lock_scope,
        ttl_seconds=OVERVIEW_LOCK_TTL_SECONDS,
    ) as acquired:
        if not acquired:
            return
        result = await _build_owner_overview(
            database,
            workspace_id=workspace_id,
            store_id=store_id,
            include_team=include_team,
            date_range=date_range,
            woo_sync_service=woo_sync_service,
            bosta_integration_service=bosta_integration_service,
            shopify_service=shopify_service,
        )
        if not any((woo_sync_service, bosta_integration_service, shopify_service)):
            result = await _preserve_snapshot_integration_summary(database, cache_key_parts, result)
        await _cache_owner_overview(database, cache_key_parts, result)


def _log_owner_overview_refresh_failure(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.warning(
            "Overview snapshot refresh failed",
            exc_info=(type(error), error, error.__traceback__),
        )


async def invalidate_overview_cache(workspace_id: str) -> None:
    # Keep the stale namespace so concurrent readers can avoid a cold-cache stampede.
    await invalidate_cached(OVERVIEW_CACHE_NAMESPACE, workspace_id)


def schedule_overview_snapshot_refresh(
    database: Any,
    *,
    workspace_id: str,
    store_id: str | None = None,
    woo_sync_service: Any | None = None,
    bosta_integration_service: Any | None = None,
    shopify_service: Any | None = None,
) -> None:
    """Prewarm owner overview snapshots after writes without blocking the write path."""
    if database.__class__.__name__ == "InMemoryDatabase":
        return
    scopes = [None]
    if store_id:
        scopes.append(store_id)
    for scope_store_id in scopes:
        for include_team in (False, True):
            cache_key_parts = (
                workspace_id,
                scope_store_id or "",
                "team" if include_team else "self",
            )
            _schedule_owner_overview_refresh(
                database,
                cache_key_parts,
                workspace_id=workspace_id,
                store_id=scope_store_id,
                include_team=include_team,
                date_range=None,
                woo_sync_service=woo_sync_service,
                bosta_integration_service=bosta_integration_service,
                shopify_service=shopify_service,
            )


async def _preserve_snapshot_integration_summary(
    database: Any,
    cache_key_parts: tuple[str, ...],
    result: dict[str, Any],
) -> dict[str, Any]:
    snapshot = await _get_owner_overview_snapshot(database, cache_key_parts)
    if snapshot is None:
        return result
    previous, _ = snapshot
    integrations = previous.get("integrations")
    previous_totals = previous.get("totals")
    if isinstance(integrations, list):
        result["integrations"] = integrations
    if isinstance(previous_totals, dict):
        connected = previous_totals.get("connectedIntegrations")
        if isinstance(connected, int):
            result.setdefault("totals", {})["connectedIntegrations"] = connected
    return result


async def _order_summary(
    orders: Any,
    products: Any,
    workspace_id: str,
    store_id: str | None,
    *,
    date_range: tuple[datetime, datetime] | None = None,
) -> dict[str, Any]:
    query = _workspace_store_query(workspace_id, store_id, date_range=date_range)
    facet_rows = await (
        await orders.aggregate(
            [
                {"$match": query},
                {
                    "$facet": {
                        "totals": [
                            {
                                "$group": {
                                    "_id": None,
                                    "orders": {"$sum": 1},
                                    "deliveredOrders": {
                                    "$sum": {"$cond": [{"$eq": ["$status", OrderStatus.DELIVERED]}, 1, 0]},
                                },
                                "cancelledOrders": {
                                    "$sum": {"$cond": [{"$eq": ["$status", OrderStatus.CANCELLED]}, 1, 0]},
                                    },
                                    "returnedOrders": {
                                        "$sum": {
                                            "$cond": [
                                                {"$in": ["$status", list(RETURNED_STATUSES)]},
                                                1,
                                                0,
                                            ]
                                        },
                                    },
                                }
                            }
                        ],
                        "revenueByCurrency": [
                            {
                                "$group": {
                                    "_id": {"$ifNull": ["$currency", "EGP"]},
                                    "value": {"$sum": _number_expression("$total")},
                                }
                            },
                            {"$project": {"_id": 0, "currency": "$_id", "value": 1}},
                        ],
                        "bounds": [
                            {
                                "$group": {
                                    "_id": None,
                                    "first": {"$min": "$created_at"},
                                    "last": {"$max": "$created_at"},
                                }
                            }
                        ],
                    }
                },
            ]
        )
    ).to_list(length=1)
    facet = facet_rows[0] if facet_rows else {}
    totals = (facet.get("totals") or [{}])[0]
    bounds = (facet.get("bounds") or [{}])[0]
    if date_range is not None:
        first, last = date_range
        span_days = max(1, (last - first).days)
    else:
        first = _datetime(bounds.get("first"))
        last = _datetime(bounds.get("last"))
        span_days = max(1, (last - first).days + 1)
    use_hour = date_range is not None and span_days <= 1
    use_month = not use_hour and span_days > 45

    trend, top_products, latest_orders, platforms = await asyncio.gather(
        _trend_aggregate(
            orders,
            query,
            use_month=use_month,
            use_hour=use_hour,
            date_range=date_range,
        ),
        _top_products_aggregate(
            orders,
            products,
            query,
            workspace_id,
            store_id,
        ),
        _latest_orders_aggregate(orders, query),
        _platforms_aggregate(orders, query),
    )

    return {
        "orders": int(totals.get("orders") or 0),
        "deliveredOrders": int(totals.get("deliveredOrders") or 0),
        "cancelledOrders": int(totals.get("cancelledOrders") or 0),
        "returnedOrders": int(totals.get("returnedOrders") or 0),
        "revenueByCurrency": {
            str(row.get("currency") or "EGP"): _number(row.get("value"))
            for row in facet.get("revenueByCurrency") or []
        },
        "trend": trend,
        "topProducts": top_products,
        "latestOrders": latest_orders,
        "platforms": platforms,
    }


async def _product_summary(
    collection: Any,
    workspace_id: str,
    store_id: str | None,
) -> dict[str, int]:
    rows = await (
        await collection.aggregate(
            [
                {"$match": _workspace_store_query(workspace_id, store_id)},
                {
                    "$group": {
                        "_id": None,
                        "products": {"$sum": 1},
                        "activeProducts": {
                            "$sum": {
                                "$cond": [
                                    {"$eq": [{"$ifNull": ["$status", "active"]}, "active"]},
                                    1,
                                    0,
                                ]
                            }
                        },
                    }
                },
            ]
        )
    ).to_list(length=1)
    row = rows[0] if rows else {}
    return {
        "products": int(row.get("products") or 0),
        "activeProducts": int(row.get("activeProducts") or 0),
    }


async def _trend_aggregate(
    collection: Any,
    query: dict[str, Any],
    *,
    use_month: bool,
    use_hour: bool = False,
    date_range: tuple[datetime, datetime] | None = None,
) -> list[dict[str, Any]]:
    key_format = "%Y-%m" if use_month else "%Y-%m-%dT%H" if use_hour else "%Y-%m-%d"
    label_format = "%b %Y" if use_month else "%H:00" if use_hour else "%b %d"
    pipeline: list[dict[str, Any]] = [
        {"$match": query},
        {
            "$addFields": {
                "_overviewCreatedAt": {"$ifNull": ["$created_at", EPOCH]},
                "_overviewCurrency": {"$ifNull": ["$currency", "EGP"]},
            }
        },
        {
            "$group": {
                "_id": {
                    "bucket": _date_to_string(key_format, "$_overviewCreatedAt"),
                    "currency": "$_overviewCurrency",
                },
                "label": {
                    "$first": _date_to_string(label_format, "$_overviewCreatedAt")
                },
                "sort": {"$min": "$_overviewCreatedAt"},
                "orders": {"$sum": 1},
                "revenue": {"$sum": _number_expression("$total")},
            }
        },
        {
            "$group": {
                "_id": "$_id.bucket",
                "label": {"$first": "$label"},
                "sort": {"$min": "$sort"},
                "orders": {"$sum": "$orders"},
                "revenuePairs": {"$push": {"k": "$_id.currency", "v": "$revenue"}},
            }
        },
        {"$sort": {"sort": 1}},
    ]
    if date_range is None:
        pipeline.extend(
            ({"$sort": {"sort": -1}}, {"$limit": MAX_CHART_BUCKETS}, {"$sort": {"sort": 1}})
        )
    pipeline.append(
        {
            "$project": {
                "_id": 0,
                "bucket": "$_id",
                "label": 1,
                "orders": 1,
                "revenueByCurrency": {"$arrayToObject": "$revenuePairs"},
            }
        }
    )
    row_limit = DENSE_CHART_BUCKET_LIMIT if date_range is not None else MAX_CHART_BUCKETS
    rows = await (await collection.aggregate(pipeline)).to_list(length=row_limit)
    if date_range is None:
        return [_public_trend_row(row) for row in rows]
    return _dense_trend_rows(rows, date_range=date_range, use_month=use_month, use_hour=use_hour)


def _public_trend_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": str(row.get("label") or ""),
        "orders": int(row.get("orders") or 0),
        "revenueByCurrency": dict(row.get("revenueByCurrency") or {}),
    }


def _dense_trend_rows(
    rows: list[dict[str, Any]],
    *,
    date_range: tuple[datetime, datetime],
    use_month: bool,
    use_hour: bool,
) -> list[dict[str, Any]]:
    rows_by_bucket = {str(row.get("bucket") or ""): _public_trend_row(row) for row in rows}
    return [
        rows_by_bucket.get(
            bucket,
            {"label": label, "orders": 0, "revenueByCurrency": {}},
        )
        for bucket, label in _trend_bucket_labels(
            date_range,
            use_month=use_month,
            use_hour=use_hour,
        )
    ]


def _trend_bucket_labels(
    date_range: tuple[datetime, datetime],
    *,
    use_month: bool,
    use_hour: bool,
) -> list[tuple[str, str]]:
    start, end = date_range
    current = start.astimezone(UTC)
    end_utc = end.astimezone(UTC)
    if use_month:
        current = datetime(current.year, current.month, 1, tzinfo=UTC)
        buckets: list[tuple[str, str]] = []
        while current < end_utc and len(buckets) < DENSE_CHART_BUCKET_LIMIT:
            buckets.append((current.strftime("%Y-%m"), current.strftime("%b %Y")))
            current = (
                datetime(current.year + 1, 1, 1, tzinfo=UTC)
                if current.month == 12
                else datetime(current.year, current.month + 1, 1, tzinfo=UTC)
            )
        return buckets

    if use_hour:
        current = datetime(current.year, current.month, current.day, current.hour, tzinfo=UTC)
        buckets = []
        while current < end_utc and len(buckets) < DENSE_CHART_BUCKET_LIMIT:
            buckets.append((current.strftime("%Y-%m-%dT%H"), current.strftime("%H:00")))
            current += timedelta(hours=1)
        return buckets

    current = datetime(current.year, current.month, current.day, tzinfo=UTC)
    buckets = []
    while current < end_utc and len(buckets) < DENSE_CHART_BUCKET_LIMIT:
        buckets.append((current.strftime("%Y-%m-%d"), current.strftime("%b %d")))
        current += timedelta(days=1)
    return buckets


async def _top_products_aggregate(
    orders: Any,
    products: Any,
    query: dict[str, Any],
    workspace_id: str,
    store_id: str | None,
) -> list[dict[str, Any]]:
    product_match = _workspace_store_query(workspace_id, store_id)
    cursor = await orders.aggregate(
        [
            {"$match": query},
            {"$unwind": "$items"},
            {
                "$addFields": {
                    "_overviewProductId": {
                        "$trim": {
                            "input": {
                                "$toString": {
                                    "$ifNull": [
                                        "$items.productId",
                                        {"$ifNull": ["$items.product_id", ""]},
                                    ]
                                }
                            }
                        }
                    },
                    "_overviewProductName": {
                        "$trim": {
                            "input": {
                                "$toString": {
                                    "$ifNull": [
                                        "$items.productName",
                                        {"$ifNull": ["$items.product_name", ""]},
                                    ]
                                }
                            }
                        }
                    },
                    "_overviewCurrency": {"$ifNull": ["$currency", "EGP"]},
                    "_overviewOrderKey": {"$ifNull": ["$id", {"$ifNull": ["$code", "$_id"]}]},
                }
            },
            {
                "$addFields": {
                    "_overviewKey": {
                        "$cond": [
                            {"$ne": ["$_overviewProductId", ""]},
                            "$_overviewProductId",
                            "$_overviewProductName",
                        ]
                    }
                }
            },
            {"$match": {"_overviewKey": {"$ne": ""}}},
            {
                "$group": {
                    "_id": {"key": "$_overviewKey", "currency": "$_overviewCurrency"},
                    "productId": {"$first": "$_overviewProductId"},
                    "name": {"$first": "$_overviewProductName"},
                    "units": {"$sum": _number_expression("$items.qty")},
                    "orderIds": {"$addToSet": "$_overviewOrderKey"},
                    "revenue": {
                        "$sum": {
                            "$multiply": [
                                _number_expression("$items.qty"),
                                _number_expression(
                                    {"$ifNull": ["$items.unitPrice", "$items.unit_price"]}
                                ),
                            ]
                        }
                    },
                }
            },
            {
                "$group": {
                    "_id": "$_id.key",
                    "productId": {"$first": "$productId"},
                    "name": {"$first": "$name"},
                    "units": {"$sum": "$units"},
                    "orders": {"$sum": {"$size": "$orderIds"}},
                    "totalRevenue": {"$sum": "$revenue"},
                    "revenuePairs": {"$push": {"k": "$_id.currency", "v": "$revenue"}},
                }
            },
            {"$sort": {"orders": -1, "units": -1, "totalRevenue": -1}},
            {"$limit": 5},
            {
                "$lookup": {
                    "from": products.name,
                    "let": {"productId": "$productId"},
                    "pipeline": [
                        {"$match": product_match},
                        {
                            "$match": {
                                "$expr": {
                                    "$or": [
                                        {"$eq": ["$id", "$$productId"]},
                                        {"$eq": ["$_id", "$$productId"]},
                                        {"$eq": ["$external_id", "$$productId"]},
                                    ]
                                }
                            }
                        },
                        {"$project": {"_id": 0, "name": 1, "image": 1, "stock": 1, "status": 1}},
                        {"$limit": 1},
                    ],
                    "as": "product",
                }
            },
            {"$addFields": {"product": {"$first": "$product"}}},
            {
                "$project": {
                    "_id": 0,
                    "key": "$_id",
                    "productId": {"$cond": [{"$eq": ["$productId", ""]}, None, "$productId"]},
                    "name": {
                        "$ifNull": [
                            "$product.name",
                            {"$ifNull": ["$name", "Unnamed product"]},
                        ]
                    },
                    "image": {"$ifNull": ["$product.image", ""]},
                    "stock": {"$ifNull": ["$product.stock", 0]},
                    "status": {"$ifNull": ["$product.status", "active"]},
                    "units": 1,
                    "orders": 1,
                    "revenueByCurrency": {"$arrayToObject": "$revenuePairs"},
                }
            },
        ]
    )
    rows = await cursor.to_list(length=5)
    return rows


async def _latest_orders_aggregate(collection: Any, query: dict[str, Any]) -> list[dict[str, Any]]:
    cursor = await collection.aggregate(
        [
            {"$match": query},
            {"$sort": {"created_at": -1}},
            {"$limit": 5},
            {
                "$project": {
                    "_id": 0,
                    "id": {"$ifNull": ["$id", "$code"]},
                    "code": {"$ifNull": ["$code", "$id"]},
                    "firstItem": {"$arrayElemAt": [{"$ifNull": ["$items", []]}, 0]},
                    "created_at": 1,
                    "total": 1,
                    "currency": 1,
                    "payment_method": 1,
                    "status": 1,
                }
            },
        ]
    )
    rows = await cursor.to_list(length=5)
    latest: list[dict[str, Any]] = []
    for order in rows:
        first_item = order.get("firstItem") if isinstance(order.get("firstItem"), dict) else {}
        product_name = (
            first_item.get("productName")
            or first_item.get("product_name")
            or "Multiple products"
        )
        latest.append(
            {
                "id": order.get("id") or "",
                "code": order.get("code") or "",
                "product": str(product_name),
                "createdAt": _datetime(order.get("created_at")).isoformat().replace("+00:00", "Z"),
                "total": _number(order.get("total")),
                "currency": str(order.get("currency") or "EGP"),
                "paymentMethod": str(order.get("payment_method") or "COD"),
                "status": str(order.get("status") or "Pending"),
            }
        )
    return latest


async def _platforms_aggregate(collection: Any, query: dict[str, Any]) -> list[dict[str, Any]]:
    cursor = await collection.aggregate(
        [
            {"$match": query},
            {
                "$addFields": {
                    "_overviewUa": _lower_string("$customer_user_agent"),
                    "_overviewReferrer": _lower_string("$marketing_attribution.referrer"),
                    "_overviewLanding": _lower_string("$marketing_attribution.landing_page"),
                    "_overviewRawSource": _trim_lower_string(
                        {"$ifNull": ["$marketing_attribution.utm_source", "$marketing_attribution.source_type"]}
                    ),
                    "_overviewMedium": _trim_lower_string("$marketing_attribution.utm_medium"),
                    "_overviewSource": _trim_lower_string("$source"),
                    "_overviewExternalSource": _trim_lower_string("$external_source"),
                }
            },
            {
                "$addFields": {
                    "_overviewPlatform": {
                        "$switch": {
                            "branches": [
                                _platform_contains_branch("$_overviewUa", "instagram", "instagram"),
                                _platform_contains_any_branch(
                                    "$_overviewUa",
                                    ["facebook", "fbav", "fb_iab", "fb4a"],
                                    "facebook",
                                ),
                                _platform_contains_branch("$_overviewUa", "tiktok", "tiktok"),
                                _platform_contains_any_branch(
                                    "$_overviewReferrer",
                                    ["facebook.com", "fb.com", "m.facebook.com"],
                                    "facebook",
                                ),
                                _platform_contains_branch("$_overviewReferrer", "instagram.com", "instagram"),
                                _platform_contains_branch("$_overviewReferrer", "tiktok.com", "tiktok"),
                                _platform_contains_branch("$_overviewReferrer", "google.com", "google"),
                                _platform_contains_any_branch(
                                    "$_overviewReferrer",
                                    ["whatsapp.com", "wa.me"],
                                    "whatsapp",
                                ),
                                _platform_contains_branch("$_overviewLanding", "fbclid", "facebook"),
                                _platform_contains_any_branch(
                                    "$_overviewLanding",
                                    ["utm_source=ig", "utm_source=instagram"],
                                    "instagram",
                                ),
                                _platform_contains_any_branch(
                                    "$_overviewLanding",
                                    ["utm_source=fb", "utm_source=facebook"],
                                    "facebook",
                                ),
                                _platform_contains_branch("$_overviewLanding", "utm_source=tiktok", "tiktok"),
                                _platform_contains_branch("$_overviewLanding", "utm_source=google", "google"),
                                _platform_contains_any_branch(
                                    "$_overviewLanding",
                                    ["utm_source=wa", "utm_source=whatsapp"],
                                    "whatsapp",
                                ),
                                _platform_in_branch("$_overviewRawSource", ["fb", "facebook"], "facebook"),
                                _platform_in_branch("$_overviewRawSource", ["ig", "instagram"], "instagram"),
                                _platform_branch("$_overviewRawSource", "tiktok"),
                                _platform_branch("$_overviewRawSource", "google"),
                                _platform_in_branch("$_overviewRawSource", ["whatsapp", "wa"], "whatsapp"),
                                _platform_in_branch("$_overviewRawSource", ["direct", "(direct)"], "direct"),
                                _platform_contains_any_branch(
                                    "$_overviewRawSource",
                                    ["fb", "facebook"],
                                    "facebook",
                                ),
                                _platform_contains_any_branch(
                                    "$_overviewRawSource",
                                    ["ig", "insta"],
                                    "instagram",
                                ),
                                _platform_contains_branch("$_overviewRawSource", "tiktok", "tiktok"),
                                _platform_contains_branch("$_overviewRawSource", "google", "google"),
                                {
                                    "case": {
                                        "$and": [
                                            {"$eq": ["$_overviewMedium", "organic"]},
                                            _contains_expression("$_overviewReferrer", "google"),
                                        ]
                                    },
                                    "then": "google",
                                },
                                _platform_branch("$_overviewMedium", "organic"),
                                *[
                                    _platform_branch("$_overviewSource", platform)
                                    for platform in SOURCE_PLATFORMS
                                ],
                                _platform_in_branch(
                                    "$_overviewExternalSource",
                                    ["woocommerce", "shopify"],
                                    "direct",
                                ),
                            ],
                            "default": "unknown",
                        }
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "platform": "$_overviewPlatform",
                        "currency": {"$ifNull": ["$currency", "EGP"]},
                    },
                    "orders": {"$sum": 1},
                    "delivered": {"$sum": {"$cond": [{"$eq": ["$status", OrderStatus.DELIVERED]}, 1, 0]}},
                    "cancelled": {"$sum": {"$cond": [{"$eq": ["$status", OrderStatus.CANCELLED]}, 1, 0]}},
                    "returned": {
                        "$sum": {
                            "$cond": [
                                {"$in": ["$status", list(RETURNED_STATUSES)]},
                                1,
                                0,
                            ]
                        }
                    },
                    "revenue": {"$sum": _number_expression("$total")},
                }
            },
            {
                "$group": {
                    "_id": "$_id.platform",
                    "orders": {"$sum": "$orders"},
                    "delivered": {"$sum": "$delivered"},
                    "cancelled": {"$sum": "$cancelled"},
                    "returned": {"$sum": "$returned"},
                    "totalRevenue": {"$sum": "$revenue"},
                    "revenuePairs": {"$push": {"k": "$_id.currency", "v": "$revenue"}},
                }
            },
            {"$sort": {"orders": -1, "totalRevenue": -1}},
            {"$limit": 12},
            {
                "$project": {
                    "_id": 0,
                    "key": "$_id",
                    "orders": 1,
                    "delivered": 1,
                    "cancelled": 1,
                    "returned": 1,
                    "revenueByCurrency": {"$arrayToObject": "$revenuePairs"},
                }
            },
        ]
    )
    rows = await cursor.to_list(length=12)
    rows = _complete_platform_rows(rows)
    for row in rows:
        key = str(row.get("key") or "unknown")
        row["label"] = PLATFORM_LABELS.get(key, key.capitalize())
    return rows


def _complete_platform_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key = {
        str(row.get("key") or "unknown"): row
        for row in rows
        if isinstance(row, dict)
    }
    for key in ANALYTICS_PLATFORM_KEYS:
        by_key.setdefault(
            key,
            {
                "key": key,
                "orders": 0,
                "delivered": 0,
                "cancelled": 0,
                "returned": 0,
                "revenueByCurrency": {},
            },
        )
    core_order = {key: index for index, key in enumerate(ANALYTICS_PLATFORM_KEYS)}
    return sorted(
        by_key.values(),
        key=lambda row: (
            -int(row.get("orders") or 0),
            -sum(float(value or 0) for value in dict(row.get("revenueByCurrency") or {}).values()),
            core_order.get(str(row.get("key") or "unknown"), len(core_order)),
        ),
    )


def _workspace_store_query(
    workspace_id: str,
    store_id: str | None,
    *,
    date_range: tuple[datetime, datetime] | None = None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"workspace_id": workspace_id, "deleted_at": None}
    if store_id:
        query["store_id"] = store_id
    if date_range is not None:
        start, end = date_range
        query["created_at"] = {"$gte": start, "$lt": end}
    return query


def _product_lookup(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for product in products:
        keys = {
            str(product.get("id") or product.get("_id") or "").strip(),
            str(product.get("external_id") or "").strip(),
        }
        keys.discard("")
        for key in keys:
            existing = lookup.get(key)
            if existing is None or (not existing.get("image") and product.get("image")):
                lookup[key] = product
    return lookup


def _revenue_by_currency(orders: list[dict[str, Any]]) -> dict[str, float]:
    revenue: dict[str, float] = defaultdict(float)
    for order in orders:
        currency = str(order.get("currency") or "EGP")
        revenue[currency] += _number(order.get("total"))
    return dict(revenue)


def _trend(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not orders:
        return []
    first = _datetime(orders[0].get("created_at"))
    last = _datetime(orders[-1].get("created_at"))
    span_days = max(1, (last - first).days + 1)
    use_month = span_days > 45
    buckets: dict[str, dict[str, Any]] = {}

    for order in orders:
        created_at = _datetime(order.get("created_at"))
        if use_month:
            key = f"{created_at.year}-{created_at.month:02d}"
            label = created_at.strftime("%b %y")
            sort = datetime(created_at.year, created_at.month, 1, tzinfo=UTC).timestamp()
        else:
            key = created_at.date().isoformat()
            label = created_at.strftime("%b %d")
            sort = datetime(
                created_at.year,
                created_at.month,
                created_at.day,
                tzinfo=UTC,
            ).timestamp()
        bucket = buckets.setdefault(
            key,
            {
                "label": label,
                "orders": 0,
                "revenueByCurrency": defaultdict(float),
                "sort": sort,
            },
        )
        bucket["orders"] += 1
        bucket["revenueByCurrency"][str(order.get("currency") or "EGP")] += _number(
            order.get("total")
        )

    rows = sorted(buckets.values(), key=lambda item: item["sort"])[-MAX_CHART_BUCKETS:]
    return [
        {
            "label": item["label"],
            "orders": item["orders"],
            "revenueByCurrency": dict(item["revenueByCurrency"]),
        }
        for item in rows
    ]


def _top_products(
    orders: list[dict[str, Any]],
    products: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for order in orders:
        seen: set[str] = set()
        currency = str(order.get("currency") or "EGP")
        for item in order.get("items") or []:
            product_id = str(item.get("productId") or item.get("product_id") or "").strip()
            name = str(item.get("productName") or item.get("product_name") or "").strip()
            key = product_id or name
            if not key:
                continue
            product = products.get(product_id) or {}
            row = rows.setdefault(
                key,
                {
                    "key": key,
                    "productId": product_id or None,
                    "name": product.get("name") or name or "Unnamed product",
                    "image": product.get("image") or "",
                    "stock": product.get("stock", 0),
                    "status": product.get("status", "active"),
                    "units": 0,
                    "orders": 0,
                    "revenueByCurrency": defaultdict(float),
                },
            )
            qty = max(0, int(_number(item.get("qty"))))
            row["units"] += qty
            row["revenueByCurrency"][currency] += qty * _number(
                item.get("unitPrice") or item.get("unit_price")
            )
            if key not in seen:
                row["orders"] += 1
                seen.add(key)

    ranked = sorted(
        rows.values(),
        key=lambda item: (item["orders"], item["units"], sum(item["revenueByCurrency"].values())),
        reverse=True,
    )[:5]
    for item in ranked:
        item["revenueByCurrency"] = dict(item["revenueByCurrency"])
    return ranked


def _latest_orders(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest = sorted(orders, key=lambda item: _datetime(item.get("created_at")), reverse=True)[:5]
    rows: list[dict[str, Any]] = []
    for order in latest:
        first_item = next((item for item in order.get("items") or [] if isinstance(item, dict)), {})
        product_name = (
            first_item.get("productName")
            or first_item.get("product_name")
            or "Multiple products"
        )
        rows.append(
            {
                "id": order.get("id") or order.get("code") or "",
                "code": order.get("code") or order.get("id") or "",
                "product": str(product_name),
                "createdAt": _datetime(order.get("created_at")).isoformat().replace("+00:00", "Z"),
                "total": _number(order.get("total")),
                "currency": str(order.get("currency") or "EGP"),
                "paymentMethod": str(order.get("payment_method") or "COD"),
                "status": str(order.get("status") or "Pending"),
            }
        )
    return rows


def _platforms(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for order in orders:
        key = _platform_key(order)
        row = rows.setdefault(
            key,
            {
                "key": key,
                "label": PLATFORM_LABELS.get(key, key.capitalize()),
                "orders": 0,
                "delivered": 0,
                "revenueByCurrency": defaultdict(float),
            },
        )
        row["orders"] += 1
        if order.get("status") == OrderStatus.DELIVERED:
            row["delivered"] += 1
        row["revenueByCurrency"][str(order.get("currency") or "EGP")] += _number(order.get("total"))

    ranked = sorted(
        rows.values(),
        key=lambda item: (item["orders"], sum(item["revenueByCurrency"].values())),
        reverse=True,
    )[:6]
    for item in ranked:
        item["revenueByCurrency"] = dict(item["revenueByCurrency"])
    return ranked


def _platform_key(order: dict[str, Any]) -> str:
    user_agent = str(order.get("customer_user_agent") or "").lower()
    if "instagram" in user_agent:
        return "instagram"
    if any(token in user_agent for token in ("facebook", "fbav", "fb_iab", "fb4a")):
        return "facebook"
    if "tiktok" in user_agent:
        return "tiktok"

    marketing_attribution = order.get("marketing_attribution") or {}
    if not isinstance(marketing_attribution, dict):
        marketing_attribution = {}

    referrer = str(marketing_attribution.get("referrer") or "").lower()
    if any(token in referrer for token in ("facebook.com", "fb.com", "m.facebook.com")):
        return "facebook"
    if "instagram.com" in referrer:
        return "instagram"
    if "tiktok.com" in referrer:
        return "tiktok"
    if "google.com" in referrer:
        return "google"
    if any(token in referrer for token in ("whatsapp.com", "wa.me")):
        return "whatsapp"

    landing_page = str(marketing_attribution.get("landing_page") or "").lower()
    if "fbclid" in landing_page:
        return "facebook"
    if "utm_source=ig" in landing_page or "utm_source=instagram" in landing_page:
        return "instagram"
    if "utm_source=fb" in landing_page or "utm_source=facebook" in landing_page:
        return "facebook"
    if "utm_source=tiktok" in landing_page:
        return "tiktok"
    if "utm_source=google" in landing_page:
        return "google"
    if "utm_source=wa" in landing_page or "utm_source=whatsapp" in landing_page:
        return "whatsapp"

    raw_source_value = (
        marketing_attribution.get("utm_source")
        if marketing_attribution.get("utm_source") is not None
        else marketing_attribution.get("source_type")
    )
    raw_source = str(raw_source_value or "").strip().lower()
    if raw_source in {"fb", "facebook"}:
        return "facebook"
    if raw_source in {"ig", "instagram"}:
        return "instagram"
    if raw_source == "tiktok":
        return "tiktok"
    if raw_source == "google":
        return "google"
    if raw_source in {"whatsapp", "wa"}:
        return "whatsapp"
    if raw_source in {"direct", "(direct)"}:
        return "direct"
    if "fb" in raw_source or "facebook" in raw_source:
        return "facebook"
    if "ig" in raw_source or "insta" in raw_source:
        return "instagram"
    if "tiktok" in raw_source:
        return "tiktok"
    if "google" in raw_source:
        return "google"

    medium = str(marketing_attribution.get("utm_medium") or "").strip().lower()
    if medium == "organic":
        return "google" if "google" in referrer else "organic"

    source = str(order.get("source") or "").strip().lower()
    if source in SOURCE_PLATFORMS:
        return source
    external_source = str(order.get("external_source") or "").strip().lower()
    if external_source in {"woocommerce", "shopify"}:
        return "direct"
    return "unknown"


async def _team_summary(collection: Any, workspace_id: str) -> dict[str, Any]:
    rows = await (
        await collection.aggregate(
            [
                {"$match": {"workspace_id": workspace_id}},
                {
                    "$facet": {
                        "totals": [
                            {
                                "$group": {
                                    "_id": None,
                                    "teamMembers": {"$sum": 1},
                                    "activeTeamMembers": {
                                        "$sum": {"$cond": [{"$eq": ["$active", True]}, 1, 0]},
                                    },
                                }
                            }
                        ],
                        "roles": [
                            {
                                "$group": {
                                    "_id": {"$ifNull": ["$role", "unknown"]},
                                    "count": {"$sum": 1},
                                }
                            },
                            {"$sort": {"count": -1, "_id": 1}},
                        ],
                        "sections": [
                            {
                                "$unwind": {
                                    "path": "$allowed_sections",
                                    "preserveNullAndEmptyArrays": False,
                                }
                            },
                            {
                                "$project": {
                                    "sectionId": {
                                        "$ifNull": [
                                            "$allowed_sections.sectionId",
                                            "$allowed_sections.id",
                                        ],
                                    }
                                }
                            },
                            {"$match": {"sectionId": {"$nin": [None, ""]}}},
                            {"$group": {"_id": "$sectionId"}},
                            {"$count": "count"},
                        ],
                    }
                },
            ]
        )
    ).to_list(length=1)
    facet = rows[0] if rows else {}
    totals = (facet.get("totals") or [{}])[0]
    sections = (facet.get("sections") or [{}])[0]
    return {
        "teamMembers": int(totals.get("teamMembers") or 0),
        "activeTeamMembers": int(totals.get("activeTeamMembers") or 0),
        "permissionSections": int(sections.get("count") or 0),
        "roleSummary": [
            {
                "label": str(row.get("_id") or "unknown").replace("_", " "),
                "count": int(row.get("count") or 0),
            }
            for row in facet.get("roles") or []
        ],
    }


def _empty_team_summary() -> dict[str, Any]:
    return {
        "teamMembers": 0,
        "activeTeamMembers": 0,
        "permissionSections": 0,
        "roleSummary": [],
    }


async def _integration_summary(
    workspace_id: str,
    *,
    woo_sync_service: Any | None,
    bosta_integration_service: Any | None,
    shopify_service: Any | None,
) -> list[dict[str, str]]:
    woo_connected = bool(
        woo_sync_service and await woo_sync_service.has_connected_status(workspace_id)
    )
    bosta_status = (
        await bosta_integration_service.get_status(workspace_id)
        if bosta_integration_service
        else None
    )
    shopify_connected = bool(shopify_service and await shopify_service.has_active(workspace_id))
    return [
        {
            "id": "woocommerce",
            "name": "WooCommerce",
            "status": "connected" if woo_connected else "available",
        },
        {
            "id": "shopify",
            "name": "Shopify",
            "status": "connected" if shopify_connected else "coming_soon",
        },
        {
            "id": "bosta",
            "name": "Bosta",
            "status": "connected" if bosta_status and bosta_status.get("isActive") else "available",
        },
        {"id": "meta", "name": "Meta", "status": "coming_soon"},
        {"id": "google", "name": "Google Ads", "status": "coming_soon"},
        {"id": "tiktok", "name": "TikTok", "status": "coming_soon"},
        {"id": "salla", "name": "Salla", "status": "coming_soon"},
    ]


def _number_expression(value: Any) -> dict[str, Any]:
    return {
        "$convert": {
            "input": {"$ifNull": [value, 0]},
            "to": "double",
            "onError": 0,
            "onNull": 0,
        }
    }


def _date_to_string(date_format: str, date_expression: str) -> dict[str, Any]:
    return {"$dateToString": {"format": date_format, "date": date_expression}}


def _platform_branch(field: str, value: str) -> dict[str, Any]:
    return {
        "case": {"$eq": [field, value]},
        "then": value,
    }


def _platform_in_branch(field: str, values: list[str], platform: str) -> dict[str, Any]:
    return {"case": {"$in": [field, values]}, "then": platform}


def _platform_contains_branch(field: str, needle: str, platform: str) -> dict[str, Any]:
    return {"case": _contains_expression(field, needle), "then": platform}


def _platform_contains_any_branch(field: str, needles: list[str], platform: str) -> dict[str, Any]:
    return {
        "case": {"$or": [_contains_expression(field, needle) for needle in needles]},
        "then": platform,
    }


def _contains_expression(field: str, needle: str) -> dict[str, Any]:
    return {"$gte": [{"$indexOfCP": [field, needle]}, 0]}


def _lower_string(field: str | dict[str, Any]) -> dict[str, Any]:
    return {"$toLower": {"$ifNull": [field, ""]}}


def _trim_lower_string(field: str | dict[str, Any]) -> dict[str, Any]:
    return {"$trim": {"input": _lower_string(field)}}


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            pass
    return datetime.fromtimestamp(0, tz=UTC)
