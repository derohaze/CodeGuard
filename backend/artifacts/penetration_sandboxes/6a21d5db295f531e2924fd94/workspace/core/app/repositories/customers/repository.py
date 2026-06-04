from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import DESCENDING, UpdateOne, ReturnDocument

from core.app.models.customers.entity import Customer
from core.app.models.common.base import new_id, utc_now
from core.app.models.orders.status import OrderStatus
from core.app.repositories.common.base import MongoRepository, regex_filter, startswith_regex_filter

_STATUS_FIELD_MAP = {
    OrderStatus.DELIVERED: "delivered_orders",
    OrderStatus.CANCELLED: "cancelled_orders",
    OrderStatus.RETURNED: "returned_orders",
}


class CustomerRepository(MongoRepository):
    collection_name = "customers"
    _tenant_scoped = True

    async def upsert_external_customer(
        self,
        *,
        workspace_id: str,
        source: str,
        external_customer_id: str,
        fields: dict,
    ) -> None:
        now = utc_now()
        safe_external_id = str(external_customer_id).strip()
        if not safe_external_id:
            return
        if "raw_payload" in fields:
            from core.app.services.woocommerce.normalization import sanitize_for_mongo
            fields["raw_payload"] = sanitize_for_mongo(fields["raw_payload"])
        first = str(fields.get("first_name") or "").strip()
        last = str(fields.get("last_name") or "").strip()
        name = str(fields.get("name") or " ".join(part for part in (first, last) if part)).strip()
        email = str(fields.get("email") or "").strip() or None
        phone = str(fields.get("phone") or "").strip()
        governorate = str(fields.get("governorate") or "").strip() or "Unknown"
        address = str(fields.get("address") or "").strip() or "-"
        if len(phone) < 4:
            phone = f"{source.lower()}-{safe_external_id}"[:40]
        customer_id = new_id("cus")
        await self.collection.update_one(
            {
                "workspace_id": workspace_id,
                "integration_key": source.lower(),
                "external_customer_id": safe_external_id,
            },
            {
                "$set": {
                    **fields,
                    "workspace_id": workspace_id,
                    "name": (name or email or f"{source} customer {safe_external_id}")[:160],
                    "phone": phone,
                    "email": email,
                    "external_customer_id": safe_external_id,
                    "integration_key": source.lower(),
                    "external_source": source.lower(),
                    "updated_at": now,
                    "deleted_at": None,
                },
                "$setOnInsert": {
                    "_id": customer_id,
                    "id": customer_id,
                    "created_at": now,
                    "governorate": governorate,
                    "address": address,
                    "total_orders": 0,
                    "delivered_orders": 0,
                    "cancelled_orders": 0,
                    "returned_orders": 0,
                    "lifetime_value": 0,
                },
            },
            upsert=True,
        )

    async def soft_delete_external_customer(
        self,
        *,
        workspace_id: str,
        source: str,
        external_customer_id: str,
        deleted_at: datetime,
    ) -> None:
        await self.collection.update_one(
            {
                "workspace_id": workspace_id,
                "integration_key": source.lower(),
                "external_customer_id": str(external_customer_id),
                "deleted_at": None,
            },
            {"$set": {"deleted_at": deleted_at, "updated_at": deleted_at}},
        )

    async def list_for_workspace(
        self,
        workspace_id: str,
        *,
        store_id: str | None,
        search: str,
        page: int,
        page_size: int,
        cursor: str | None = None,
    ) -> dict:
        query: dict[str, object] = {"workspace_id": workspace_id, "deleted_at": None}
        if store_id:
            query["$or"] = [
                {"store_id": store_id},
                {"store_id": {"$exists": False}},
                {"store_id": None},
            ]
        normalized_search = search.strip()
        if normalized_search:
            if normalized_search.isdigit():
                query["phone"] = startswith_regex_filter(normalized_search, case_insensitive=False)
            else:
                search_or = [{"name": regex_filter(normalized_search)}, {"phone": regex_filter(normalized_search)}]
                if "$or" in query:
                    query = {"$and": [query, {"$or": search_or}]}
                else:
                    query["$or"] = search_or
        if cursor:
            return await self.list_cursor_page(
                query,
                page_size,
                sort_field="created_at",
                projection={"_id": 0},
                cursor=cursor,
            )

        return await self.list_page(
            query,
            page,
            page_size,
            sort=[("created_at", DESCENDING)],
            projection={"_id": 0},
        )

    async def get_by_email(self, email: str) -> dict | None:
        return await self.find_one(
            {"email": email.lower().strip(), "deleted_at": None},
            {"_id": 0},
        )

    async def get_by_phone(self, workspace_id: str, phone: str) -> dict | None:
        return await self.find_one(
            {"workspace_id": workspace_id, "phone": phone, "deleted_at": None},
            {"_id": 0},
        )

    async def create(self, customer: Customer) -> dict:
        return await self.insert_model(customer)

    async def upsert_imported_customer(
        self,
        *,
        workspace_id: str,
        name: str,
        phone: str,
        email: str | None,
        external_customer_id: str | None,
        governorate: str,
        address: str,
        integration_key: str | None,
    ) -> bool:
        existing = None
        external_customer_id = (external_customer_id or "").strip() or None
        if external_customer_id:
            external_id_query: dict[str, object] = {
                "workspace_id": workspace_id,
                "external_customer_id": external_customer_id,
                "deleted_at": None,
            }
            if integration_key:
                external_id_query["integration_key"] = integration_key
            existing = await self.find_one(external_id_query, {"_id": 0})
            if not existing and integration_key:
                existing = await self.find_one(
                    {
                        "workspace_id": workspace_id,
                        "external_customer_id": external_customer_id,
                        "deleted_at": None,
                        "integration_key": {"$exists": False},
                    },
                    {"_id": 0},
                )
        if phone:
            phone_query: dict[str, object] = {
                "workspace_id": workspace_id,
                "phone": phone,
                "deleted_at": None,
            }
            if integration_key:
                phone_query["integration_key"] = integration_key
            existing = await self.find_one(phone_query, {"_id": 0})
            if not existing and integration_key:
                existing = await self.find_one(
                    {
                        "workspace_id": workspace_id,
                        "phone": phone,
                        "deleted_at": None,
                        "integration_key": {"$exists": False},
                    },
                    {"_id": 0},
                )
        if not existing and email:
            email_query: dict[str, object] = {
                "workspace_id": workspace_id,
                "email": email,
                "deleted_at": None,
            }
            if integration_key:
                email_query["integration_key"] = integration_key
            existing = await self.find_one(email_query, {"_id": 0})
            if not existing and integration_key:
                existing = await self.find_one(
                    {
                        "workspace_id": workspace_id,
                        "email": email,
                        "deleted_at": None,
                        "integration_key": {"$exists": False},
                    },
                    {"_id": 0},
                )
        customer = Customer(
            workspace_id=workspace_id,
            name=name,
            phone=phone,
            email=email,
            external_customer_id=external_customer_id,
            governorate=governorate,
            address=address,
            integration_key=integration_key,
        )
        created = existing is None
        if existing:
            await self.collection.update_one(
                {"_id": existing["id"]},
                {"$set": customer.model_dump(mode="python", exclude={"id", "created_at"})},
            )
        else:
            await self.create(customer)
        return created

    async def count_active_for_workspace(self, workspace_id: str) -> int:
        return int(
            await self.collection.count_documents(
                {"workspace_id": workspace_id, "deleted_at": None}
            )
        )

    async def bulk_upsert_backfilled_woocommerce_customers(
        self,
        *,
        rows: list[dict[str, Any]],
    ) -> None:
        if not rows:
            return
        operations = [
            UpdateOne(
                {
                    "workspace_id": row["workspace_id"],
                    "phone": row["phone"],
                    "deleted_at": None,
                },
                {
                    "$set": row["set"],
                    "$setOnInsert": row["set_on_insert"],
                },
                upsert=True,
            )
            for row in rows
        ]
        if hasattr(self.collection, "bulk_write"):
            await self.collection.bulk_write(operations, ordered=False)
            return
        for row in rows:
            await self.collection.update_one(
                {
                    "workspace_id": row["workspace_id"],
                    "phone": row["phone"],
                    "deleted_at": None,
                },
                {"$set": row["set"], "$setOnInsert": row["set_on_insert"]},
                upsert=True,
            )

    async def resolve_by_phone(
        self,
        workspace_id: str,
        phone: str,
        *,
        store_id: str | None = None,
        name: str | None = None,
        email: str | None = None,
        governorate: str | None = None,
        address: str | None = None,
        last_ip_address: str | None = None,
        lifetime_value_delta: float = 0,
        updated_at: datetime | None = None,
    ) -> str:
        now = updated_at or utc_now()
        customer_id = new_id("cus")
        set_fields: dict[str, object] = {"updated_at": now, "last_ip_address": last_ip_address}
        set_on_insert: dict[str, object] = {
            "_id": customer_id,
            "id": customer_id,
            "workspace_id": workspace_id,
            "name": (name or phone)[:160],
            "phone": phone[:40],
            "email": email,
            "governorate": (governorate or "")[:80],
            "address": (address or "")[:500],
            "delivered_orders": 0,
            "cancelled_orders": 0,
            "returned_orders": 0,
            "created_at": now,
            "deleted_at": None,
        }
        if store_id:
            set_fields["store_id"] = store_id
        else:
            set_on_insert["store_id"] = None
        doc = await self.collection.find_one_and_update(
            {"workspace_id": workspace_id, "phone": phone, "deleted_at": None},
            {
                "$inc": {"total_orders": 1, "lifetime_value": lifetime_value_delta},
                "$set": set_fields,
                "$setOnInsert": set_on_insert,
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return doc["id"]

    async def update_last_ip(
        self,
        customer_id: str,
        ip: str,
        *,
        updated_at: datetime,
    ) -> None:
        await self.collection.update_one(
            {"_id": customer_id},
            {"$set": {"last_ip_address": ip, "updated_at": updated_at}},
        )

    async def increment_order_stats(
        self,
        customer_id: str,
        *,
        updated_at: datetime,
        lifetime_value_delta: float = 0,
    ) -> None:
        await self.collection.update_one(
            {"_id": customer_id},
            {
                "$inc": {"total_orders": 1, "lifetime_value": lifetime_value_delta},
                "$set": {"updated_at": updated_at},
            },
        )

    async def increment_status_stats(
        self,
        customer_id: str,
        status: str,
        *,
        updated_at: datetime,
    ) -> None:
        field = _STATUS_FIELD_MAP.get(status)
        if not field:
            return
        await self.collection.update_one(
            {"_id": customer_id},
            {"$inc": {field: 1}, "$set": {"updated_at": updated_at}},
        )

    async def decrement_status_stats(
        self,
        customer_id: str,
        status: str,
        *,
        updated_at: datetime,
    ) -> None:
        field = _STATUS_FIELD_MAP.get(status)
        if not field:
            return
        await self.collection.update_one(
            {"_id": customer_id},
            {"$inc": {field: -1}, "$set": {"updated_at": updated_at}},
        )

    async def set_customer_stats(
        self,
        customer_id: str,
        *,
        total_orders: int,
        lifetime_value: float,
        delivered_orders: int,
        cancelled_orders: int,
        returned_orders: int,
        updated_at: datetime | None = None,
    ) -> None:
        now = updated_at or utc_now()
        await self.collection.update_one(
            {"_id": customer_id},
            {
                "$set": {
                    "total_orders": total_orders,
                    "lifetime_value": max(0.0, lifetime_value),
                    "delivered_orders": delivered_orders,
                    "cancelled_orders": cancelled_orders,
                    "returned_orders": returned_orders,
                    "updated_at": now,
                },
            },
        )

    async def link_orders_to_customer(
        self,
        order_ids: list[str],
        customer_id: str,
        *,
        orders_collection: Any,
        updated_at: datetime,
    ) -> None:
        if not order_ids:
            return
        await orders_collection.update_many(
            {"_id": {"$in": order_ids}},
            {"$set": {"customer_id": customer_id, "updated_at": updated_at}},
        )

    async def list_for_store(
        self,
        store_id: str,
        *,
        search: str,
        page: int,
        page_size: int,
        cursor: str | None = None,
    ) -> dict:
        query: dict[str, object] = {"store_id": store_id, "deleted_at": None}
        normalized_search = search.strip()
        if normalized_search:
            if normalized_search.isdigit():
                query["phone"] = startswith_regex_filter(normalized_search, case_insensitive=False)
            else:
                query["$or"] = [{"name": regex_filter(normalized_search)}, {"phone": regex_filter(normalized_search)}]
        if cursor:
            return await self.list_cursor_page(
                query,
                page_size,
                sort_field="created_at",
                projection={"_id": 0},
                cursor=cursor,
            )
        return await self.list_page(
            query,
            page,
            page_size,
            sort=[("created_at", DESCENDING)],
            projection={"_id": 0},
        )

    async def get_by_phone_for_store(self, store_id: str, phone: str) -> dict | None:
        return await self.find_one(
            {"store_id": store_id, "phone": phone, "deleted_at": None},
            {"_id": 0},
        )

    async def count_active_for_store(self, store_id: str) -> int:
        return int(
            await self.collection.count_documents(
                {"store_id": store_id, "deleted_at": None}
            )
        )

    async def soft_delete_for_store(self, store_id: str, *, deleted_at: datetime) -> None:
        await self.collection.update_many(
            {"store_id": store_id, "deleted_at": None},
            {"$set": {"deleted_at": deleted_at, "updated_at": deleted_at}},
        )

    async def soft_delete_for_workspace(self, workspace_id: str, *, deleted_at: datetime) -> None:
        await self.collection.update_many(
            {"workspace_id": workspace_id, "deleted_at": None},
            {"$set": {"deleted_at": deleted_at, "updated_at": deleted_at}},
        )
