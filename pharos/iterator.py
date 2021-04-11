class SimpleIterator:
    def __init__(self, client, api_spec):
        self.client = client
        self.api_spec = api_spec

    def get(self, **kwargs):
        result = self.api_spec.get(**kwargs).to_dict()
        if "items" not in result:
            result = [result]
        else:
            result = result["items"]
        return iter(result)


class ChunkIterator(SimpleIterator):
    def get(self, **kwargs):
        chunk_size = self.client.settings.chunk_size
        _continue = None
        END = "END"
        kwargs["limit"] = chunk_size

        while _continue != END:
            kwargs["_continue"] = _continue
            response = self.api_spec.get(**kwargs).to_dict()

            if "items" not in response:
                yield response
                break

            _continue = response["metadata"].get("continue") or END
            results = response["items"]

            while results:
                yield results.pop(0)
