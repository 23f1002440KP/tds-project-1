# tds-project-1

A FastAPI-based backend that generates, deploys, and evaluates web applications using LLMs and GitHub Pages.

## Features

- **Task Submission API**: Accepts structured POST requests describing a coding task.
- **LLM Code Generation**: Uses an LLM (via [aipipe.org](https://aipipe.org/)) to generate all necessary application files.
- **Automatic GitHub Deployment**: Creates a new public GitHub repository, commits generated files, and enables GitHub Pages for instant deployment.
- **Evaluation Callback**: Posts deployment details to a provided evaluation URL.
- **CORS Support**: Configurable for development and production.

## Project Structure

```
.
├── app.py               # FastAPI application and endpoints
├── generator.py         # LLM code generation logic
├── github_manager.py    # GitHub API integration and deployment
├── requirements.txt     # Python dependencies
├── Dockerfile           # Containerization setup
├── .gitignore
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.11+
- [GitHub Personal Access Token](https://github.com/settings/tokens) with `repo` scope
- [AI_PIPE_TOKEN](https://aipipe.org/) for LLM access

### Installation

1. **Clone the repository:**
   ```sh
   git clone <repo-url>
   cd tds-project-1
   ```

2. **Install dependencies:**
   ```sh
   pip install -r requirements.txt
   ```

3. **Create a `.env` file:**
   ```
   GITHUB_TOKEN=your_github_token
   GITHUB_USERNAME=your_github_username
   AI_PIPE_TOKEN=your_aipipe_token
   TDS_SECRET=your_secret
   ```

### Running the App

```sh
uvicorn app:app --host 0.0.0.0 --port 7860
```

Or with Docker:

```sh
docker build -t tds-project-1 .
docker run -p 7860:7860 --env-file .env tds-project-1
```

### API Usage

#### Health Check

```http
GET /
```

#### Submit a Task

```http
POST /tasks
Content-Type: application/json

{
  "email": "user@example.com",
  "secret": "your_secret",
  "task": "Build a simple to-do app",
  "round": 1,
  "nonce": "unique-string",
  "brief": "A web app to manage tasks",
  "checks": ["Should add and remove tasks"],
  "evaluation_url": "https://your-callback-url",
  "attachments": [
    "name":"filename.ext",
    "url":"data-uri"
  ]
}
```

### Environment Variables

- `GITHUB_TOKEN`: GitHub PAT with repo access
- `GITHUB_USERNAME`: Your GitHub username
- `AI_PIPE_TOKEN`: Token for LLM API
- `TDS_SECRET`: Secret for authenticating task submissions
- `TDS_ALLOW_ORIGINS`: (Optional) CORS allowed origins

## License

MIT License. See [LICENSE](LICENSE).

## Acknowledgements

- [FastAPI](https://fastapi.tiangolo.com/)
- [PyGithub](https://pygithub.readthedocs.io/)
- [aipipe.org](https://aipipe.org/)