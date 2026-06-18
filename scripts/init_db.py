"""Initialize database schema and seed demo data.

Usage: python scripts/init_db.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import engine, Base, SessionLocal
from app.models import User, Contract, ContractStatus, UserRole, UserStatus
import bcrypt
import datetime


def seed_data():
    """Create demo accounts and sample data."""
    db = SessionLocal()

    try:
        # Check if users already exist
        existing = db.query(User).first()
        if existing:
            print("Database already initialized. Skipping seed.")
            return

        # Create demo users with bcrypt password hashes
        users = [
            {
                "username": "admin",
                "password": "admin123",
                "display_name": "系统管理员",
                "email": "admin@example.com",
                "role": UserRole.admin,
                "status": UserStatus.active,
            },
            {
                "username": "manager",
                "password": "manager123",
                "display_name": "合同经理",
                "email": "manager@example.com",
                "role": UserRole.manager,
                "status": UserStatus.active,
            },
            {
                "username": "viewer",
                "password": "viewer123",
                "display_name": "只读用户",
                "email": "viewer@example.com",
                "role": UserRole.viewer,
                "status": UserStatus.active,
            },
        ]

        db_users = {}
        for u in users:
            hashed = bcrypt.hashpw(u["password"].encode("utf-8"), bcrypt.gensalt())
            user = User(
                username=u["username"],
                password_hash=hashed.decode("utf-8"),
                display_name=u["display_name"],
                email=u["email"],
                role=u["role"],
                status=u["status"],
            )
            db.add(user)
            db.flush()
            db_users[u["username"]] = user
            print(f"  Created user: {u['username']} (role={u['role'].value})")

        # Create sample contracts
        sample_contracts = [
            {
                "contract_no": "HT-2026-001",
                "title": "办公室租赁合同",
                "party_a": "ABC科技有限公司",
                "party_b": "XYZ物业管理公司",
                "amount": 120000.00,
                "status": ContractStatus.signed,
                "sign_date": datetime.datetime(2026, 1, 15),
                "start_date": datetime.datetime(2026, 2, 1),
                "end_date": datetime.datetime(2027, 1, 31),
                "description": "上海市浦东新区XX路XX号办公室租赁",
            },
            {
                "contract_no": "HT-2026-002",
                "title": "软件开发服务合同",
                "party_a": "ABC科技有限公司",
                "party_b": "DEF软件外包公司",
                "amount": 500000.00,
                "status": ContractStatus.pending,
                "sign_date": None,
                "start_date": datetime.datetime(2026, 6, 1),
                "end_date": datetime.datetime(2026, 12, 31),
                "description": "企业管理系统定制开发",
            },
            {
                "contract_no": "HT-2026-003",
                "title": "设备采购合同",
                "party_a": "ABC科技有限公司",
                "party_b": "GHI设备供应商",
                "amount": 85000.00,
                "status": ContractStatus.draft,
                "sign_date": None,
                "start_date": None,
                "end_date": None,
                "description": "服务器及网络设备采购",
            },
        ]

        for c in sample_contracts:
            contract = Contract(
                contract_no=c["contract_no"],
                title=c["title"],
                party_a=c["party_a"],
                party_b=c["party_b"],
                amount=c["amount"],
                status=c["status"],
                sign_date=c["sign_date"],
                start_date=c["start_date"],
                end_date=c["end_date"],
                description=c["description"],
                created_by=db_users["admin"].id,
            )
            db.add(contract)
            print(f"  Created contract: {c['contract_no']} (status={c['status'].value})")

        db.commit()
        print(f"\nInitialization complete: {len(users)} users, {len(sample_contracts)} contracts")

    except Exception as e:
        db.rollback()
        print(f"Error during seed: {e}")
        raise
    finally:
        db.close()


def main():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Tables created.")

    print("Seeding demo data...")
    seed_data()


if __name__ == "__main__":
    main()
