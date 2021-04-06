# Pharos(WIP)

Managing Kubernetes resources in Python.


## Example

```python
from pharos.models import Deployment
from pharos.k8s_utils import get_client_from_config


client = get_client_from_config('YOUR_PATH/.kube/config')


# select and get related
deployments = Deployment.objects.using(client).filter(namespace='default')
deployment = deployments[0]
pods = deployment.pods.all()


# select labels, also support chain select
Deployment.objects.using(client).filter(selector='app=test,version=v1')
Deployment.objects.using(client).filter(selector='app=test').filter(selector='version=v1')


# customize model with json path
class MyDeployment(Deployment):
    uid = models.QueryField(operator=operators.JsonPathOperator, path="metadata.uid")

deployment = MyDeployment.objects.using(client).all()[0]
print(deployment.uid)

```
