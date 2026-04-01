#!/usr/bin/env python3
"""APS Executor — runs APS procedures using Ollama + tool execution.
Simple agent loop: prompt -> model -> tool calls -> execute -> repeat."""

import json, subprocess, sys, re, time, urllib.request, os

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "command-r:latest"
MAX_TURNS = 15

TOOLS = [{
    "type": "function",
    "function": {
        "name": "exec",
        "description": "Execute a shell command and return stdout+stderr",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"}
            },
            "required": ["command"]
        }
    }
}]


def chat(messages):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as resp:
        return json.loads(resp.read())


def parse_tool_calls_from_text(text):
    """Parse tool calls from model text output when Ollama returns them in content."""
    calls = []
    cleaned = text.strip()
    # Strip markdown code blocks
    if "```" in cleaned:
        blocks = re.findall(r"```(?:\w*\n)?(.*?)```", cleaned, re.DOTALL)
        for block in blocks:
            try:
                obj = json.loads(block.strip())
                if isinstance(obj, dict) and "name" in obj:
                    calls.append(obj)
                    return calls
            except (json.JSONDecodeError, ValueError):
                pass

    # Try to parse the whole text as JSON (maybe with trailing text)
    # Find the first { and match to its closing }
    brace_start = cleaned.find("{")
    if brace_start >= 0:
        depth = 0
        for i in range(brace_start, len(cleaned)):
            if cleaned[i] == "{":
                depth += 1
            elif cleaned[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = cleaned[brace_start:i+1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict) and "name" in obj and "arguments" in obj:
                            calls.append(obj)
                            return calls
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    # Fallback regex
    for match in re.finditer(r'\{"name"\s*:\s*"exec"\s*,\s*"arguments"\s*:\s*\{[^}]+\}\s*\}', text):
        try:
            obj = json.loads(match.group())
            calls.append(obj)
        except (json.JSONDecodeError, ValueError):
            pass

    # Last resort: find "command" value directly and construct the call
    if not calls:
        cmd_match = re.search(r'"command"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
        if cmd_match:
            calls.append({"name": "exec", "arguments": {"command": cmd_match.group(1)}})

    return calls


def execute_command(cmd):
    print(f"  [EXEC] {cmd}", flush=True)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=60, cwd="/home/openclaw"
        )
        output = result.stdout + result.stderr
        return output.strip() or "(no output)", result.returncode
    except subprocess.TimeoutExpired:
        return "ERROR: Command timed out after 60 seconds", 1
    except Exception as e:
        return f"ERROR: {e}", 1


def check_output(output, returncode):
    """Pattern-match known error responses. Returns (success, failure_reason)."""
    # Shell-level failure
    if returncode != 0:
        return False, f"Exit code {returncode}"
    if output.startswith("ERROR:"):
        return False, output

    # API error patterns (JSON responses with error fields)
    if '"error"' in output and '"code"' in output:
        try:
            data = json.loads(output)
            if data.get("error"):
                err = data["error"]
                msg = err.get("message", str(err))
                return False, f"API error: {msg}"
        except (json.JSONDecodeError, ValueError):
            pass

    # HTTP error patterns
    if "<title>401 Unauthorized</title>" in output or "Invalid Authentication" in output:
        return False, "Authentication failed (401)"
    if "<title>403 Forbidden</title>" in output:
        return False, "Forbidden (403)"
    if "<title>404 Not Found</title>" in output:
        return False, "Not found (404)"
    if "<title>500" in output:
        return False, "Server error (500)"

    # FreeIPA-specific patterns
    if "Insufficient access" in output or "ACIError" in output:
        return False, "FreeIPA: insufficient permissions"
    if "Invalid JSON-RPC" in output or "JSONError" in output:
        return False, "FreeIPA: invalid JSON-RPC request"

    # HTML page returned (expected JSON but got HTML)
    if output.strip().startswith("<!DOCTYPE html>") or output.strip().startswith("<html"):
        return False, "Got HTML instead of expected API response"

    # Permission/access patterns
    if "Permission denied" in output:
        return False, "Permission denied"
    if "Connection refused" in output:
        return False, "Connection refused"

    return True, None


FEEDBACK_URL = os.environ.get("APS_FEEDBACK_URL", "http://localhost:8000/api/v1/aps/feedback/")


def post_feedback(tx_log):
    """POST transaction log to CISO Platform feedback endpoint."""
    payload = {
        "service_name": tx_log.get("service_name", "unknown"),
        "scope": tx_log.get("scope"),
        "agent": tx_log.get("agent", "qwen"),
        "overall_success": all(s["success"] for s in tx_log["steps"]) if tx_log["steps"] else False,
        "duration_seconds": round(time.time() - tx_log["start_time"], 2),
        "total_steps": len(tx_log["steps"]),
        "steps_completed": sum(1 for s in tx_log["steps"] if s["success"]),
        "error_summary": tx_log.get("error_summary"),
        "steps": tx_log["steps"],
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(FEEDBACK_URL, data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())
            print(f"  [FEEDBACK] Posted: id={result.get('id')}", flush=True)
    except Exception as e:
        print(f"  [FEEDBACK] Failed to post: {e}", flush=True)


def run(task, service_name="unknown", scope=None, agent="qwen"):
    tx_log = {
        "service_name": service_name,
        "scope": scope,
        "agent": agent,
        "steps": [],
        "start_time": time.time(),
        "error_summary": None,
    }

    messages = [
        {"role": "system", "content":
         "You execute tasks by running shell commands. STRICT RULES:\n"
         "1. To run a command, respond with ONLY this JSON and NOTHING else:\n"
         '   {"name": "exec", "arguments": {"command": "your command"}}\n'
         "2. Do NOT add any text before or after the JSON. No markdown. No explanation.\n"
         "3. You MUST execute EVERY command listed in the task. Do NOT skip commands.\n"
         "4. Do NOT summarize or report results until you have run ALL commands.\n"
         "5. Do NOT make up or hallucinate results. Only report what the commands actually output.\n"
         "6. Run ONE command at a time. Wait for output before the next.\n"
         "7. After ALL commands are done, give your final plain text summary with real output data only."},
        {"role": "user", "content": task}
    ]

    final_result = None

    for turn in range(MAX_TURNS):
        print(f"\n--- Turn {turn+1} ---", flush=True)
        try:
            resp = chat(messages)
        except Exception as e:
            tx_log["error_summary"] = f"Model call failed: {e}"
            print(f"  [ERROR] Model call failed: {e}", flush=True)
            break

        msg = resp["message"]
        content = msg.get("content", "").strip()
        tool_calls = msg.get("tool_calls", [])

        # Try native tool_calls first, then parse from content
        if not tool_calls and content:
            parsed = parse_tool_calls_from_text(content)
            if parsed:
                tool_calls = [{"function": tc} for tc in parsed]

        if not tool_calls:
            # No tool calls — final response
            print(f"  [RESULT] {content}", flush=True)
            final_result = content
            break

        # Execute tool calls
        messages.append(msg)  # Keep full assistant message with tool_calls

        for tc in tool_calls:
            fn = tc.get("function", tc)
            args = fn.get("arguments", {})
            # Handle different model formats:
            # qwen3: {"arguments": {"command": "..."}}
            # command-r: {"arguments": {"parameters": {"command": "..."}, "tool_name": "exec"}}
            cmd = args.get("command", "")
            if not cmd and "parameters" in args:
                cmd = args["parameters"].get("command", "")
            if not cmd:
                continue
            output, returncode = execute_command(cmd)
            success, failure_reason = check_output(output, returncode)

            status_tag = "PASS" if success else f"FAIL: {failure_reason}"
            print(f"  [{status_tag}]", flush=True)
            print(f"  [OUTPUT] {output[:1000]}", flush=True)
            messages.append({"role": "tool", "content": output})

            # Record step
            tx_log["steps"].append({
                "step_number": len(tx_log["steps"]) + 1,
                "prescribed_command": None,
                "actual_command": cmd,
                "output": output[:2000],
                "success": success,
                "failure_reason": failure_reason,
                "deviation": False,
            })
    else:
        tx_log["error_summary"] = "Max turns reached"
        final_result = "Max turns reached"

    # Post feedback
    post_feedback(tx_log)

    return final_result


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="APS Executor — run procedures via Ollama")
    parser.add_argument("task", nargs="*", help="Task description")
    parser.add_argument("--service", default="unknown", help="Service name for feedback")
    parser.add_argument("--scope", default=None, help="Scope for feedback")
    parser.add_argument("--agent", default="qwen", help="Agent name for feedback")
    args = parser.parse_args()

    task_text = " ".join(args.task) if args.task else input("Task: ")
    result = run(task_text, service_name=args.service, scope=args.scope, agent=args.agent)
    print(f"\n=== FINAL RESULT ===\n{result}")
