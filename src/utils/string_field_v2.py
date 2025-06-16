from wtforms import StringField


class StringFieldV2(StringField):
    def get(self) -> str:
        if self.data is None or not isinstance(self.data, str):
            return ""
        return self.data.strip()
