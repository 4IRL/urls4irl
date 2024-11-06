"""Make unique URL per UTub

Revision ID: 799cc1c01a1c
Revises: d5abefc6c65a
Create Date: 2024-11-04 17:22:55.876426

"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "799cc1c01a1c"
down_revision = "d5abefc6c65a"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("UtubUrls", schema=None) as batch_op:
        batch_op.create_unique_constraint("unique_url_per_utub", ["utubID", "urlID"])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("UtubUrls", schema=None) as batch_op:
        batch_op.drop_constraint("unique_url_per_utub", type_="unique")
    # ### end Alembic commands ###
