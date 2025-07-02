# PTT MCP Server

This project is a PTT agent based on `fastmcp` and `PyPtt`, which can operate PTT through the MCP protocol.

## Features

- Login and logout
- Get, post, reply, delete, and comment on posts
- Send, get, and delete mail
- Give money (P幣)
- Get user, post, and board information
- and more...

## Installation

1.  Clone the project:
    ```bash
    git clone https://github.com/your-username/mcp_server.git
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Create a `.env` file and set the following environment variables:
    ```
    PTT_ID=your_ptt_id
    PTT_PW=your_ptt_password
    ```

## Usage

Run the MCP server:

```bash
python src/mcp_server.py
```

Then you can connect to the server with your MCP client.

## API

For detailed API documentation, please refer to the `basic_api.py` file.
