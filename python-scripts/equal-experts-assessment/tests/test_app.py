import unittest
from unittest.mock import patch, Mock
from app import app

class GitHubGistsAPITest(unittest.TestCase):
    def setUp(self):
        app.config["TESTING"] = True
        self.client = app.test_client()

    def test_default(self):
            response = self.client.get("/")
            self.assertEqual(response.status_code, 200)

    def test_health_check(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["status"],
            "healthy"
        )

    @patch("app.requests.get")
    def test_user_not_found(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        response = self.client.get("/unknownuser")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(
            response.get_json()["error"],
            "GitHub user not found"
        )

    @patch("app.requests.get")
    def test_github_api_failure(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        response = self.client.get("/octocat")
        self.assertEqual(response.status_code, 502)

    @patch("app.requests.get")
    def test_github_api_timeout(self, mock_get):
        import requests
        mock_get.side_effect = requests.exceptions.Timeout
        response = self.client.get("/octocat")
        self.assertEqual(response.status_code, 504)

    @patch("app.requests.get")
    def test_get_user_gists_success(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "id": "12345",
                "description": "Sample Gist",
                "html_url": "https://gist.github.com/12345",
                "public": True,
                "created_at": "2026-01-01T10:00:00Z",
                "updated_at": "2026-01-02T10:00:00Z",
                "files": {
                    "hello.py": {},
                    "README.md": {}
                }
            }
        ]
        mock_get.return_value = mock_response
        response = self.client.get("/octocat")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["username"], "octocat")
        self.assertEqual(data["total_gists"], 1)
        self.assertEqual(data["gists"][0]["id"], "12345")
        self.assertEqual(
            data["gists"][0]["files"],
            ["hello.py", "README.md"]
        )
    

if __name__ == "__main__":
    unittest.main()