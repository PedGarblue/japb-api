# japb-api

[![Build Status](https://travis-ci.org/PedGarblue/japb-api.svg?branch=master)](https://travis-ci.org/PedGarblue/japb-api)
[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

Just Another Personal Budget API.

# Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/)  

# Local Development

Copy and modify at with your hosts  the `web.env.example` file:

```bash
    cp web.env.example web.env
```

Start the dev server for local development:
```bash
docker-compose up
```

Run a command inside the docker container:

```bash
docker-compose run --rm web [command]
```

Create admin user on container

```bash
docker exec -it django_test_web_1 bash

python3 manage.py createsuperuser
```
