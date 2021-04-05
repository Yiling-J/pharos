from kubernetes.dynamic import DynamicClient


class QuerySet:
    """Represent a lazy database lookup for a set of objects."""

    def __init__(self, model=None, using=None):
        self.model = model
        self._client = using
        self._result_cache = None
        self._query = []
        self.api_kwargs = {}

    @property
    def query(self):
        return self._query

    def filter(self, **kwargs):
        clone = self._clone()
        for k, v in kwargs.items():
            field = getattr(clone.model, k, None)
            if not field:
                raise
            clone._query.append({'operator': field.operator, 'value': v})
        return clone

    def all(self):
        return self._clone()

    def get(self, **kwargs):
        clone = self.filter(kwargs)
        num = len(clone)
        if num == 1:
            return clone._result_cache[0]
        if not num:
            raise
        raise

    def __repr__(self):
        data = list(self)
        return '<%s %r>' % (self.__class__.__name__, data)

    def __len__(self):
        self._fetch_all()
        return len(self._result_cache)

    def __iter__(self):
        self._fetch_all()

        return iter(self._result_cache)

    def _get_result(self):
        client = DynamicClient(self._client)

        for item in [i for i in self._query if i['operator'].type == 'PRE']:
            item['operator'].update_queryset(self, item['value'])
        results = client.resources.get(
            api_version=self.model.Meta.api_version,
            kind=self.model.Meta.kind,
            **self.api_kwargs
        )
        self._result_cache = results

        for item in [i for i in self._query if i['operator'].type == 'POST']:
            item['operator'].update_queryset(self, item['value'])

        self._result_cache = [self.model(
            _client=self._client,
            k8s_object=i
        ) for i in self._result_cache]
        return self._result_cache

    def _fetch_all(self):
        if self._result_cache is None:
            self._get_result()

    def _clone(self):
        c = self.__class__(
            model=self.model,
            using=self._client,

        )
        c._query = self._query
        return c
