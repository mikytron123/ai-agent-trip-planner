
<a name="readme-top"></a>

<h3 align="center">AI Agent Trip Travel </h3>

  <p align="center">
    A multi agent system for planning a vacation in a city using weather data
    <br />
    <br />
  </p>
</div>



<!-- TABLE OF CONTENTS -->
<details>
  <summary>Table of Contents</summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
      <ul>
        <li><a href="#built-with">Built With</a></li>
      </ul>
    </li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
  </ol>
</details>



<!-- ABOUT THE PROJECT -->
## About The Project

This is a multi AI Agent system for planning a trip in a city using historical weather data and nearby attractions. This project uses Ollama for interacting with local LLMs, FastAPI for the backend API, Shiny for the frontend ui. 


<p align="right">(<a href="#readme-top">back to top</a>)</p>



### Built With

* [![Ollama]][Ollama-url]
* [![Shiny]][Shiny-url]
* [![FastAPI]][FastAPI-url]

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- GETTING STARTED -->
## Getting Started

To get a local copy up and running follow these simple steps.

### Prerequisites

Install Docker.
Create a `.env` file using `env.example` as an example.
LLM environment variable should be set to any ollama model.

### Installation

1. Clone the repo
   ```sh
   git clone https://github.com/mikytron123/ai-agent-trip-planner.git
   ```
2. Run Ollama
   ```sh
   ollama serve
   ```
3. Run backend server
   ```sh
   cd backend
   fastapi run
   ```
4. Run shiny ui
   ```sh
   shiny run -p 8001
   ```
<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- USAGE EXAMPLES -->
## Usage

Navigate to `http://localhost:8001` in your browser and start asking questions.

<p align="right">(<a href="#readme-top">back to top</a>)</p>



<!-- MARKDOWN LINKS & IMAGES -->
[FastAPI]: https://img.shields.io/badge/FastAPI-black?style=for-the-badge
[FastAPI-url]: https://fastapi.tiangolo.com/
[Ollama]: https://img.shields.io/badge/Ollama-black?style=for-the-badge
[Ollama-url]: https://www.ollama.com/
[Shiny]: https://img.shields.io/badge/Shiny-black?style=for-the-badge
[Shiny-url]: https://shiny.posit.co/py/
