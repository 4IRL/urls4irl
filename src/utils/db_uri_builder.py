def build_db_uri(
    username: str | None, password: str | None, database: str | None, database_host: str
) -> str | None:
    if not all(
        (
            username,
            password,
            database,
        )
    ):
        return None
    return f"postgresql://{username}:{password}@{database_host}:5432/{database}"
