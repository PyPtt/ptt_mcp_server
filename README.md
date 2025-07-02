# PTT MCP Server

This project is a PTT agent based on `fastmcp` and the powerful [`PyPtt`](https://pyptt.cc/) library, enabling it to truly log in and interact with the PTT bulletin board system through the MCP protocol.

## Features

- Login and logout
- Get, post, reply, delete, and comment on posts
- Send, get, and delete mail
- Give money (P幣)
- Get user, post, and board information
- and more...

## Installation

```bash
pip install ptt-mcp-server
```

## Usage

Run the MCP server:

```bash
ptt-mcp-server
```

Then you can connect to the server with your MCP client.

### MCP Client Configuration

Here is an example of how to configure your MCP client to connect to the server:

```json
{
  "mcpServers": {
    "PTT": {
      "command": "ptt-mcp-server",
      "env": {
        "PTT_ID": "YOUR_PTT_ID",
        "PTT_PW": "YOUR_PTT_PW"
      }
    }
  }
}
```

**Note:**

*   Replace `YOUR_PTT_ID` and `YOUR_PTT_PW` with your actual PTT credentials.

### Alternative MCP Client Configuration (Using a Virtual Environment)

If you prefer to explicitly use a Python interpreter from a virtual environment, or if the `ptt-mcp-server` command is not directly available in your system's PATH, you can configure your MCP client as follows:

```json
{
  "mcpServers": {
    "PTT": {
      "command": "/path/to/your/venv/bin/python3", // Replace with the actual path to your venv's python executable
      "args": ["/path/to/your/project/src/mcp_server.py"], // Replace with the actual path to mcp_server.py
      "env": {
        "PTT_ID": "YOUR_PTT_ID",
        "PTT_PW": "YOUR_PTT_PW"
      }
    }
  }
}
```

**Note:**

*   Replace `/path/to/your/venv/bin/python3` with the absolute path to the Python executable within your virtual environment (e.g., `/Users/codingman/git/mcp_server/.venv/bin/python3`).
*   Replace `/path/to/your/project/src/mcp_server.py` with the absolute path to the `mcp_server.py` file within your project (e.g., `/Users/codingman/git/mcp_server/src/mcp_server.py`).

## API

For detailed API documentation, please refer to the `basic_api.py` file.
