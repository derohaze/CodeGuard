from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import DESCENDING
from pymongo import UpdateOne

from core.app.models.catalog.entity import Product
from core.app.models.common.base import new_id, utc_now
from core.app.repositories.common.base import MongoRepository, regex_filter, startswith_regex_filter


class ProductRepository(MongoRepository):
    collection_name = "products"
    _tenant_scoped = True

    async def upsert_external_product(
        self,
        *,
        workspace_id: str,
        source: str,
        external_id: str,
        fields: dict,
    ) -> None:
        now = utc_now()
        safe_external_id = str(external_id).strip()
        if not safe_external_id:
            return
        if "raw_payload" in fields:
            from core.app.services.woocommerce.normalization import sanitize_for_mongo
            fields["raw_payload"] = sanitize_for_mongo(fields["raw_payload"])
        normalized_source = source.lower()
        source_display = str(fields.get("source") or source).strip()[:80] or source
        fallback_name = f"{source_display} product {safe_external_id}"
        name = str(fields.get("name") or fields.get("title") or fallback_name)[:180]
        sku = str(fields.get("sku") or f"{normalized_source}-{safe_external_id}")[:80]
        price_raw = fields.get("price") or fields.get("total_price") or 0
        try:
            price = max(0.0, float(price_raw or 0))
        except (TypeError, ValueError):
            price = 0.0
        currency = str(fields.get("currency") or "EGP").strip().upper() or "EGP"
        status = str(fields.get("status") or "active").strip() or "active"

        update = {
            **fields,
            "workspace_id": workspace_id,
            "name": name or f"{source_display} product {safe_external_id}",
            "sku": sku,
            "price": price,
            "source": source_display,
            "external_source": normalized_source,
            "external_id": safe_external_id,
            "updated_at": now,
            "deleted_at": None,
        }
        product_id = new_id("prd")
        set_on_insert = {
            "_id": product_id,
            "id": product_id,
            "created_at": now,
            "cost": 0,
            "currency": currency,
            "status": status,
        }
        for key in list(set_on_insert):
            if key in update:
                set_on_insert.pop(key)
        await self.collection.update_one(
            {
                "workspace_id": workspace_id,
                "external_id": safe_external_id,
                "$or": [
                    {"external_source": normalized_source},
                    {"external_source": {"$exists": False}},
                ],
            },
            {"$set": update, "$setOnInsert": set_on_insert},
            upsert=True,
        )

    async def soft_delete_external_product(
        self,
        *,
        workspace_id: str,
        source: str,
        external_id: str,
        deleted_at: datetime,
    ) -> None:
        await self.collection.update_one(
            {
                "workspace_id": workspace_id,
                "external_source": source.lower(),
                "external_id": str(external_id),
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
        include_cost: bool,
        cursor: str | None = None,
    ) -> dict:
        query: dict[str, object] = {"workspace_id": workspace_id, "deleted_at": None}
        store_or = None
        if store_id:
            store_or = [
                {"store_id": store_id},
                {"store_id": {"$exists": False}},
                {"store_id": None},
            ]
        normalized_search = search.strip()
        search_or = None
        text_query = None
        if normalized_search:
            # Use $text index for word-level searches (fast, indexed).
            # Fall back to $regex for substring/short searches.
            if len(normalized_search) >= 2 and normalized_search.replace(" ", "").isalnum():
                text_query = {"$text": {"$search": normalized_search}}
            else:
                search_or = [
                    {"name": regex_filter(normalized_search)},
                    {"sku": regex_filter(normalized_search)},
                ]
        if text_query:
            query.update(text_query)
        if store_or and search_or:
            query["$and"] = [{"$or": store_or}, {"$or": search_or}]
        elif store_or:
            query["$or"] = store_or
        elif search_or:
            query["$or"] = search_or
        projection = {"_id": 0}
        if not include_cost:
            projection["cost"] = 0
        if cursor:
            return await self.list_cursor_page(
                query,
                page_size,
                sort_field="created_at",
                projection=projection,
                cursor=cursor,
            )

        return await self.list_page(
            query,
            page,
            page_size,
            sort=[("created_at", DESCENDING)],
            projection=projection,
        )

    async def summarize_for_workspace(
        self,
        workspace_id: str,
        store_id: str | None,
        *,
        search: str,
    ) -> dict:
        query = self._workspace_query(workspace_id, store_id=store_id, search=search)
        cursor = await self.collection.aggregate([
            {"$match": query},
            {
                "$group": {
                    "_id": None,
                    "totalProducts": {"$sum": 1},
                    "inventoryValue": {
                        "$sum": {
                            "$multiply": [
                                {"$ifNull": ["$price", 0]},
                                {"$ifNull": ["$stock", 0]},
                            ]
                        }
                    },
                    "lowStock": {
                        "$sum": {
                            "$cond": [
                                {
                                    "$and": [
                                        {"$gt": [{"$ifNull": ["$stock", 0]}, 0]},
                                        {"$lt": [{"$ifNull": ["$stock", 0]}, 10]},
                                    ]
                                },
                                1,
                                0,
                            ]
                        }
                    },
                    "outOfStock": {
                        "$sum": {
                            "$cond": [
                                {"$lte": [{"$ifNull": ["$stock", 0]}, 0]},
                                1,
                                0,
                            ]
                        }
                    },
                }
            },
        ])
        rows = await cursor.to_list(length=1)
        if not rows:
            return {
                "totalProducts": 0,
                "inventoryValue": 0,
                "lowStock": 0,
                "outOfStock": 0,
            }
        row = rows[0]
        return {
            "totalProducts": int(row.get("totalProducts") or 0),
            "inventoryValue": float(row.get("inventoryValue") or 0),
            "lowStock": int(row.get("lowStock") or 0),
            "outOfStock": int(row.get("outOfStock") or 0),
        }

    def _workspace_query(self, workspace_id: str, *, store_id: str | None, search: str) -> dict[str, object]:
        query: dict[str, object] = {"workspace_id": workspace_id, "deleted_at": None}
        store_or = None
        if store_id:
            store_or = [
                {"store_id": store_id},
                {"store_id": {"$exists": False}},
                {"store_id": None},
            ]
        normalized_search = search.strip()
        search_or = None
        text_query = None
        if normalized_search:
            if len(normalized_search) >= 2 and normalized_search.replace(" ", "").isalnum():
                text_query = {"$text": {"$search": normalized_search}}
            else:
                search_or = [
                    {"name": regex_filter(normalized_search)},
                    {"sku": regex_filter(normalized_search)},
                ]
        if text_query:
            query.update(text_query)
        if store_or and search_or:
            query["$and"] = [{"$or": store_or}, {"$or": search_or}]
        elif store_or:
            query["$or"] = store_or
        elif search_or:
            query["$or"] = search_or
        return query

    async def get_workspace_product(self, workspace_id: str, product_id: str) -> dict | None:
        return await self.find_one(
            {"_id": product_id, "workspace_id": workspace_id, "deleted_at": None},
            {"_id": 0},
        )

    async def create(self, product: Product) -> dict:
        return await self.insert_model(product)

    async def upsert(self, product: Product) -> dict:
        return await self.upsert_model(product)

    async def count_active_for_workspace(self, workspace_id: str) -> int:
        return int(
            await self.collection.count_documents(
                {"workspace_id": workspace_id, "deleted_at": None}
            )
        )

    async def upsert_imported_product(
        self,
        *,
        product: Product,
        integration_key: str | None,
    ) -> bool:
        normalized_external_id = str(product.external_id or "").strip() or None
        product_query: dict[str, object] = {
            "workspace_id": product.workspace_id,
            "sku": product.sku,
        }
        if integration_key:
            product_query["integration_key"] = integration_key
        product_doc = product.model_dump(mode="python")
        set_on_insert = {
            "_id": product.id,
            "id": product.id,
            "workspace_id": product.workspace_id,
            "owner_user_id": product.owner_user_id,
            "created_by_user_id": product.created_by_user_id,
            "created_at": product.created_at,
        }
        updates = dict(product_doc)
        for key in (
            "_id",
            "id",
            "created_at",
            "workspace_id",
            "owner_user_id",
            "created_by_user_id",
        ):
            updates.pop(key, None)
        existing_product = None
        if normalized_external_id:
            external_query: dict[str, object] = {
                "workspace_id": product.workspace_id,
                "external_id": normalized_external_id,
                "deleted_at": None,
            }
            if integration_key:
                external_query["integration_key"] = integration_key
            existing_product = await self.find_one(external_query, {"_id": 0})
            if not existing_product and integration_key:
                existing_product = await self.find_one(
                    {
                        "workspace_id": product.workspace_id,
                        "external_id": normalized_external_id,
                        "deleted_at": None,
                        "integration_key": {"$exists": False},
                    },
                    {"_id": 0},
                )

        if not existing_product:
            existing_product = await self.find_one(product_query, {"_id": 0})
        if not existing_product and integration_key:
            existing_product = await self.find_one(
                {
                    "workspace_id": product.workspace_id,
                    "sku": product.sku,
                    "integration_key": {"$exists": False},
                },
                {"_id": 0},
            )
        created = existing_product is None
        if existing_product:
            await self.collection.update_one(
                {"_id": existing_product["id"]},
                {"$set": updates},
            )
        else:
            await self.collection.update_one(
                product_query,
                {"$set": updates, "$setOnInsert": set_on_insert},
                upsert=True,
            )
        return created

    async def upsert_workspace_sku(self, product: Product) -> tuple[dict, bool]:
        document = product.to_mongo()
        set_on_insert = {
            "_id": product.id,
            "id": product.id,
            "workspace_id": product.workspace_id,
            "owner_user_id": product.owner_user_id,
            "created_by_user_id": product.created_by_user_id,
            "created_at": product.created_at,
        }
        updates = dict(document)
        for key in (
            "_id",
            "id",
            "created_at",
            "workspace_id",
            "owner_user_id",
            "created_by_user_id",
        ):
            updates.pop(key, None)

        result = await self.collection.update_one(
            {"workspace_id": product.workspace_id, "sku": product.sku},
            {"$set": updates, "$setOnInsert": set_on_insert},
            upsert=True,
        )
        saved = await self.find_one(
            {"workspace_id": product.workspace_id, "sku": product.sku},
            {"_id": 0},
        )
        return saved or {}, result.upserted_id is not None

    async def update(
        self,
        workspace_id: str,
        store_id: str | None,
        product_id: str,
        patch: dict,
        updated_at: datetime,
    ) -> dict | None:
        update = {**patch, "updated_at": updated_at}
        scope_query: dict[str, object] = {
            "_id": product_id,
            "workspace_id": workspace_id,
            "deleted_at": None,
        }
        if store_id:
            scope_query["$or"] = [
                {"store_id": store_id},
                {"store_id": {"$exists": False}},
                {"store_id": None},
            ]
        await self.collection.update_one(
            scope_query,
            {"$set": update},
        )
        product = await self.get_workspace_product(workspace_id, product_id)
        if not product:
            return None
        if store_id and product.get("store_id") not in {None, store_id}:
            return None
        return product

    async def bulk_upsert_backfilled_woocommerce_products(
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
                    "sku": row["sku"],
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
                    "sku": row["sku"],
                    "deleted_at": None,
                },
                {"$set": row["set"], "$setOnInsert": row["set_on_insert"]},
                upsert=True,
            )

    async def list_for_store(
        self,
        store_id: str,
        *,
        search: str,
        page: int,
        page_size: int,
        include_cost: bool,
        cursor: str | None = None,
    ) -> dict:
        query: dict[str, object] = {"store_id": store_id, "deleted_at": None}
        normalized_search = search.strip()
        if normalized_search:
            if normalized_search.replace("-", "").replace("_", "").isalnum():
                query["sku"] = startswith_regex_filter(normalized_search, case_insensitive=False)
            else:
                query["$or"] = [
                    {"name": regex_filter(normalized_search)},
                    {"sku": regex_filter(normalized_search)},
                ]
        projection = {"_id": 0}
        if not include_cost:
            projection["cost"] = 0
        if cursor:
            return await self.list_cursor_page(
                query,
                page_size,
                sort_field="created_at",
                projection=projection,
                cursor=cursor,
            )
        return await self.list_page(
            query,
            page,
            page_size,
            sort=[("created_at", DESCENDING)],
            projection=projection,
        )

    async def get_store_product(self, store_id: str, product_id: str) -> dict | None:
        return await self.find_one(
            {"_id": product_id, "store_id": store_id, "deleted_at": None},
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
