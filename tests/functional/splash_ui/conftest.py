# Standard library
from datetime import datetime

# External libraries
import pytest
from sqlalchemy import text

import tests.functional.constants as const

# Internal libraries


@pytest.fixture(scope="module")
def add_test_user(provide_engine):
    engine = provide_engine

    with engine.begin() as con:
        # Define the SQL query
        sql_query = text(
            """
            INSERT INTO "Users" (username, email, password, created_at)
            SELECT :username, :email, :password, :created_at
            WHERE NOT EXISTS (
                SELECT 1 FROM "Users" WHERE username = :username
            )
            RETURNING id
            """
        )

        # Bind user data to the query
        sql_params = {
            "username": const.USERNAME_TEST,
            "email": const.PASSWORD_TEST,
            "password": const.PASSWORD_TEST,
            "created_at": datetime.utcnow(),
        }

        # Execute the query
        result = con.execute(sql_query, **sql_params)

        # Check the result
        if not result.all():
            print(f"User with email '{const.PASSWORD_TEST}' already exists.")
        else:
            # Implement
            print("Unimplemented")
