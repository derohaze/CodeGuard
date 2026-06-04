from __future__ import annotations

from datetime import datetime
from typing import Any

from pymongo import ASCENDING, DESCENDING

from core.app.models.common.base import utc_now
from core.app.models.identity.entity import (
    Membership,
    Permission,
    RefreshToken,
    Role,
    TeamAccount,
    User,
)
from core.app.repositories.common.base import MongoRepository


class UserRepository(MongoRepository):
    collection_name = "users"

    async def get_by_email(self, email: str) -> dict | None:
        return await self.find_one({"email": email.lower()})

    async def get_by_id(self, user_id: str) -> dict | None:
        return await self.find_one({"_id": user_id})

    async def list_by_ids(self, user_ids: list[str]) -> dict[str, dict]:
        ids = list(
            dict.fromkeys(
                safe_id
                for user_id in user_ids
                if (safe_id := str(user_id).strip())
            )
        )
        if not ids:
            return {}
        rows = await self.collection.find(
            {"_id": {"$in": ids}},
            {"_id": 0},
        ).to_list(length=len(ids))
        return {str(row["id"]): row for row in rows if row.get("id")}

    async def get_by_username(self, username: str) -> dict | None:
        return await self.find_one({"username": username.lower()})

    async def count_all(self) -> int:
        return int(await self.collection.count_documents({}))

    async def create(self, user: User) -> dict:
        return await self.insert_model(user)

    async def upsert(self, user: User) -> dict:
        return await self.upsert_model(user)

    async def set_active(self, user_id: str, active: bool) -> None:
        await self.collection.update_one(
            {"_id": user_id},
            {"$set": {"active": active, "updated_at": utc_now()}},
        )

    async def update_profile(
        self,
        user_id: str,
        *,
        name: str | None = None,
        username: str | None = None,
        email: str | None = None,
        active: bool | None = None,
    ) -> dict | None:
        patch: dict[str, Any] = {"updated_at": utc_now()}
        if name is not None:
            patch["name"] = name
        if username is not None:
            patch["username"] = username.lower()
        if email is not None:
            patch["email"] = email.lower()
        if active is not None:
            patch["active"] = active
        await self.collection.update_one({"_id": user_id}, {"$set": patch})
        return await self.get_by_id(user_id)

    async def update_new_device_login_email_notifications(
        self,
        user_id: str,
        enabled: bool,
    ) -> dict | None:
        await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "new_device_login_email_notifications_enabled": enabled,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(user_id)

    async def update_password(self, user_id: str, password_hash: str) -> dict | None:
        await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_changed_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(user_id)

    async def update_default_workspace(self, user_id: str, workspace_id: str) -> dict | None:
        await self.collection.update_one(
            {"_id": user_id},
            {"$set": {"workspace_id": workspace_id, "updated_at": utc_now()}},
        )
        return await self.get_by_id(user_id)

    async def update_two_factor_pending(self, user_id: str, encrypted_secret: str) -> dict | None:
        await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "two_factor_pending_secret_encrypted": encrypted_secret,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(user_id)

    async def enable_two_factor(
        self,
        user_id: str,
        encrypted_secret: str,
        backup_code_hashes: list[str],
    ) -> dict | None:
        now = utc_now()
        await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "two_factor_enabled": True,
                    "two_factor_secret_encrypted": encrypted_secret,
                    "two_factor_pending_secret_encrypted": None,
                    "two_factor_backup_code_hashes": backup_code_hashes,
                    "two_factor_enabled_at": now,
                    "updated_at": now,
                }
            },
        )
        return await self.get_by_id(user_id)

    async def disable_two_factor(self, user_id: str) -> dict | None:
        await self.collection.update_one(
            {"_id": user_id},
            {
                "$set": {
                    "two_factor_enabled": False,
                    "two_factor_secret_encrypted": None,
                    "two_factor_pending_secret_encrypted": None,
                    "two_factor_backup_code_hashes": [],
                    "two_factor_enabled_at": None,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(user_id)

    async def consume_two_factor_backup_code(self, user_id: str, code_hash: str) -> bool:
        result = await self.collection.find_one_and_update(
            {"_id": user_id, "two_factor_backup_code_hashes": code_hash},
            {
                "$pull": {"two_factor_backup_code_hashes": code_hash},
                "$set": {"updated_at": utc_now()},
            },
        )
        return result is not None


class TeamAccountRepository(MongoRepository):
    collection_name = "team_accounts"

    async def get_by_email(self, email: str) -> dict | None:
        return await self.find_one({"email": email.lower()})

    async def get_by_id(self, account_id: str) -> dict | None:
        return await self.find_one({"_id": account_id})

    async def list_by_ids(self, account_ids: list[str]) -> dict[str, dict]:
        ids = list(
            dict.fromkeys(
                safe_id
                for account_id in account_ids
                if (safe_id := str(account_id).strip())
            )
        )
        if not ids:
            return {}
        rows = await self.collection.find(
            {"_id": {"$in": ids}},
            {"_id": 0},
        ).to_list(length=len(ids))
        return {str(row["id"]): row for row in rows if row.get("id")}

    async def get_by_username(self, username: str) -> dict | None:
        return await self.find_one({"username": username.lower()})

    async def count_all(self) -> int:
        return int(await self.collection.count_documents({}))

    async def create(self, account: TeamAccount) -> dict:
        return await self.insert_model(account)

    async def update_profile(
        self,
        account_id: str,
        *,
        name: str | None = None,
        username: str | None = None,
        email: str | None = None,
        active: bool | None = None,
    ) -> dict | None:
        patch: dict[str, Any] = {"updated_at": utc_now()}
        if name is not None:
            patch["name"] = name
        if username is not None:
            patch["username"] = username.lower()
        if email is not None:
            patch["email"] = email.lower()
        if active is not None:
            patch["active"] = active
        await self.collection.update_one({"_id": account_id}, {"$set": patch})
        return await self.get_by_id(account_id)

    async def update_new_device_login_email_notifications(
        self,
        account_id: str,
        enabled: bool,
    ) -> dict | None:
        await self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "new_device_login_email_notifications_enabled": enabled,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(account_id)

    async def update_password(self, account_id: str, password_hash: str) -> dict | None:
        await self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "password_hash": password_hash,
                    "password_changed_at": utc_now(),
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(account_id)

    async def update_two_factor_pending(
        self,
        account_id: str,
        encrypted_secret: str,
    ) -> dict | None:
        await self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "two_factor_pending_secret_encrypted": encrypted_secret,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(account_id)

    async def enable_two_factor(
        self,
        account_id: str,
        encrypted_secret: str,
        backup_code_hashes: list[str],
    ) -> dict | None:
        now = utc_now()
        await self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "two_factor_enabled": True,
                    "two_factor_secret_encrypted": encrypted_secret,
                    "two_factor_pending_secret_encrypted": None,
                    "two_factor_backup_code_hashes": backup_code_hashes,
                    "two_factor_enabled_at": now,
                    "updated_at": now,
                }
            },
        )
        return await self.get_by_id(account_id)

    async def disable_two_factor(self, account_id: str) -> dict | None:
        await self.collection.update_one(
            {"_id": account_id},
            {
                "$set": {
                    "two_factor_enabled": False,
                    "two_factor_secret_encrypted": None,
                    "two_factor_pending_secret_encrypted": None,
                    "two_factor_backup_code_hashes": [],
                    "two_factor_enabled_at": None,
                    "updated_at": utc_now(),
                }
            },
        )
        return await self.get_by_id(account_id)

    async def consume_two_factor_backup_code(self, account_id: str, code_hash: str) -> bool:
        result = await self.collection.find_one_and_update(
            {"_id": account_id, "two_factor_backup_code_hashes": code_hash},
            {
                "$pull": {"two_factor_backup_code_hashes": code_hash},
                "$set": {"updated_at": utc_now()},
            },
        )
        return result is not None

    async def hard_delete(self, account_id: str) -> bool:
        result = await self.collection.delete_one({"_id": account_id})
        return result.deleted_count > 0


class MembershipRepository(MongoRepository):
    collection_name = "memberships"

    async def get_active(
        self,
        *,
        user_id: str,
        workspace_id: str | None = None,
        store_id: str | None = None,
        role: str | None = None,
    ) -> dict | None:
        query: dict[str, object] = {"user_id": user_id, "active": True}
        if workspace_id:
            query["workspace_id"] = workspace_id
        if store_id:
            query["store_id"] = store_id
        if role:
            query["role"] = role
        return await self.find_one(query)

    async def list_for_user(self, user_id: str) -> list[dict]:
        cursor = (
            self.collection.find({"user_id": user_id, "active": True}, {"_id": 0})
            .sort([("workspace_id", ASCENDING)])
            .limit(100)
        )
        return await cursor.to_list(length=100)

    async def list_active_memberships_for_users_in_workspaces(
        self,
        user_ids: list[str],
        workspace_ids: set[str],
    ) -> list[dict]:
        """Batch fetch active memberships for many users, filtered to workspace_ids (owner scope)."""
        if not user_ids or not workspace_ids:
            return []
        cursor = self.collection.find(
            {
                "user_id": {"$in": user_ids},
                "active": True,
                "workspace_id": {"$in": list(workspace_ids)},
            },
            {"_id": 0},
        ).limit(2000)
        return await cursor.to_list(length=2000)

    async def list_workspace_memberships(self, workspace_id: str) -> list[dict]:
        cursor = (
            self.collection.find({"workspace_id": workspace_id}, {"_id": 0})
            .sort([("role", ASCENDING), ("user_id", ASCENDING)])
            .limit(500)
        )
        return await cursor.to_list(length=500)

    async def upsert(self, membership: Membership) -> dict:
        return await self.upsert_model(membership)

    async def upsert_for_user_workspace(self, membership: Membership) -> dict:
        document = membership.to_mongo()
        document.pop("_id", None)
        query = {"user_id": membership.user_id, "workspace_id": membership.workspace_id}
        if membership.store_id:
            query["store_id"] = membership.store_id
        existing = await self.find_one(query)
        if existing:
            await self.collection.update_one(
                {"_id": existing["id"]},
                {
                    "$set": {
                        **document,
                        "id": existing["id"],
                        "created_at": existing.get("created_at", membership.created_at),
                        "updated_at": utc_now(),
                    }
                },
            )
            return await self.find_one({"_id": existing["id"]}) or {}
        return await self.insert_model(membership)

    async def set_membership_active(
        self,
        *,
        user_id: str,
        workspace_id: str,
        active: bool,
    ) -> None:
        await self.collection.update_one(
            {"user_id": user_id, "workspace_id": workspace_id},
            {"$set": {"active": active, "updated_at": utc_now()}},
        )

    async def get_membership_row(
        self,
        *,
        user_id: str,
        workspace_id: str,
    ) -> dict | None:
        return await self.find_one({"user_id": user_id, "workspace_id": workspace_id})

    async def remove_workspace_access_except(
        self,
        *,
        user_id: str,
        allowed_workspace_ids: list[str],
        scoped_workspace_ids: list[str],
    ) -> None:
        memberships = await self.collection.find(
            {"user_id": user_id},
            {"_id": 0},
        ).to_list(length=500)
        for membership in memberships:
            if (
                membership["workspace_id"] in scoped_workspace_ids
                and membership["workspace_id"] not in allowed_workspace_ids
            ):
                await self.set_membership_active(
                    user_id=user_id,
                    workspace_id=membership["workspace_id"],
                    active=False,
                )

    async def deactivate_workspace_memberships(self, workspace_id: str) -> None:
        await self.collection.update_many(
            {"workspace_id": workspace_id},
            {"$set": {"active": False, "updated_at": utc_now()}},
        )

    async def deactivate_store_memberships(self, store_id: str) -> None:
        await self.collection.update_many(
            {"store_id": store_id},
            {"$set": {"active": False, "updated_at": utc_now()}},
        )

    async def hard_delete_all_for_user(self, user_id: str) -> None:
        await self.collection.delete_many({"user_id": user_id})

    async def hard_delete_for_user_in_workspaces(
        self,
        *,
        user_id: str,
        workspace_ids: list[str],
    ) -> None:
        scoped = [workspace_id for workspace_id in workspace_ids if workspace_id]
        if not scoped:
            return
        await self.collection.delete_many({"user_id": user_id, "workspace_id": {"$in": scoped}})


class RoleRepository(MongoRepository):
    collection_name = "roles"

    async def get_active(self, workspace_id: str, role: str, store_id: str | None = None) -> dict | None:
        query: dict[str, object] = {"workspace_id": workspace_id, "name": role, "active": True}
        if store_id:
            query["store_id"] = store_id
        return await self.find_one(query)

    async def upsert(self, role: Role) -> dict:
        return await self.upsert_model(role)

    async def deactivate_workspace_roles(self, workspace_id: str) -> None:
        await self.collection.update_many(
            {"workspace_id": workspace_id},
            {"$set": {"active": False, "updated_at": utc_now()}},
        )

    async def deactivate_store_roles(self, store_id: str) -> None:
        await self.collection.update_many(
            {"store_id": store_id},
            {"$set": {"active": False, "updated_at": utc_now()}},
        )


class PermissionRepository(MongoRepository):
    collection_name = "permissions"

    async def upsert(self, permission: Permission) -> dict:
        return await self.upsert_model(permission)


class RefreshTokenRepository(MongoRepository):
    collection_name = "refresh_tokens"

    async def create(self, refresh_token: RefreshToken) -> dict:
        return await self.insert_model(refresh_token)

    async def get_active_by_hash(self, token_hash: str) -> dict | None:
        return await self.find_one({"token_hash": token_hash, "revoked_at": None})

    async def get_by_hash(self, token_hash: str) -> dict | None:
        return await self.find_one({"token_hash": token_hash})

    async def get_for_user(self, *, token_id: str, user_id: str) -> dict | None:
        return await self.find_one({"_id": token_id, "user_id": user_id}, {"_id": 0})

    async def list_for_user(self, user_id: str, *, limit: int = 100) -> list[dict]:
        safe_limit = min(100, max(1, limit))
        cursor = (
            self.collection.find({"user_id": user_id}, {"_id": 0, "token_hash": 0})
            .sort(
                [
                    ("last_seen_at", DESCENDING),
                    ("updated_at", DESCENDING),
                    ("created_at", DESCENDING),
                ]
            )
            .limit(safe_limit)
        )
        return await cursor.to_list(length=safe_limit)

    async def has_device_for_user(
        self,
        *,
        user_id: str,
        exclude_device_id: str,
    ) -> bool:
        return bool(
            await self.collection.find_one(
                {
                    "user_id": user_id,
                    "device_id": {"$nin": ["", exclude_device_id]},
                },
                {"_id": 1},
            )
        )

    async def revoke(self, token_id: str, revoked_at: datetime) -> None:
        await self.collection.update_one(
            {"_id": token_id, "revoked_at": None},
            {"$set": {"revoked_at": revoked_at, "updated_at": revoked_at}},
        )

    async def revoke_for_user(self, user_id: str, revoked_at: datetime) -> None:
        records = await self.collection.find(
            {"user_id": user_id, "revoked_at": None},
            {"_id": 0},
        ).to_list(length=500)
        for record in records:
            await self.revoke(record["id"], revoked_at)

    async def revoke_for_workspace(self, workspace_id: str, revoked_at: datetime) -> None:
        records = await self.collection.find(
            {"workspace_id": workspace_id, "revoked_at": None},
            {"_id": 0},
        ).to_list(length=500)
        for record in records:
            await self.revoke(record["id"], revoked_at)

    async def revoke_for_store(self, store_id: str, revoked_at: datetime) -> None:
        await self.collection.update_many(
            {"store_id": store_id, "revoked_at": None},
            {"$set": {"revoked_at": revoked_at, "updated_at": revoked_at}},
        )

    async def delete_inactive_for_user(self, user_id: str, *, now: datetime) -> int:
        result = await self.collection.delete_many(
            {
                "user_id": user_id,
                "$or": [
                    {"revoked_at": {"$ne": None}},
                    {"expires_at": {"$lte": now}},
                ],
            }
        )
        return int(result.deleted_count)
