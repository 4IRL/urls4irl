import nh3


def sanitize_user_input(user_input: str | None) -> str | None:
    if not user_input:
        return None

    if nh3.is_html(user_input):
        output = nh3.clean(user_input, tags=set(), attributes=None)
        cleaned_output = output.replace("&lt;", "<").replace("&gt;", ">")
        return cleaned_output if cleaned_output else None

    return user_input
