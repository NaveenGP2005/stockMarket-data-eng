import os
import sys
import subprocess

# 1. Manually load environment variables from .env if it exists
env_path = os.path.abspath(".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                # Strip quotes if present
                val = val.strip().strip("'").strip('"')
                os.environ[key.strip()] = val
    print("Loaded environment variables from .env file.")
else:
    print("Warning: .env file not found. Running with system environment variables.")

# 2. Configure dbt directory
dbt_dir = os.path.abspath("dbt_stocks")

# 3. Build dbt command (default to 'run' if no args provided)
args = sys.argv[1:]
if not args:
    args = ["run"]

command = ["dbt"] + args + ["--profiles-dir", "."]

print(f"Executing: {' '.join(command)}")
print(f"Working directory: {dbt_dir}\n")

# 4. Run dbt command
try:
    result = subprocess.run(
        command,
        cwd=dbt_dir,
        shell=True if os.name == 'nt' else False, # Safely run shell command on Windows
        check=True
    )
    print("\ndbt command completed successfully!")
except subprocess.CalledProcessError as e:
    print(f"\nError: dbt command failed with exit code {e.returncode}")
    sys.exit(e.returncode)
