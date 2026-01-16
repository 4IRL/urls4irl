from wtforms import StringField, TextAreaField


class StringFieldV2(StringField):
    def get(self) -> str:
        if self.data is None or not isinstance(self.data, str):
            return ""
        return self.data.strip()


class TextAreaFieldV2(TextAreaField):
    def get(self) -> str:
        if self.data is None or not isinstance(self.data, str):
            return ""
        return self.data.strip()
