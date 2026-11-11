import pytest
from app.routers.dashboard import calculate_expense_split
from app.models import User


def test_expense_split_calculation():
    # Setup 3 members
    u1 = User(id=1, email="alice@test.com", full_name="Alice")
    u2 = User(id=2, email="bob@test.com", full_name="Bob")
    u3 = User(id=3, email="charlie@test.com", full_name="Charlie")
    members = [u1, u2, u3]

    # Alice paid 900 for dinner
    expenses = [
        {"amount": 900.0, "user_id": 1, "purpose": "Dinner"}
    ]

    total, share, balances, settlements = calculate_expense_split(members, expenses)

    assert total == 900.0
    assert share == 300.0

    # Alice paid 900, share 300 -> net +600 (owed)
    assert balances[1]["paid"] == 900.0
    assert balances[1]["net"] == 600.0

    # Bob paid 0, share 300 -> net -300 (owes)
    assert balances[2]["paid"] == 0.0
    assert balances[2]["net"] == -300.0

    # Charlie paid 0, share 300 -> net -300 (owes)
    assert balances[3]["paid"] == 0.0
    assert balances[3]["net"] == -300.0

    # Settlements should have Bob -> Alice 300 and Charlie -> Alice 300
    assert len(settlements) == 2
    settlement_from_ids = {s["from_id"] for s in settlements}
    assert settlement_from_ids == {2, 3}
    for s in settlements:
        assert s["to_id"] == 1
        assert s["amount"] == 300.0


def test_expense_split_empty():
    total, share, balances, settlements = calculate_expense_split([], [])
    assert total == 0
    assert share == 0.0
    assert settlements == []
