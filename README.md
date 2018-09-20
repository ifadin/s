# Scripts

## CI docker images

Images that can be used in CI systems that run just docker containers.

Install all required dependencies in your Dockerfile.ci and publish an image: 

```bash
    cd ci
    bash build.sh --push
```

Then run any command:

```bash
    ./ci.sh java -version
```

#### SBT

Dockerized [sbt](ci/sbt/Dockerfile.ci) ci image witch cached dependencies from your project. 

To build:

0. Copy `ci` folder into your project.
0. Move sbt [Dockerfile.ci](ci/sbt/Dockerfile.ci) into `ci` folder.
0. Publish a ci image.
0. Run any `sbt` command inside: `./ci.sh sbt about`.


## DB utils

 - connect to remote tunnel
 - decrypt local `.pgpass`
 - dump between two remotes
 

## Airflow contrib

- AWS SES email sending [module](./airflow/aws_ses.py).
Put this file into Airflow `PYTHONPATH` and set `AIRFLOW__EMAIL__EMAIL_BACKEND=aws_ses.send_raw_email` env variable.
- Operators:
-- BigQuery insert operator using native python SDK and streaming API

### Run tests 

```bash
    PYTHONPATH=airflow python3 -m unittest discover test
```

To run a specific test:

```bash
    PYTHONPATH=airflow python3 -m unittest test.test_operators
```