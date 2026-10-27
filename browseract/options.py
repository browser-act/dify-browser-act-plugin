from collections import Counter

from dify_plugin.entities import I18nObject, ParameterOption

from browseract.errors import BrowserActError


def parameter_options(items: list[dict], value_key: str) -> list[ParameterOption]:
    values = set()
    for item in items:
        value = item.get(value_key)
        if (
            type(value) not in (str, int)
            or (isinstance(value, str) and not value.strip())
            or (isinstance(value, int) and value <= 0)
            or not isinstance(item.get("name"), str)
            or not item["name"]
            or str(value) in values
        ):
            raise BrowserActError("BrowserAct returned invalid options or duplicate IDs. Refresh and try again.")
        values.add(str(value))
    counts = Counter(item["name"] for item in items)
    result = []
    for item in items:
        value = str(item[value_key])
        name = item["name"]
        display_name = name[:100] + "…" if len(name) > 100 else name
        label = f"{display_name} ({value})" if counts[name] > 1 else display_name
        result.append(ParameterOption(
            value=value,
            label=I18nObject(en_US=label, zh_Hans=label),
        ))
    return result
