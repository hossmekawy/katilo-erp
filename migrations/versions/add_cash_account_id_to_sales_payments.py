"""Add cash_account_id to sales_payments table

Revision ID: add_cash_account_id_to_sales_payments
Revises: 
Create Date: 2023-07-10 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_cash_account_id_to_sales_payments'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Add cash_account_id column to sales_payments table
    with op.batch_alter_table('sales_payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cash_account_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(None, 'cash_accounts', ['cash_account_id'], ['id'])


def downgrade():
    # Remove cash_account_id column from sales_payments table
    with op.batch_alter_table('sales_payments', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_column('cash_account_id')
