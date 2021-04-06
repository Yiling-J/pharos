from jsonpath_ng.ext import parse


class BaseOperator:

    def __init__(self, path):
        self.path = path

    def get_value(self, obj):
        raise


class SelectorOperator(BaseOperator):
    type = 'PRE'

    def get_value(self, obj):
        data = obj.k8s_object['spec'].get('selector')
        if data:
            labels = [f'{k}={v}' for k, v in data.get('matchLabels', {}).items()]
            expressions = [f'{i["key"]} {i["operator"]} {tuple(i["values"])}' for i in data.get('matchExpressions', [])]
            return ','.join(labels + expressions)
        return None

    def update_queryset(self, qs, value, op):
        if 'label_selector' in qs.api_kwargs:
            qs.api_kwargs['label_selector'] += f',{value}'
        else:
            qs.api_kwargs['label_selector'] = value


class ClientValueOperator(BaseOperator):
    type = 'PRE'

    def get_value(self, obj):
        jsonpath_expr = parse(self.path)
        matches = jsonpath_expr.find(obj.k8s_object)
        return matches[0].value if matches else None

    def update_queryset(self, qs, value, op):
        qs.api_kwargs[self.field_name] = value
        return qs


class JsonPathOperator(BaseOperator):
    type = 'POST'

    def get_value(self, obj):
        jsonpath_expr = parse(self.path)
        matches = jsonpath_expr.find(obj.k8s_object)
        return matches[0].value if matches else None

    def update_queryset(self, qs, value, op):
        jsonpath_expr = parse(self.path)
        if op == 'EQUAL':
            qs._result_cache = [
                i for i in qs if jsonpath_expr.find(i)[:1] == [value]
            ]
        elif op == 'IN':
            qs._result_cache = [
                i for i in qs if jsonpath_expr.find(i)[:1] in value
            ]
        else:
            raise


class OwnerRefOperator(BaseOperator):
    type = 'POST'

    def get_value(self, obj):
        return obj['metadata'].get('ownerReferences')

    def update_queryset(self, qs, data, op):
        if op == 'IN':
            values = {owner.k8s_object['metadata']['uid'] for owner in data}
        else:
            values = {data.k8s_object['metadata']['uid']}

        jsonpath_expr = parse(f'$.metadata.ownerReferences[*].uid')
        qs._result_cache = [
            i for i in qs if {m.value for m in jsonpath_expr.find(i)} & set(values)
        ]
