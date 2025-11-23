from dataclasses import dataclass

from src.models.urls import Urls
from src.urls.constants import URLState


@dataclass
class ValidatedUrl:
    url: Urls
    url_state: URLState
