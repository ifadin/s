# Scripts

### CI docker images

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

