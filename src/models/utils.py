from dataclasses import dataclass

from src.models.users import Users


@dataclass
class VerifyTokenResponse:
    is_expired: bool = False
    user: Users | None = None
    failed_due_to_exception: bool = False
