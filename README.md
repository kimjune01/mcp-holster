# Holster

This server makes swapping in and out of MCP servers with Claude config happen from inside Claude desktop instead of opening a text editor.

The default location for the config file is located in

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

## Motivation

Dealing with text editors for manually modifying a JSON file is a job perfect for LLMs, but Claude only gives a pointer to the config file and wishes us luck. Can we do better?

## Scope

The most common way I find servers is through Github, and I download them manually. For now, downloading or looking for servers out on the web is out of scope.

Keeping track of workspaces defined a collection of servers would be a nice to have, but out of scope for now.

### Create

Given that I have mcp servers in a directory somewhere, in my case, I clone them into `~/Documents` or make new ones of my own in there. Holster should be able to look at it and make up a server config and insert it into Claude's config file.

### Read

Given that I have one or many mcp servers, the client should be able to query for all the mcp servers. In order to keep things simple, the config file for Claude should be the only source of truth. Servers not being used shouldn't be recognized by Claude, but be recognized by Holster.

The read tool call should display two lists of tools by name, used and unused.

### Update

Although the easiest thing to do would be to comment out the unused servers, JSON does not support comments. It should be moved to a different array that is not recognized by Claude. The alternative key to `mcpServers` is `unusedMcpServers`.

In order to mark a server to not be used, it should be moved from one array to another. The parameters to this tool call should be an array of server names, as specified from Read.

To make the operation deterministic, the tool call should involve parsing and encoding JSON.

### Delete

Deleting an object from inside the JSON array should also involve parsing and encoding JSON, taking in an array of server names.
