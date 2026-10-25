// Config writers: pure functions that take the current file content and
// return the new content, so merging is tested without touching disk.

/** Merge MCP server entries into a Claude Desktop or ChatGPT style config ({ mcpServers: {...} }). Existing entries with other names are kept. */
export function mergeMcpServers(existingJson, entries) {
  let doc = {};
  if (existingJson && existingJson.trim()) {
    try { doc = JSON.parse(existingJson); } catch { throw new Error("The existing config is not valid JSON; fix it by hand first."); }
  }
  if (typeof doc !== "object" || doc === null || Array.isArray(doc)) doc = {};
  doc.mcpServers = { ...(doc.mcpServers || {}), ...entries };
  return JSON.stringify(doc, null, 2) + "\n";
}

/** The MCP entries the console registers in Claude Desktop and ChatGPT. */
export function lapidaryMcpEntries({ backendDir, pythonExe, reaCommand = "npx", reaArgs = ["-y", "rea-agents@6.4.0", "mcp"] }) {
  return {
    lapidary: { command: pythonExe, args: [`${backendDir}/mcp_server.py`] },
    rea: { command: reaCommand, args: reaArgs },
  };
}

/**
 * A docker compose file for Open WebUI with Lapidary, OpenAI and Ollama as providers.
 * Lapidary is reached from inside the container as host.docker.internal.
 */
export function openWebUICompose({ lapidaryKey, openaiKey = "", port = 3080, lapidaryPort = 8000 }) {
  const urls = [`http://host.docker.internal:${lapidaryPort}/v1`];
  const keys = [lapidaryKey];
  if (openaiKey) { urls.push("https://api.openai.com/v1"); keys.push(openaiKey); }
  return [
    "services:",
    "  open-webui:",
    "    image: ghcr.io/open-webui/open-webui:main",
    "    container_name: open-webui",
    `    ports: ["${port}:8080"]`,
    "    environment:",
    `      OPENAI_API_BASE_URLS: "${urls.join(";")}"`,
    `      OPENAI_API_KEYS: "${keys.join(";")}"`,
    '      OLLAMA_BASE_URL: "http://host.docker.internal:11434"',
    '      WEBUI_NAME: "Lapidary"',
    "    extra_hosts: [\"host.docker.internal:host-gateway\"]",
    "    volumes: [\"open-webui:/app/backend/data\"]",
    "    restart: unless-stopped",
    "volumes:",
    "  open-webui: {}",
    "",
  ].join("\n");
}

/** The MCP server list Lapidary's own backend reads (configs/mcp_servers.json). */
export function lapidaryMcpServersFile({ reaCommand = "npx", reaArgs = ["-y", "rea-agents@6.4.0", "mcp"] }) {
  return JSON.stringify({ mcpServers: { rea: { command: reaCommand, args: reaArgs, risky: false } } }, null, 2) + "\n";
}

/** Environment for the backend sidecar from the console's settings. */
export function backendEnv(settings, { dataDir, mcpServersFile }) {
  const env = {
    GEMS_API_KEY: settings.gemsApiKey,
    GEMS_STORAGE: "sqlite",
    GEMS_SQLITE_PATH: `${dataDir}/lapidary.db`,
    GEMS_MCP_SERVERS_FILE: mcpServersFile,
    CORS_ORIGINS: "http://localhost:3000",
  };
  env.GEMS_MODEL_POLICY = settings.modelPolicy || "auto";
  if (settings.localBaseUrl) env.LOCAL_OPENAI_BASE_URL = settings.localBaseUrl;
  if (settings.anthropicKey) env.ANTHROPIC_API_KEY = settings.anthropicKey;
  if (settings.openaiKey) env.OPENAI_API_KEY = settings.openaiKey;
  if (settings.supabaseUrl && settings.supabaseKey) {
    env.GEMS_STORAGE = "supabase";
    env.SUPABASE_URL = settings.supabaseUrl;
    env.SUPABASE_SERVICE_ROLE_KEY = settings.supabaseKey;
  }
  return env;
}
