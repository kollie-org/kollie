import os

import structlog
from kubernetes import config

from kollie.constants import LOCAL_STAGE, TEST_STAGE

logger = structlog.get_logger(__name__)


def connect_to_cluster():
    logger.debug("Connecting to Kubernetes Cluster")

    stage = os.environ.get("APPLICATION_STAGE", LOCAL_STAGE)

    if stage == TEST_STAGE:
        raise RuntimeError("Attempt to connect to a live cluster during test!")

    try:
        if stage != LOCAL_STAGE:
            _connect_in_cluster_mode(logger)
        else:
            _connect_using_local_kubeconfig(logger)
    except (TypeError, config.ConfigException) as e:
        logger.error(f"Unable to connect to Kubernetes Cluster: {e!s}")
        raise


def _connect_in_cluster_mode(logger):
    logger.info("Connecting to Kubernetes Cluster in cluster mode")
    config.load_incluster_config()
    logger.info("Connected to Kubernetes Cluster in cluster mode")


def _connect_using_local_kubeconfig(logger):
    logger.info("Connecting to Kubernetes Cluster using local kubeconfig")
    config.load_kube_config()
    logger.info("Connected to Kubernetes Cluster using local kubeconfig")
