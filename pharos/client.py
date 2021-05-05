import kubernetes
from collections import UserDict


default_settings = {
    "disable_compress": False,
    "enable_chunk": True,
    "chunk_size": 200,
    "template_engine": "pharos.jinja.JinjaEngine",
    "jinja_loader": None,
}


class Settings(UserDict):
    def __init__(self):
        super().__init__()
        self.data.update(default_settings)

    def __getattr__(self, name):
        try:
            return self.data[name]
        except KeyError:
            raise AttributeError("setting not found")


class Client:
    k8s_client = None

    def __init__(self, path, context=None, **kwargs):
        self.path = path
        self.context = context
        self.k8s_client = kubernetes.config.new_client_from_config(
            path, context=context
        )
        self.dynamic_client = kubernetes.dynamic.DynamicClient(self.k8s_client)
        self.settings = Settings()
        self.settings.update(kwargs)

    def use_context(self, context):
        self.context = context
        self.k8s_client = kubernetes.config.new_client_from_config(
            self.path, context=context
        )
        self.dynamic_client = kubernetes.dynamic.DynamicClient(self.k8s_client)
