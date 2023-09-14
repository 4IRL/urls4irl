from urls4irl import create_app
from os import environ
from dotenv import load_dotenv

load_dotenv(override=True)
if environ.get("PRODUCTION") is None:
    print("Missing PRODUCTION environment variable.")
    quit()

is_production_env_var = environ.get("PRODUCTION")

if is_production_env_var.lower() not in ("false", "true"):
    print("Invalid PRODUCTION environment variable.")
    quit()
else:
    is_production = True if is_production_env_var.lower() == "true" else False

app = create_app()

if __name__ == "__main__":
    if not is_production:
        print("Not in production.")
        app.run(port=5000)
    else:
        print("In production.")
        app.run(host="0.0.0.0")
