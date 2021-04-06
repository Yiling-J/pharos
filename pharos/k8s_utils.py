import kubernetes


def get_client_from_config(config_path):
    api_client = kubernetes.config.new_client_from_config(config_path)
    return kubernetes.dynamic.DynamicClient(api_client)
