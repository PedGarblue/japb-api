# japb-api

[![Build Status](https://travis-ci.org/PedGarblue/japb-api.svg?branch=master)](https://travis-ci.org/PedGarblue/japb-api)
[![Built with](https://img.shields.io/badge/Built_with-Cookiecutter_Django_Rest-F7B633.svg)](https://github.com/agconti/cookiecutter-django-rest)

Just Another Personal Budgeet API. Check out the project's [documentation](http://PedGarblue.github.io/japb-api/).

# Prerequisites

- [Docker](https://docs.docker.com/docker-for-mac/install/)  

# Local Development

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
