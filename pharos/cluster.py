from kubernetes import config


class Cluster:

    def __init__(self, k8s_config):
        self.api_client = config.new_client_from_config(context=k8s_config)

    class Meta:
        support_models = []
