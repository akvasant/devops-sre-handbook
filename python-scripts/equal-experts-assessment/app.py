import os
import requests
import time
import logging
from flask import Flask, jsonify

app = Flask(__name__)

GITHUB_API_URL = os.getenv("GITHUB_API_URL", "https://api.github.com/users/{}/gists")
GITHUB_API_TIMEOUT = os.getenv("GITHUB_API_TIMEOUT", 10)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)


@app.route("/", methods=["GET"])
def default():
    logger.info("Root endpoint / is accessed")
    return "Equal Experts Coding Assignment", 200

@app.route("/health", methods=["GET"])
def health_check():
    logger.debug("Health check /health is requested")
    return jsonify({"status": "healthy"}), 200

@app.route("/<username>", methods=["GET"])
def get_user_gists(username):
    start_time = time.time()
    logger.info("Received request to fetch Gists for user: %s", username)
    try:
        # response = requests.get(GITHUB_API_URL.format(username), timeout=GITHUB_API_TIMEOUT)
        # if response.status_code == 404:
        #     return jsonify({"error": "GitHub user not found"}), 404
        # if response.status_code != 200:
        #     return jsonify({"error": "Unable to fetch Gists from GitHub"}), 502
        # gists = response.json()
        gists = []
        page = 1
        while True:
            response = requests.get(
                GITHUB_API_URL.format(username),
                params={
                    "per_page": 100,
                    "page": page
                },
                timeout=GITHUB_API_TIMEOUT
            )
            if response.status_code == 404:
                logger.warning("GitHub user not found: %s", username)
                return jsonify({"error": "GitHub user not found"}), 404
            if response.status_code != 200:
                logger.error("GitHub API returned status %s for user: %s",
                    response.status_code,
                    username
                )
                return jsonify({"error": "Unable to fetch Gists from GitHub"}), 502
            page_gists = response.json()
            gists.extend(page_gists)
            if len(page_gists) < 100:
                break
            page += 1
        result = []
        for gist in gists:
            result.append({
                "id": gist["id"],
                "description": gist["description"],
                "url": gist["html_url"],
                "public": gist["public"],
                "created_at": gist["created_at"],
                "updated_at": gist["updated_at"],
                "files": list(gist["files"].keys())
            })
        duration = round(time.time() - start_time, 3)
        logger.info(
            "Successfully fetched %s Gists for user: %s in %s seconds",
            len(result),
            username,
            duration
        )
        return jsonify({
            "username": username,
            "total_gists": len(result),
            "gists": result
        }), 200
    except requests.exceptions.Timeout:
        logger.error("GitHub API request timed out for user: %s", username)
        return jsonify({"error": "GitHub API request timed out"}), 504
    except requests.exceptions.RequestException:
        logger.exception("Error connecting to GitHub API for user: %s", username)
        return jsonify({"error": "Unable to connect to GitHub API"}), 502

if __name__ == "__main__":
    logger.info("Starting GitHub Gists API on port 8080")
    app.run(host="0.0.0.0", port=8080)