# Pharos(WIP)

Managing Kubernetes resources in Python.


## Example

create client

```python
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config')
```

create client with settings

```python
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config', disable_compress=True, chunk_size=500)

# access settings
client.settings.chunk_size

```
basic query syntax, follow django ORM style

```python
from pharos.models import Deployment
from pharos.client import Client


client = Client('YOUR_PATH/.kube/config')

# select and get related
deployments = Deployment.objects.using(client).filter(namespace='default')
deployment = deployments[0]
pods = deployment.pods.all()

# select labels, also support chain select
Deployment.objects.using(client).filter(selector='app=test,version=v1')
Deployment.objects.using(client).filter(selector='app=test').filter(selector='version=v1')

# limit results
pods = Pod.objects.all().limit(100)

# refresh query
pods_refreshed = pods.all()

```

extend existing model

```python
from pharos.models import Deployment
from pharos.client import Client


class MyDeployment(Deployment):
    uid = models.JsonPathField(path="metadata.uid")

deployment = MyDeployment.objects.using(client).all()[0]
print(deployment.uid)

# you can use filter on custom fields!
deployments = MyDeployment.objects.using(client).filter(uid='123')

```

create your own model

```python
from pharos.models import K8smodel


class TestResource(K8smodel):

    class Meta:
        api_version = "v1"
        kind = "TestResource"

```
