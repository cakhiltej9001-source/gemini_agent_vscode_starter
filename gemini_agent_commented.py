"""
gemini_agent_commented.py

Beginner-friendly AI Agent example using:
1) Google Gemini (via Google AI Studio API key) as the reasoning model
2) yfinance as a stock-price tool
3) Safe, allowlisted OS commands as a system tool

IMPORTANT:
- Put your Gemini API key in a .env file. Never hard-code it here.
- The OS command tool below only permits a small set of safe commands.
- Stock data comes from Yahoo Finance through yfinance and may be delayed.
"""

# ============================================================
# 1. IMPORT REQUIRED LIBRARIES
# ============================================================

# os:
# - reads environment variables such as GEMINI_API_KEY
# - helps identify whether the computer is Windows/Linux/macOS
# - gives the current working directory
import os

# sys:
# Used here to get the exact Python executable/version being used.
import sys

# platform:
# Gives basic information about the operating system and machine.
import platform

# subprocess:
# Lets Python execute operating-system commands.
# We use it carefully with an allowlist instead of running arbitrary commands.
import subprocess

# datetime:
# Used to return the current local system time.
from datetime import datetime

# yfinance:
# Retrieves the latest available market data from Yahoo Finance.
import yfinance as yf

# dotenv:
# Loads variables from a local .env file.
from dotenv import load_dotenv

# Google's official Gemini SDK.
from google import genai
from google.genai import types


# ============================================================
# 2. LOAD ENVIRONMENT VARIABLES
# ============================================================

# Reads the .env file from the current project folder.
load_dotenv()

# Read your Google AI Studio API key from .env.
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Read the model name from .env.
# If GEMINI_MODEL is missing, use gemini-2.5-flash by default.
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Stop early with a clear message if the API key is missing.
if not GEMINI_API_KEY:
    raise ValueError(
        "GEMINI_API_KEY was not found.\n"
        "Create a .env file in this folder and add:\n"
        "GEMINI_API_KEY=your_key_here"
    )


# ============================================================
# 3. CREATE THE GEMINI CLIENT
# ============================================================

# The client is the Python application's connection to Gemini.
client = genai.Client(api_key=GEMINI_API_KEY)


# ============================================================
# 4. STOCK TOOL
# ============================================================

# This dictionary lets the user type either a company name or ticker.
# Example:
#   "nvidia" -> "NVDA"
#   "apple"  -> "AAPL"
COMPANY_SYMBOLS = {
    "apple": "AAPL",
    "nvidia": "NVDA",
    "microsoft": "MSFT",
    "google": "GOOGL",
    "alphabet": "GOOGL",
    "amazon": "AMZN",
    "meta": "META",
    "tesla": "TSLA",
}


def get_stock_price(symbol: str) -> dict:
    """
    Return the latest available stock price for a company/ticker.

    Example inputs:
        "AAPL"
        "NVDA"
        "Apple"
        "NVIDIA"

    Why return a dictionary?
    ------------------------
    Structured data is easier for Gemini to understand and use reliably
    than an unstructured paragraph.
    """

    try:
        # Remove accidental spaces from the user/model input.
        cleaned = symbol.strip()

        # If the input is a known company name, convert it to a ticker.
        # Otherwise assume the user already supplied a ticker symbol.
        ticker_symbol = COMPANY_SYMBOLS.get(
            cleaned.lower(),
            cleaned.upper()
        )

        print(f"\n📈 TOOL CALLED -> get_stock_price('{ticker_symbol}')")

        # Create a yfinance object for the requested stock.
        ticker = yf.Ticker(ticker_symbol)

        # Try to get today's minute-level data.
        history = ticker.history(
            period="1d",
            interval="1m",
            auto_adjust=False
        )

        # Sometimes minute-level data is unavailable, for example:
        # - market is closed
        # - provider does not return recent minute data
        # In that case, try a larger time window.
        if history.empty:
            history = ticker.history(
                period="5d",
                interval="5m",
                auto_adjust=False
            )

        # If yfinance still returned no data, report a clean failure.
        if history.empty:
            return {
                "success": False,
                "symbol": ticker_symbol,
                "error": "No stock-price data was returned."
            }

        # Remove missing Close values.
        close_prices = history["Close"].dropna()

        if close_prices.empty:
            return {
                "success": False,
                "symbol": ticker_symbol,
                "error": "No valid closing price was found."
            }

        # iloc[-1] means: take the final/latest row.
        latest_price = float(close_prices.iloc[-1])

        # Capture the timestamp associated with that latest price.
        latest_time = close_prices.index[-1]

        result = {
            "success": True,
            "symbol": ticker_symbol,
            "latest_price": round(latest_price, 2),
            "timestamp": str(latest_time),
            "source": "Yahoo Finance via yfinance",
            "note": (
                "Latest available market price. "
                "Data can be delayed depending on the exchange/provider."
            )
        }

        print("✅ STOCK TOOL RESULT:", result)

        return result

    except Exception as e:
        # Tools should fail gracefully instead of crashing the whole agent.
        return {
            "success": False,
            "symbol": symbol,
            "error": str(e)
        }


# ============================================================
# 5. SAFE OS COMMAND TOOL
# ============================================================

def get_safe_commands() -> dict:
    """
    Build an allowlist of operating-system commands.

    Why use an allowlist?
    ---------------------
    Giving an AI model unrestricted shell access is unsafe.
    Instead, Gemini can only choose one of the operations below.
    """

    # os.name == "nt" means Windows.
    if os.name == "nt":
        return {
            "list_files": ["cmd", "/c", "dir"],
            "current_directory": ["cmd", "/c", "cd"],
            "whoami": ["whoami"],
            "hostname": ["hostname"],
            "python_version": [sys.executable, "--version"],
            "system_info": ["cmd", "/c", "ver"],
        }

    # Linux/macOS commands.
    return {
        "list_files": ["ls", "-la"],
        "current_directory": ["pwd"],
        "whoami": ["whoami"],
        "hostname": ["hostname"],
        "python_version": [sys.executable, "--version"],
        "system_info": ["uname", "-a"],
    }


def run_os_command(command_name: str) -> dict:
    """
    Execute one SAFE command from the allowlist.

    Allowed logical command names:
        list_files
        current_directory
        whoami
        hostname
        python_version
        system_info

    Notice:
    The model does NOT provide a raw shell command such as:
        rm ...
        del ...
        powershell ...
    It only selects a predefined operation.
    """

    # Normalize the selected tool input.
    command_name = command_name.strip().lower()

    print(f"\n💻 TOOL CALLED -> run_os_command('{command_name}')")

    # Get the safe command mapping for the current operating system.
    safe_commands = get_safe_commands()

    # Refuse anything not explicitly permitted.
    if command_name not in safe_commands:
        return {
            "success": False,
            "error": f"Command '{command_name}' is not allowed.",
            "allowed_commands": list(safe_commands.keys())
        }

    try:
        # Translate logical name -> actual command array.
        command = safe_commands[command_name]

        # Run the command.
        #
        # shell=False:
        #   avoids passing arbitrary command text through a shell.
        #
        # timeout=10:
        #   prevents a stuck process from running forever.
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
            shell=False
        )

        # Successful commands usually write to stdout.
        output = result.stdout.strip()

        # If stdout is empty, capture stderr instead.
        if not output:
            output = result.stderr.strip()

        response = {
            "success": result.returncode == 0,
            "command_name": command_name,
            "output": output,
            "return_code": result.returncode
        }

        print("✅ OS TOOL RESULT:")
        print(output)

        return response

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out after 10 seconds."
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# ============================================================
# 6. BASIC SYSTEM-INFORMATION TOOL
# ============================================================

def get_system_details() -> dict:
    """
    Return basic information about the computer running this script.

    This tool does not execute arbitrary terminal commands.
    """

    print("\n🖥️ TOOL CALLED -> get_system_details()")

    return {
        "operating_system": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "current_directory": os.getcwd(),
        "current_time": datetime.now().isoformat()
    }


# ============================================================
# 7. SYSTEM PROMPT = AGENT INSTRUCTIONS
# ============================================================

# The system prompt tells Gemini:
# - what role it has
# - what tools are available
# - when it should use them
# - what safety rules it must follow
SYSTEM_PROMPT = """
You are a beginner-friendly tool-using AI agent.

Your job is to understand the user's request, decide whether a tool is
required, use the correct tool when necessary, observe the tool result,
and then give a concise final answer.

AVAILABLE TOOLS

1. get_stock_price(symbol)
Use it whenever the user asks for the latest available stock price.

Common mappings:
Apple -> AAPL
NVIDIA -> NVDA
Microsoft -> MSFT
Google/Alphabet -> GOOGL
Amazon -> AMZN
Meta -> META
Tesla -> TSLA


2. run_os_command(command_name)
Use it when the user asks for one of these safe system operations:

- list_files
- current_directory
- whoami
- hostname
- python_version
- system_info


3. get_system_details()
Use it when the user asks about the local operating system, machine,
Python version, current directory, or current system time.

RULES

- Never invent a stock price.
- If current market data is requested, use get_stock_price.
- Never claim an OS command ran unless you actually used the tool.
- Never attempt an OS command outside the approved allowlist.
- Explain errors clearly if a tool fails.
- Keep final answers concise and beginner-friendly.
"""


# ============================================================
# 8. REGISTER PYTHON FUNCTIONS AS GEMINI TOOLS
# ============================================================

# The Gemini SDK can inspect these Python function signatures/docstrings
# and expose them as callable tools to the model.
#
# Conceptually:
#
# User -> Gemini -> selects a function -> Python executes it
#      -> result goes back to Gemini -> Gemini answers the user
config = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=[
        get_stock_price,
        run_os_command,
        get_system_details
    ],
    # Lower temperature = more deterministic/tool-focused behavior.
    temperature=0.2,
)


# ============================================================
# 9. CREATE A CHAT SESSION
# ============================================================

# A chat object keeps conversational context while this program is running.
#
# Important:
# This is session context, not permanent long-term memory.
chat = client.chats.create(
    model=MODEL,
    config=config
)


# ============================================================
# 10. USER/AGENT LOOP
# ============================================================

print("\n" + "=" * 70)
print("🤖 GEMINI TOOL-USING AI AGENT")
print("=" * 70)

print(f"\nModel: {MODEL}")

print("\nAvailable abilities:")
print("  📈 Get the latest available stock prices")
print("  💻 Run a small set of safe OS commands")
print("  🖥️ Inspect basic system information")

print("\nTry questions such as:")
print("  1. What is NVIDIA's latest stock price?")
print("  2. What is Apple's latest stock price?")
print("  3. List the files in my current directory.")
print("  4. What Python version am I running?")
print("  5. What operating system am I using?")

print("\nType 'exit' to stop.\n")


# Outer application loop:
# Keep accepting user requests until the user types exit/quit/bye.
while True:

    user_query = input("👤 You: ").strip()

    # Exit condition.
    if user_query.lower() in {"exit", "quit", "bye"}:
        print("\n👋 Agent stopped.")
        break

    # Ignore empty input.
    if not user_query:
        continue

    try:
        # Send the user's natural-language request to Gemini.
        #
        # Because tools were registered above, Gemini can decide whether
        # it needs to call one of them before composing the final answer.
        response = chat.send_message(user_query)

        print("\n🤖 Gemini:")
        print(response.text)
        print()

    except Exception as e:
        # Catch API/network/runtime errors so the program can continue.
        print("\n❌ ERROR:")
        print(e)
        print()


# ============================================================
# END OF PROGRAM
# ============================================================

# Main architecture to remember:
#
#       USER
#         |
#         v
#      GEMINI
#         |
#     Need a tool?
#      /       \
#    Yes        No
#     |          |
#     v          |
# Python Tool    |
#     |          |
# Observation    |
#     \          /
#      v        v
#       GEMINI
#         |
#         v
#    FINAL ANSWER
#
# This is the core idea behind a tool-using AI agent.
