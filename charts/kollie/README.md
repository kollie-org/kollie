# Kollie Helm Chart

This chart is pushed to GHCR as an OCI artifact. You can use in Flux like this:

```
apiVersion: source.toolkit.fluxcd.io/v1
kind: OCIRepository
metadata:
  name: kollie
  namespace: kollie
spec:
  interval: 12h
  layerSelector:
    mediaType: "application/vnd.cncf.helm.chart.content.v1.tar+gzip"
    operation: copy
  url: oci://ghcr.io/kollie-org/charts/kollie
  ref:
    tag: "0.1.0"
```

An example Helm Release of Kollie might look something like this:

```
apiVersion: helm.toolkit.fluxcd.io/v2
kind: HelmRelease
metadata:
  name: kollie
  namespace: kollie
spec:
  chartRef:
    kind: OCIRepository
    name: kollie
  interval: 1h
  values:
    replicaCount: 2
    ingress:
      className: ingress-nginx-internal
      enabled: true
      hosts:
        - host: kollie.mydomain.com
          paths:
            - path: /
              pathType: Prefix
      tls:
        - hosts:
            - kollie.mydomain.com
      annotations:
        # nginx.ingress.kubernetes.io/configuration-snippet: |
        #   proxy_set_header x-auth-request-email "placeholder@mydomain.com";
        #   proxy_set_header x-auth-request-user "Placeholder User";
        nginx.ingress.kubernetes.io/auth-signin: "https://auth.mydomain.com/oauth2/start?rd=https%3A%2F%2F$host$request_uri"
        nginx.ingress.kubernetes.io/auth-url: "http://oauth2-proxy.auth.svc.cluster.local/oauth2/auth"
        nginx.ingress.kubernetes.io/auth-response-headers: "X-Auth-Request-User, X-Auth-Request-Email"
    resources:
      requests:
        cpu: 5m
        memory: 105Mi
      limits:
        memory: 300Mi
    daemon:
      resources:
        requests:
          cpu: 5m
          memory: 128Mi
        limits:
          memory: 384Mi
```

Please see [values.yaml](./values.yaml) for more details on how to configure Kollie. Watch this space for an example repository with a complete example.
