# GitHub Gists API

A simple REST API that retrieves publicly available GitHub Gists for a given GitHub username.

## Features

- Fetches public Gists for a GitHub user.
- Supports pagination to retrieve all available Gists.
- Returns Gist details, including ID, description, URL, timestamps, and filenames.
- Provides a health-check endpoint.
- Handles GitHub API errors and request timeouts.
- Includes automated unit tests and Docker support.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/` | Application information |
| GET | `/health` | Health check |
| GET | `/<username>` | Retrieve public Gists for a GitHub user |

### Example

```bash
curl http://localhost:8081/octocat
```

## Prerequisites

- Python 3.12+
- Docker
- Git

## Run Locally

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Start the application:

```bash
python app.py
```

The API will be available at `http://localhost:8080`.

## Run Tests

```bash
python -m unittest discover -s tests -v
```

Tests use mocked GitHub API responses, so they do not depend on GitHub availability.

## Run Using Docker

1. Build the image:

```bash
docker build -t github-gists-api .
```

2. Start the container:

```bash
docker run -d --name github-gists-api -p 8081:8080 github-gists-api
```

3. Verify:

```bash
curl http://localhost:8081/health
curl http://localhost:8081/octocat
```

The container listens on port `8080`; host port `8081` is used to avoid conflict with Jenkins running on port `8080`.

## Configuration

The application supports the following environment variables:

| Variable | Default | Description |
|---|---|---|
| `GITHUB_API_URL` | `https://api.github.com/users/{}/gists` | GitHub Gists API endpoint |
| `GITHUB_API_TIMEOUT` | `10` seconds | Request timeout |
| `LOG_LEVEL` | `INFO` | Application logging level |

## Assumptions and Trade-offs

- Only publicly available Gists are retrieved; GitHub authentication is not required.
- Gists are retrieved using pagination (`100` per page).
- The API depends on GitHub's public API and its rate limits.
- A configurable request timeout prevents requests from waiting indefinitely.
- Unit tests mock external API calls to keep tests reliable and independent.
- Caching and authentication are not implemented to keep the solution simple and focused on the assignment requirements.

## CI/CD

A Jenkins pipeline automates:

1. Source code checkout from GitHub.
2. Dependency installation.
3. Automated unit tests.
4. Docker image build.
5. Container deployment.
6. Application health verification.

## Logging and Troubleshooting

Application logs are written to standard output and can be viewed using:

```bash
docker logs -f github-gists-api
```

To stop and remove the container:

```bash
docker rm -f github-gists-api
```
