from alembic import op
import sqlalchemy as sa

revision = '0001_initial'
down_revision = None
branch_labels = None
depend_on = None


def upgrade() -> None:
    op.create_table(
        'investigations',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('investigation_id', sa.String(24), nullable=False, unique=True),
        sa.Column('entity_type', sa.String(64), nullable=False),
        sa.Column('target', sa.String(256), nullable=False),
        sa.Column('status', sa.String(32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('timeline', sa.Text, nullable=True),
    )
    op.create_table(
        'findings',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('investigation_id', sa.Integer, sa.ForeignKey('investigations.id'), nullable=False),
        sa.Column('category', sa.String(64), nullable=False),
        sa.Column('title', sa.String(256), nullable=False),
        sa.Column('details', sa.Text, nullable=False),
        sa.Column('source', sa.String(256), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('findings')
    op.drop_table('investigations')
