# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

import base64
import hashlib
import os
from typing import Dict, List

import kubernetes
from kaapanapy.logger import get_logger
from kube_client import get_kube_client
from kubernetes import client

logger = get_logger(__file__)


class Secret:
    """Defines Kubernetes Secret Volume"""

    def __init__(self, deploy_type, deploy_target, secret, key, optional=False):
        """Initialize a Kubernetes Secret Object. Used to track requested secrets from
        the user.
        :param deploy_type: The type of secret deploy in Kubernetes, either `env` or
            `volume`
        :type deploy_type: ``str``
        :param deploy_target: The environment variable when `deploy_type` `env` or
            file path when `deploy_type` `volume` where expose secret
        :type deploy_target: ``str``
        :param secret: Name of the secrets object in Kubernetes
        :type secret: ``str``
        :param key: Key of the secret within the Kubernetes Secret
        :type key: ``str``
        :param optional: Specify whether the Secret or it's key must be defined
        :type optional: ``boolean``
        """
        self.deploy_type = deploy_type
        self.deploy_target = deploy_target
        if deploy_type == "env":
            self.deploy_target = deploy_target.upper()
        self.secret = secret
        self.key = key
        self.optional = optional

    def get_kube_object_env(self):
        if self.deploy_type == "env":
            env = kubernetes.client.V1EnvVar()
            env.name = self.deploy_target

            env_value_from = kubernetes.client.V1EnvVarSource()

            secretKeySelector = kubernetes.client.V1SecretKeySelector()
            secretKeySelector.name = self.secret
            secretKeySelector.key = self.key
            secretKeySelector.optional = self.optional

            env_value_from.secret_key_ref = secretKeySelector
            env.value_from = env_value_from

            return env

        else:
            return None

    def get_kube_object_volume(self):
        if self.deploy_type == "volume":
            kube_volume = kubernetes.client.V1Volume()
            kube_volume.name = self.secret + "_volume"
            secretVolumeSource = kubernetes.client.V1SecretVolumeSource()
            secretVolumeSource.optional = self.optional
            secretVolumeSource.secret_name = self.secret

            secretVolumeSource.items = []
            item = kubernetes.client.V1KeyToPath()
            item.key = self.key
            item.path = os.path.basename(self.deploy_target)
            secretVolumeSource.items.append(item)

            kube_volume.secret = secretVolumeSource

            return kube_volume

    def get_kube_object_volume_mount(self):
        if self.deploy_type == "volume":
            kube_volume_mount = kubernetes.client.V1VolumeMount()

            kube_volume_mount.name = self.secret + "_volume"
            kube_volume_mount.mount_path = self.deploy_target
            kube_volume_mount.sub_path = os.path.basename(self.deploy_target)
            kube_volume_mount.read_only = True

            return kube_volume_mount
        else:
            return None


def create_k8s_secret(
    secret_name: str,
    secret_data: Dict[str, str],
    namespace: str = "secrets",
):

    if not check_namespace_exists(namespace):
        create_namespace(namespace)

    api_instance, _, _ = get_kube_client()

    encoded_credentials = {}
    for key, value in secret_data.items():
        encoded_credentials[key] = base64.b64encode(value.encode("utf-8")).decode(
            "utf-8"
        )

    secret = client.V1Secret(
        api_version="v1",
        kind="Secret",
        metadata=client.V1ObjectMeta(name=secret_name),
        data=encoded_credentials,
        type="Opaque",  # Use "Opaque" type for generic secret data
    )
    try:
        api_instance.create_namespaced_secret(namespace, secret)
        logger.info("Secret created successfully")
    except client.ApiException as e:
        logger.error(f"Secret '{secret_name}' creation FAILED: {e}.")
        if e.status == 409:  # already exists
            return
        else:
            raise e


def delete_k8s_secret(secret_name: str, namespace: str = "secrets"):
    api_instance, _, _ = get_kube_client()

    try:
        api_instance.delete_namespaced_secret(name=secret_name, namespace=namespace)
        logger.info(
            f"Secret '{secret_name}' deleted successfully from namespace '{namespace}'."
        )
    except client.ApiException as e:
        if e.status == 404:
            logger.warning(
                f"Secret '{secret_name}' not found in namespace '{namespace}'."
            )
        else:
            logger.error(f"Failed to delete secret '{secret_name}': {e}.")

    secrets = get_all_k8s_secrets(namespace=namespace)
    if secrets is not None and len(secrets) == 0:
        delete_namespace(namespace)


def get_all_endpoints(namespace: str = "secrets") -> List[str]:
    secrets = get_all_k8s_secrets(namespace)
    return [secret["dcmweb_endpoint"] for secret in secrets]


def get_all_k8s_secrets(namespace: str = "secrets") -> List[Dict[str, str]]:
    api_instance, _, _ = get_kube_client()

    try:
        secrets = api_instance.list_namespaced_secret(namespace=namespace)
        all_secrets = []

        for secret in secrets.items:
            decoded_data = {
                key: base64.b64decode(value).decode("utf-8")
                for key, value in secret.data.items()
            }
            all_secrets.append(decoded_data)

        logger.info(f"All secrets retrieved successfully from namespace '{namespace}'.")
        return all_secrets
    except client.ApiException as e:
        logger.error(f"Failed to retrieve secrets from namespace '{namespace}': {e}.")
        return []


def get_k8s_secret(secret_name: str, namespace: str = "secrets"):
    api_instance, _, _ = get_kube_client()

    try:
        secret = api_instance.read_namespaced_secret(
            name=secret_name, namespace=namespace
        )
        decoded_data = {
            key: base64.b64decode(value).decode("utf-8")
            for key, value in secret.data.items()
        }
        logger.info(
            f"Secret '{secret_name}' retrieved successfully from namespace '{namespace}'."
        )
        return decoded_data
    except client.ApiException as e:
        if e.status == 404:
            logger.warning(
                f"Secret '{secret_name}' not found in namespace '{namespace}'."
            )
        else:
            logger.error(f"Failed to retrieve secret '{secret_name}': {e}.")
        return None


def check_namespace_exists(namespace: str) -> bool:
    api_instance, _, _ = get_kube_client()

    try:
        api_instance.read_namespace(name=namespace)
        logger.info(f"Namespace '{namespace}' exists.")
        return True
    except client.ApiException as e:
        if e.status == 404:
            logger.info(f"Namespace '{namespace}' does not exist.")
            return False
        else:
            logger.error(f"Failed to check namespace '{namespace}': {e}.")
            return False


def create_namespace(namespace: str) -> bool:
    api_instance, _, _ = get_kube_client()
    namespace_body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))

    try:
        api_instance.create_namespace(body=namespace_body)
        logger.info(f"Namespace '{namespace}' created successfully.")
        return True
    except client.ApiException as e:
        logger.error(f"Failed to create namespace '{namespace}': {e}.")
        return False


def delete_namespace(namespace: str) -> bool:
    api_instance, _, _ = get_kube_client()

    try:
        api_instance.delete_namespace(name=namespace)
        logger.info(f"Namespace '{namespace}' removed successfully.")
        return True
    except client.ApiException as e:
        if e.status == 404:
            logger.info(f"Namespace '{namespace}' does not exist.")
        else:
            logger.error(f"Failed to remove namespace '{namespace}': {e}.")
        return False


def hash_secret_name(dcmweb_endpoint: str):
    # Calculate SHA-256 hash of the endpoint URL
    hash_object = hashlib.sha256(dcmweb_endpoint.encode())
    hash_hex = hash_object.hexdigest()

    # Convert hexadecimal hash to a valid Kubernetes secret name
    valid_chars = set("abcdefghijklmnopqrstuvwxyz0123456789.-")
    secret_name = "".join(c if c in valid_chars else "-" for c in hash_hex.lower())

    # Ensure the secret name starts with a letter as per Kubernetes naming convention
    if not secret_name[0].isalpha():
        secret_name = (
            "s-" + secret_name
        )  # prepend 's-' if the name starts with a non-letter

    return secret_name[:63]  # Kubernetes secret names are limited to 63 characters
