from jsonpath_ng.ext import parse


class BaseOperator:

    def __init__(self, path):
        self.path = path

    def get_value(self, obj):
        raise


class SelectorOperator(BaseOperator):
    type = 'PRE'

    def update_queryset(self, qs, value):
        if 'label_selector' in qs.api_kwargs:
            qs.api_kwargs['label_selector'] += f',{value}'
        else:
            qs.api_kwargs['label_selector'] = value


class ClientValueOperator(BaseOperator):
    type = 'PRE'

    def get_value(self, obj):
        jsonpath_expr = parse(self.path)
        matches = jsonpath_expr.find(obj)
        return matches[0].value if matches else None

    def update_queryset(self, qs, value):
        qs.api_kwargs[self.field_name] = value
        return qs


class JsonPathOperator(BaseOperator):
    type = 'POST'

    def get_value(self, obj):
        jsonpath_expr = parse(self.path)
        matches = jsonpath_expr.find(obj)
        return matches[0].value if matches else None


class OwnerRefOperator(BaseOperator):
    type = 'POST'

    def get_value(self, obj):
        return obj['metadata'].get('ownerReferences')

    def update_queryset(self, qs, owner):
        uid = owner.k8s_object['metadata']['uid']
        jsonpath_expr = parse(
            f'$.metadata.ownerReferences[?(@.uid=="{uid}")]'
        )
        qs._result_cache = [i for i in qs if jsonpath_expr.find(i)]
