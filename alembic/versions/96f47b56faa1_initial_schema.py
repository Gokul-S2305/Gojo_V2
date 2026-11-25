"""initial_schema

Revision ID: 96f47b56faa1
Revises: 
Create Date: 2026-11-09 19:07:35.159591

"""
from typing import Sequence, Union

from alembic import op
from sqlmodel import SQLModel


# revision identifiers, used by Alembic.
revision: str = '96f47b56faa1'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the complete schema for a fresh database."""
    from app import models  # noqa: F401
    bind = op.get_bind()
    SQLModel.metadata.create_all(bind)


def downgrade() -> None:
    from app import models  # noqa: F401
    bind = op.get_bind()
    SQLModel.metadata.drop_all(bind)
