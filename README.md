# Pharos(WIP)

Managing Kubernetes resources in Python.


## Example

```python
from pharos.models import Deployment
from pharos.k8s_utils import get_client_from_config


client = get_client_from_config('YOUR_PATH/.kube/config')

deployments = Deployment.objects.using(client).filter(namespace='default')
deployment = deployments[0]
pods = deployment.pods.all()

```
