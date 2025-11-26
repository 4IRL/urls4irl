from dataclasses import dataclass

from src.models.urls import Urls
from src.urls.constants import URLNormalizationResult, URLState


@dataclass
class NormalizedUrl:
    input_url_string: str
    time_to_validate: float
    status: URLNormalizationResult | None = URLNormalizationResult.VALID_URL
    exception: Exception | None = None
    validated_url: str = ""


@dataclass
class ValidatedUrl:
    url_state: URLState
    normalized_url: NormalizedUrl
    url: Urls | None = None

    def get_validated_url(self) -> str:
        if self.url is None:
            return ""

        return self.url.url_string
