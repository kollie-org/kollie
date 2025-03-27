# Kollie
<p align="left">
<a href="https://github.com/kollie-org/kollie/actions/workflows/ci.yaml/badge.svg"><img src="https://github.com/kollie-org/kollie/actions/workflows/ci.yaml/badge.svg" /></a>
<a href="https://github.com/psf/black"><img alt="Code style: black" src="https://img.shields.io/badge/code%20style-black-000000.svg"></a>
<img alt="Kubernetes" src="https://img.shields.io/badge/kubernetes-%E2%9D%A4%EF%B8%8F-blue?logo=kubernetes&labelColor=white">
<img alt="Helm" src="https://img.shields.io/badge/helm-%E2%9D%A4%EF%B8%8F-blue?logo=helm">
<a href="/LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>


Kollie is a tool for herding your ephemeral test environments on Kubernetes; through deploying and managing test environments deployed using Flux and Helm.

It has its origins as an internal developer tool at Tails.com. We are working on making it useful for a wider audience, but please bear with us while we do things like write documentation, build a Helm Chart and remove hardcoded values.

## Deployment guide

Kollie currently makes quite a few assumptions about your environment and your Flux repository structure. Here is a list of the large ones:
* Your Flux GitRepository resources are all located in the `flux-system` namespace
* Each of your applications has a `ImageRepository` resource on your cluster to allow tracking of new container images. It will need its `accessFrom` attribute configured to allow access from the `kollie` namespace.
* The container images are tagged in the format `<branch name>-<git commit id>-<unix timestamp>`
* The ownership attribution of environments relies on `x-auth-request-email` and `x-auth-request-user` headers being sent in requests from something like oauth2-proxy
* There are a number of configuration environment variables and config files which Kollie needs to run. These will be defined in the Helm Chart.
* All Kustomizations created by Kollie have an `environment` and a `downscaler_uptime` [substitution](https://fluxcd.io/flux/components/kustomize/kustomizations/#post-build-variable-substitution). The first just contains the environment name, the second provides a time window for when the environment should _not_ be scaled to 0. More in the [Downscaling](#downscaling) section.
* Kustomization labels and annotations are hardcoded to Tails.com conventions

In addition the following features still have hardcoding, preventing them from working outside of Tails.com (PRs welcome to fix):
* Custom GitRepository Kubernetes resource creation to allow tracking of a non-default branch


## Developer guide

Welcome to the Kollie developer guide. This guide is intended for developers looking to contribute to the Kollie project. Due to the nature of the project, we assume that you are comfortable with reading and understanding technical documentation for a Python project as well as having at least some basic knowledge around Kubernetes, Flux and Helm.

This guide describes the core concepts of Kollie and how to get your local environment set up for development.

### Core concepts

The core idea of Kollie is to piggyback on a design feature of Flux. Flux is a popular tool for deploying applications to Kubernetes clusters. It works by reading a set of Kubernetes manifests from a Git repository and applying them to the cluster.

One of the key features of Flux is the post build variable substitution built into Flux [Kustomizations](https://fluxcd.io/flux/components/kustomize/kustomization/) (not to be confused with [Kustomize overlays](https://github.com/kubernetes-sigs/kustomize)). Flux's Kustomization Controller give us the ability to "fill in" values for placeholders in a base manifest. Under the hood, Flux creates [Kustomization CRDs](https://fluxcd.io/flux/components/kustomize/kustomization/) in our Kubernetes cluster for every app it knows how to deploy. These CRDs define where the base manifest is (`GitRepository` + location within it) and `postBuild` actions such as environment variable substitution. When Flux reads these CRDs, it applies the substitutions to the base manifests and deploys the app. Exactly how the deployment itself is done is dependent on the service itself but in most cases it is done using Helm via Flux's Helm controller.

Kollie takes advantage of this behaviour of Flux by creating Kustomization CRDs similar to what Flux would do, but configured for test environments.

The following diagram illustrates that concept.

![Kollie design](./_static/kollie_design.png)

Don't worry if that description of how Kollie works left your head spinning. Most of the magic happens within Flux. Kollie is just a simple tool that creates YAML files inside Kubernetes clusters! That means you can contribute to this project even if you are new to the world of Kubernetes and infrastructure and learn about those technologies along the way!

Read on to see how you can get started by setting up your local environment for development.

### Setting up local environment

The included docker + docker-compose setup makes it quick and easy to get started with Kollie. Follow the instructions below:

To get started with Kollie, you'll need to set up a local development environment.

#### Cloning the project

The first step is to clone the Kollie project from GitHub. You can do this by running the following command:

```
git clone git@github.com:kollie-org/kollie.git
```

#### Building the project

Once you have cloned the project, you can build it using the `make build` command. This will build the Docker image for the Kollie application.

If it's your first time building the project, you will need to run `make setup-secrets` before running the application. This attempts to populate a `current_user.env` file for auth purposes when working in your local env. If your local git config uses something other than your email address you will need to correct the value stored against the `X_AUTH_REQUEST_EMAIL` key.

#### Running the application

To run the Kollie application, you can use the `make run` command. This will start the Kollie application in a Docker container.

#### Testing the application

To test the Kollie application, you can use the `make test` command. This will run the unit tests for the Kollie application.

### Coding Style and linting
- We use [Black formatter](https://github.com/psf/black). Please make sure your code is formatted using Black or else the CI steps will fail.
- We check for PEP8 and Pyflakes using [Ruff linter](https://github.com/astral-sh/ruff)

## Debugging guide

The common things which go wrong with Kollie environments are related to the Flux Custom Resources which Kollie creates. These are the `Kustomization` and the `ImagePolicy` for each app in an environment. These are made in the `kollie` namespace alongside the Kollie application. Check the status of them with `kubectl` to see if there is a problem reconciling the configuration.

The most common issue in this category is the `ImagePolicy` finding no matching image tags. This is usally because there are no images on the registry matching the configured image tag prefix in the format Kollie looks for (`<image_tag_prefix>-<git_commit_id>-<unixtimestamp>`). However it could also be due to a missing `ImageRepository` object or a problem authenticating to the container image registry configured in that `ImageRepository`.

If the `Kustomization` and `ImagePolicy` are fine, it is worth looking at the resources your Kustomizations are creating (as configured in your git repository). It is possible there is some issue with a downstream `HelmRelease` or similar.

## Downscaling

Kollie is designed to be compatible with https://github.com/caas-team/GoKubeDownscaler . One of the Post Build Substitutions provided to the Kustomization resource by default is an uptime window, which can be fed into the namespace annotation required by that controller. When an environment is created it will always have an uptime window until 7pm that day (UTC). It is possible to extend this window from the web interface for that environment if the test environment is needed by the user/developer for longer (or on another subsequent day).

There is also the concept of a lease_exclusion_window for environments you want to run all the time, during a specific window. If an environment name is specified in the `KOLLIE_LEASE_EXCLUSION_LIST` environment variable then the uptime window will always be configured as the hardcoded (for now) value of `Mon-Fri 07:00-19:00 Europe/London`.
