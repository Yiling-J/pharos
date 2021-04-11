from jsonpath_ng.ext import parse


class BaseOperator:
    def __init__(self, path):
        self.path = path

    def get_value(self, obj):
        raise


class SelectorOperator(BaseOperator):
    type = "PRE"

    def get_value(self, obj):
        data = obj.k8s_object["spec"].get("selector")
        if data:
            labels = [f"{k}={v}" for k, v in data.get("matchLabels", {}).items()]
            expressions = [
                f'{i["key"]} {i["operator"]} {tuple(i["values"])}'
                for i in data.get("matchExpressions", [])
            ]
            return ",".join(labels + expressions)
        return None

    def update_queryset(self, qs, value, op):
        if "label_selector" in qs.api_kwargs:
            qs.api_kwargs["label_selector"] += f",{value}"
        else:
            qs.api_kwargs["label_selector"] = value


class ClientValueOperator(BaseOperator):
    type = "PRE"

    def get_value(self, obj):
        jsonpath_expr = parse(self.path)
        matches = jsonpath_expr.find(obj.k8s_object)
        return matches[0].value if matches else None

    def update_queryset(self, qs, value, op):
        qs.api_kwargs[self.field_name] = value
        return qs


def find_jsonpath_value(jsonpath_expr, data):
    matches = [i.value for i in jsonpath_expr.find(data)]
    return matches[0] if matches else None


class JsonPathOperator(BaseOperator):
    type = "POST"

    def __init__(self, path):
        super().__init__(path)
        self.jsonpath_expr = parse(self.path)

    def get_value(self, obj):
        jsonpath_expr = parse(self.path)
        matches = jsonpath_expr.find(obj.k8s_object)
        return matches[0].value if matches else None

    def verify(self, obj, data, op):
        if op == "EQUAL":
            return find_jsonpath_value(self.jsonpath_expr, obj) == data
        elif op == "IN":
            return find_jsonpath_value(self.jsonpath_expr, obj) in data
        else:
            raise


class OwnerRefOperator(BaseOperator):
    type = "POST"

    def __init__(self, path):
        self.path = "$.metadata.ownerReferences[*].uid"
        self.jsonpath_expr = parse(self.path)

    def get_value(self, obj):
        return obj["metadata"].get("ownerReferences")

    def verify(self, obj, data, op):
        if op == "IN":
            values = {owner.k8s_object["metadata"]["uid"] for owner in data}
        else:
            values = {data.k8s_object["metadata"]["uid"]}

        return bool({i.value for i in self.jsonpath_expr.find(obj)} & set(values))
