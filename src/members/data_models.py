from dataclasses import dataclass

from src.models.users import Users


@dataclass
class ValidatedMember:
    user: Users
    in_utub: bool
