from __future__ import annotations
from pydantic import BaseModel, Field

from backend.members.constants import MemberAddSource
from backend.utils.constants import USER_CONSTANTS


class AddMemberRequest(BaseModel):
    username: str = Field(
        min_length=USER_CONSTANTS.MIN_USERNAME_LENGTH,
        max_length=USER_CONSTANTS.MAX_USERNAME_LENGTH,
        description="Username of the member to add",
    )
    source: MemberAddSource = Field(
        default=MemberAddSource.EXACT_USERNAME,
        description=(
            "Where the add originated: a co-member typeahead pick "
            "(search_result) or the exact-username outsider path "
            "(exact_username, the default when omitted)"
        ),
    )
