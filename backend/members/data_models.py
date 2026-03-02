from dataclasses import dataclass

from backend.models.users import Users


@dataclass
class ValidatedMember:
    user: Users
    in_utub: bool
